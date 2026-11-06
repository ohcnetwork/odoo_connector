import base64
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import date_utils


class PurchaseReturnRegisterWizard(models.TransientModel):
    _name = "care.purchase.return.register.wizard"
    _description = "Purchase Return Register Wizard"

    date_from = fields.Date(required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(required=True, default=lambda self: date_utils.end_of(date.today(), "month"))
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    posted_only = fields.Boolean(
        default=True,
        help="If enabled, only posted bills are included.",
    )
    gross_mode = fields.Selection(
        [
            ("tax_amount", "Tax Amount"),
            ("taxable_base", "Taxable Base"),
        ],
        required=True,
        default="taxable_base",
        help="Controls how GROSS columns are computed for GST buckets.",
    )
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    _ZERO_BUCKET = Decimal("0")
    _RATE_PRECISION = Decimal("0.01")
    # GST slabs that always get columns, even when no credit note in the period uses them. Any other
    # rate (12%, 28%, ...) gets columns only in periods that use it.
    _FIXED_RATES = tuple(Decimal(rate).quantize(Decimal("0.01")) for rate in ("5", "18"))
    # Supplier credit note numbers are typed as "CREDIT NOTE NO: CR26..." and similar,
    # sometimes followed by the note's date.
    _REF_PREFIX = re.compile(r"^\s*CREDIT\s+NOTE?\s+(?:BILL\s+)?NO\s*[:;.]?\s*", re.IGNORECASE)
    _REF_DATE_SUFFIX = re.compile(r"\s+DTD\s*[:.]?\s*\S+\s*$", re.IGNORECASE)

    @api.onchange("date_from")
    def _onchange_date_from(self):
        if self.date_from:
            self.date_to = date_utils.end_of(self.date_from, "month")

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Date From cannot be greater than Date To."))

    def action_export_excel(self):
        self.ensure_one()
        xlsx_content = self._build_xlsx_bytes()
        filename = "purchase_return_register_%s_to_%s.xlsx" % (
            self._file_date(self.date_from),
            self._file_date(self.date_to),
        )
        self.write(
            {
                "file_data": base64.b64encode(xlsx_content),
                "file_name": filename,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/?model=care.purchase.return.register.wizard&id=%s&field=file_data&filename_field=file_name&download=true"
            % self.id,
            "target": "self",
        }

    def _file_date(self, value):
        # Same as the sheet's d-mmm-yy dates, e.g. 1-Jun-26.
        return "%s-%s" % (value.day, value.strftime("%b-%y"))

    def _d(self, value):
        if value in (None, ""):
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    def _absd(self, value):
        val = self._d(value)
        return -val if val < 0 else val

    def _extract_percent(self, name):
        if not name:
            return Decimal("0")
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", str(name))
        return self._d(match.group(1)) if match else Decimal("0")

    def _normalize_rate(self, rate):
        if rate in (None, ""):
            return None
        normalized = self._absd(rate).quantize(self._RATE_PRECISION)
        return normalized

    def _line_bucket_rate(self, line):
        rates = set()
        for tax in line.tax_ids:
            tax_name = (tax.name or "").upper()
            if "GST" not in tax_name:
                continue
            component_rate = self._absd(tax.amount) or self._extract_percent(tax.name)
            if not component_rate:
                continue
            if "CGST" in tax_name or "SGST" in tax_name:
                bucket_rate = self._normalize_rate(component_rate * Decimal("2"))
            else:
                bucket_rate = self._normalize_rate(component_rate)
            if bucket_rate is not None:
                rates.add(bucket_rate)
        if len(rates) == 1:
            return next(iter(rates))
        return None

    def _supplier_note_number(self, ref):
        number = self._REF_PREFIX.sub("", ref or "")
        return self._REF_DATE_SUFFIX.sub("", number).strip()

    def _prepare_rows(self):
        self.ensure_one()

        # The month is the day the return was booked (the accounting date), as in the old
        # pharmacy register; the supplier's credit note date goes in Invoice Date.
        domain = [
            ("company_id", "=", self.company_id.id),
            ("move_type", "=", "in_refund"),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
        ]
        if self.posted_only:
            domain.append(("state", "=", "posted"))

        moves = self.env["account.move"].search(domain, order="date, name, id")
        if not moves:
            raise ValidationError(_("No records found for the selected filters."))

        rows = []
        for move in moves:
            partner = move.partner_id.commercial_partner_id
            address_parts = [
                partner.street or "",
                partner.street2 or "",
                partner.city or "",
                partner.state_id.name or "",
                partner.zip or "",
            ]
            address = ", ".join([part for part in address_parts if part])

            bucket_data = defaultdict(
                lambda: {
                    "taxable": Decimal("0"),
                    "cgst": Decimal("0"),
                    "sgst": Decimal("0"),
                    "igst": Decimal("0"),
                }
            )
            bucket_data[self._ZERO_BUCKET]
            # Amounts are taken from the journal items' balance with the sign flipped (a credit
            # note credits the purchase and tax accounts), so a returned line comes out positive.
            invoice_lines = move.invoice_line_ids.filtered(lambda line: line.display_type == "product")
            line_total = sum(-self._d(line.balance) for line in invoice_lines)
            for line in invoice_lines:
                taxable = -self._d(line.balance)
                bucket_rate = self._line_bucket_rate(line)
                if bucket_rate in (None, self._ZERO_BUCKET):
                    bucket_data[self._ZERO_BUCKET]["taxable"] += taxable
                    continue
                bucket_data[bucket_rate]["taxable"] += taxable
            # Taxable Value is the gross at the GST rates only: 0% and untaxed lines
            # show under GST 0% alone, as in the old register. Invoice Value has both.
            taxable_total = line_total - bucket_data[self._ZERO_BUCKET]["taxable"]

            tax_lines = move.line_ids.filtered(lambda line: line.tax_line_id)

            for tax_line in tax_lines:
                tax = tax_line.tax_line_id
                tax_name = (tax.name or "").upper()
                component_rate = self._absd(tax.amount) or self._extract_percent(tax.name)
                tax_amount = -self._d(tax_line.balance)
                bucket_rate = None
                if "IGST" in tax_name:
                    bucket_rate = self._normalize_rate(component_rate)
                elif "CGST" in tax_name or "SGST" in tax_name:
                    bucket_rate = self._normalize_rate(component_rate * Decimal("2"))
                elif "GST" in tax_name:
                    bucket_rate = self._normalize_rate(component_rate)

                if bucket_rate in (None, self._ZERO_BUCKET):
                    continue

                if "CGST" in tax_name:
                    bucket_data[bucket_rate]["cgst"] += tax_amount
                elif "SGST" in tax_name:
                    bucket_data[bucket_rate]["sgst"] += tax_amount
                else:
                    bucket_data[bucket_rate]["igst"] += tax_amount

            gst_total = sum(
                bucket["cgst"] + bucket["sgst"] + bucket["igst"] for bucket in bucket_data.values()
            )

            rows.append(
                {
                    "bill_no": move.name or "",
                    "bill_date": move.date,
                    "invoice_no": self._supplier_note_number(move.ref),
                    "invoice_date": move.invoice_date,
                    # Lines plus GST to the paisa; Odoo's whole-rupee rounding is left out.
                    "invoice_value": line_total + gst_total,
                    "place_of_supply": partner.state_id.name or " - ",
                    "gstin": partner.vat or "",
                    "party": partner.name or "",
                    "address": address,
                    "taxable_total": taxable_total,
                    "buckets": dict(bucket_data),
                }
            )
        return rows

    def _build_xlsx_bytes(self):
        rows = self._prepare_rows()
        rates = sorted(
            set(self._FIXED_RATES)
            | {
                rate
                for row in rows
                for rate, values in row["buckets"].items()
                if rate != self._ZERO_BUCKET
                and (values["taxable"] or values["cgst"] or values["sgst"] or values["igst"])
            }
        )
        output = io.BytesIO()
        workbook = None
        try:
            import xlsxwriter
            from xlsxwriter.utility import xl_rowcol_to_cell

            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            sheet = workbook.add_worksheet(_("Purchase Return Register"))

            header_fmt = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1})
            subheader_fmt = workbook.add_format({"bold": True, "align": "center", "border": 1})
            text_fmt = workbook.add_format({"border": 1})
            num_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
            date_fmt = workbook.add_format({"border": 1, "num_format": "d-mmm-yy"})
            total_text_fmt = workbook.add_format({"bold": True, "border": 1})
            total_num_fmt = workbook.add_format({"bold": True, "border": 1, "num_format": "#,##0.00"})

            # Header row 1: columns before the GST slabs span both header rows.
            columns = [
                ("Bill No", 20),
                ("Bill Date", 11),
                ("Invoice No", 20),
                ("Invoice Date", 11),
                ("Invoice Value", 14),
                ("Place Of Supply", 16),
                ("GSTIN", 18),
                ("Party", 30),
                ("Address", 40),
                ("Taxable Value", 14),
                ("GST 0%", 12),
            ]
            for col, (label, width) in enumerate(columns):
                sheet.merge_range(0, col, 1, col, label, header_fmt)
                sheet.set_column(col, col, width)

            # Header rows 1 and 2: one GST slab over its GROSS, CGST, SGST and IGST columns.
            rates_start_col = len(columns)
            for idx, rate in enumerate(rates):
                base = rates_start_col + (idx * 4)
                rate_label = format(rate.normalize(), "f")
                sheet.merge_range(0, base, 0, base + 3, "GST %s%%" % rate_label, header_fmt)
                for offset, label in enumerate(("GROSS", "CGST", "SGST", "IGST")):
                    sheet.write(1, base + offset, label, subheader_fmt)
                sheet.set_column(base, base, 12)
                sheet.set_column(base + 1, base + 3, 10)
            last_col = rates_start_col + (len(rates) * 4) - 1

            first_data_row = 2
            row_idx = first_data_row
            totals = defaultdict(Decimal)

            def write_amount(col, value):
                sheet.write_number(row_idx, col, float(value), num_fmt)
                totals[col] += value

            def write_date(col, value):
                if value:
                    sheet.write_datetime(row_idx, col, value, date_fmt)
                else:
                    sheet.write(row_idx, col, "", text_fmt)

            for row in rows:
                sheet.write(row_idx, 0, row["bill_no"], text_fmt)
                write_date(1, row["bill_date"])
                sheet.write(row_idx, 2, row["invoice_no"], text_fmt)
                write_date(3, row["invoice_date"])
                write_amount(4, row["invoice_value"])
                sheet.write(row_idx, 5, row["place_of_supply"], text_fmt)
                sheet.write(row_idx, 6, row["gstin"], text_fmt)
                sheet.write(row_idx, 7, row["party"], text_fmt)
                sheet.write(row_idx, 8, row["address"], text_fmt)
                write_amount(9, row["taxable_total"])
                zero_bucket = row["buckets"].get(self._ZERO_BUCKET, {})
                write_amount(10, zero_bucket.get("taxable", Decimal("0")))

                for idx, rate in enumerate(rates):
                    start_col = rates_start_col + (idx * 4)
                    bucket = row["buckets"].get(
                        rate,
                        {"taxable": Decimal("0"), "cgst": Decimal("0"), "sgst": Decimal("0"), "igst": Decimal("0")},
                    )
                    tax_amount = bucket["cgst"] + bucket["sgst"] + bucket["igst"]
                    gross_val = tax_amount if self.gross_mode == "tax_amount" else bucket["taxable"]
                    write_amount(start_col, gross_val)
                    write_amount(start_col + 1, bucket["cgst"])
                    write_amount(start_col + 2, bucket["sgst"])
                    write_amount(start_col + 3, bucket["igst"])
                row_idx += 1

            # Totals row: SUM formulas, with the computed totals cached for viewers that don't recalculate.
            sheet.write(row_idx, 0, _("Total"), total_text_fmt)
            for col in range(1, last_col + 1):
                if col in totals:
                    formula = "=SUM(%s:%s)" % (
                        xl_rowcol_to_cell(first_data_row, col),
                        xl_rowcol_to_cell(row_idx - 1, col),
                    )
                    sheet.write_formula(row_idx, col, formula, total_num_fmt, float(round(totals[col], 2)))
                else:
                    sheet.write_blank(row_idx, col, None, total_text_fmt)

        finally:
            if workbook:
                workbook.close()
        return output.getvalue()
