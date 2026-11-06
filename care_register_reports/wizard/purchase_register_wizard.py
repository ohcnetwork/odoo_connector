import base64
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import date_utils


class PurchaseRegisterWizard(models.TransientModel):
    _name = "care.purchase.register.wizard"
    _description = "Purchase Register Wizard"

    date_from = fields.Date(required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(required=True, default=lambda self: date_utils.end_of(date.today(), "month"))
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    include_refunds = fields.Boolean(
        string="Include Credit Notes",
        help="Include vendor credit notes (refunds) in the export.",
    )
    posted_only = fields.Boolean(
        default=True,
        help="If enabled, only posted bills are included.",
    )
    care_only = fields.Boolean(
        string="Only Bills from Care",
        default=True,
        help="List only bills created from Care. Untick to include bills entered directly in Odoo.",
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
    # GST slabs that always get columns, even when no bill in the period uses them. Any other
    # rate (12%, 28%, ...) gets columns only in periods that use it.
    _FIXED_RATES = tuple(Decimal(rate).quantize(Decimal("0.01")) for rate in ("5", "18"))

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
        filename = "purchase_register_%s_to_%s.xlsx" % (
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
            "url": "/web/content/?model=care.purchase.register.wizard&id=%s&field=file_data&filename_field=file_name&download=true"
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

    def _get_grn_number(self, move):
        grn_numbers = []
        if move.grn_number:
            grn_numbers.append(str(move.grn_number))

        pickings = move.stock_move_ids.mapped("picking_id").filtered(
            lambda p: p and p.state == "done" and p.picking_type_id.code == "incoming"
        )
        if not pickings and move.invoice_origin:
            origins = [part.strip() for part in str(move.invoice_origin).split(",") if part.strip()]
            if origins:
                pickings = self.env["stock.picking"].search(
                    [
                        ("company_id", "=", move.company_id.id),
                        ("origin", "in", origins),
                        ("state", "=", "done"),
                        ("picking_type_id.code", "=", "incoming"),
                    ]
                )

        picking_names = sorted(set(pickings.mapped("name")))
        for picking_name in picking_names:
            if picking_name and picking_name not in grn_numbers:
                grn_numbers.append(picking_name)

        return ", ".join(grn_numbers)

    def _prepare_rows(self):
        self.ensure_one()
        move_types = ["in_invoice", "in_receipt"]
        if self.include_refunds:
            move_types.append("in_refund")

        domain = [
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", move_types),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]
        if self.care_only:
            # Only stock purchases: bills created from Care deliveries. Bills typed in Odoo
            # (salaries, fees, utilities, services) are left out.
            domain.append(("x_care_id", "!=", False))
        if self.posted_only:
            domain.append(("state", "=", "posted"))

        moves = self.env["account.move"].search(domain, order="invoice_date, name, id")
        if not moves:
            raise ValidationError(_("No records found for the selected filters."))

        rows = []
        for move in moves:
            partner = move.partner_id.commercial_partner_id
            grn_number = self._get_grn_number(move)
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
            # Amounts are taken from the journal items' balance (debit positive), so a
            # discount line reduces the bill and credit notes come out negative.
            invoice_lines = move.invoice_line_ids.filtered(lambda line: line.display_type == "product")
            line_total = sum(self._d(line.balance) for line in invoice_lines)
            for line in invoice_lines:
                taxable = self._d(line.balance)
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
                tax_amount = self._d(tax_line.balance)
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
            round_off = sum(
                self._d(line.balance) for line in move.line_ids if line.display_type == "rounding"
            )

            rows.append(
                {
                    "bill_no": move.name or "",
                    "bill_date": move.invoice_date or move.date,
                    "invoice_no": move.ref or "",
                    "grn_no": grn_number,
                    "invoice_date": move.invoice_date or move.date,
                    "invoice_value": line_total + gst_total,
                    "round_off": round_off,
                    "bill_total": -self._d(move.amount_total_signed),
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
            sheet = workbook.add_worksheet(_("Purchase Register"))

            header_fmt = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1})
            subheader_fmt = workbook.add_format({"bold": True, "align": "center", "border": 1})
            text_fmt = workbook.add_format({"border": 1})
            num_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
            date_fmt = workbook.add_format({"border": 1, "num_format": "d-mmm-yy"})
            total_text_fmt = workbook.add_format({"bold": True, "border": 1})
            total_num_fmt = workbook.add_format({"bold": True, "border": 1, "num_format": "#,##0.00"})

            # Header row 1: columns before the GST slabs span both header rows.
            columns = [
                ("Bill No", 18),
                ("Bill Date", 11),
                ("Invoice No", 20),
                ("GRN No", 14),
                ("Invoice Date", 11),
                ("Invoice Value", 14),
                ("Round Off", 10),
                ("Bill Total", 14),
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

            for row in rows:
                sheet.write(row_idx, 0, row["bill_no"], text_fmt)
                if row["bill_date"]:
                    sheet.write_datetime(row_idx, 1, row["bill_date"], date_fmt)
                else:
                    sheet.write(row_idx, 1, "", text_fmt)
                sheet.write(row_idx, 2, row["invoice_no"], text_fmt)
                sheet.write(row_idx, 3, row["grn_no"], text_fmt)
                if row["invoice_date"]:
                    sheet.write_datetime(row_idx, 4, row["invoice_date"], date_fmt)
                else:
                    sheet.write(row_idx, 4, "", text_fmt)
                write_amount(5, row["invoice_value"])
                write_amount(6, row["round_off"])
                write_amount(7, row["bill_total"])
                sheet.write(row_idx, 8, row["place_of_supply"], text_fmt)
                sheet.write(row_idx, 9, row["gstin"], text_fmt)
                sheet.write(row_idx, 10, row["party"], text_fmt)
                sheet.write(row_idx, 11, row["address"], text_fmt)
                write_amount(12, row["taxable_total"])
                zero_bucket = row["buckets"].get(self._ZERO_BUCKET, {})
                write_amount(13, zero_bucket.get("taxable", Decimal("0")))

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
