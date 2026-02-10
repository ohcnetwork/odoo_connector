import base64
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PurchaseReturnRegisterWizard(models.TransientModel):
    _name = "care.purchase.return.register.wizard"
    _description = "Purchase Return Register Wizard"

    date_from = fields.Date(required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(required=True, default=lambda self: date.today())
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

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Date From cannot be greater than Date To."))

    def action_export_excel(self):
        self.ensure_one()
        xlsx_content = self._build_xlsx_bytes()
        filename = "purchase_return_register_%s_to_%s.xlsx" % (self.date_from, self.date_to)
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

    def _get_grn_info(self, move):
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

        grn_date = False
        date_values = [d for d in pickings.mapped("date_done") if d]
        if date_values:
            grn_date = min(date_values).date()

        return ", ".join(grn_numbers), grn_date

    def _prepare_rows(self):
        self.ensure_one()
        move_types = ["in_refund"]

        domain = [
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", move_types),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]
        if self.posted_only:
            domain.append(("state", "=", "posted"))

        moves = self.env["account.move"].search(domain, order="invoice_date, name, id")
        if not moves:
            raise ValidationError(_("No records found for the selected filters."))

        rows = []
        for move in moves:
            partner = move.partner_id.commercial_partner_id
            grn_number, grn_date = self._get_grn_info(move)
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
            invoice_lines = move.invoice_line_ids.filtered(lambda line: line.display_type == "product")
            taxable_total = sum(self._absd(line.price_subtotal) for line in invoice_lines)
            for line in invoice_lines:
                taxable = self._absd(line.price_subtotal)
                bucket_rate = self._line_bucket_rate(line)
                if bucket_rate in (None, self._ZERO_BUCKET):
                    bucket_data[self._ZERO_BUCKET]["taxable"] += taxable
                    continue
                bucket_data[bucket_rate]["taxable"] += taxable

            tax_lines = move.line_ids.filtered(lambda line: line.tax_line_id)

            for tax_line in tax_lines:
                tax = tax_line.tax_line_id
                tax_name = (tax.name or "").upper()
                component_rate = self._absd(tax.amount) or self._extract_percent(tax.name)
                tax_amount = self._absd(tax_line.amount_currency or tax_line.balance)
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

            rows.append(
                {
                    "bill_no": move.name or "",
                    "bill_date": move.invoice_date or move.date,
                    "invoice_no": move.ref or "",
                    "grn_no": grn_number,
                    "grn_date": grn_date,
                    "invoice_date": move.invoice_date or move.date,
                    "invoice_value": self._absd(move.amount_total),
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
        dynamic_rates = sorted(
            {
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

            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            sheet = workbook.add_worksheet(_("Purchase Return Register"))

            header_fmt = workbook.add_format({"bold": True, "align": "center", "border": 1})
            subheader_fmt = workbook.add_format({"bold": True, "align": "center", "border": 1})
            text_fmt = workbook.add_format({"border": 1})
            num_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
            date_fmt = workbook.add_format({"border": 1, "num_format": "dd-mm-yyyy"})

            # Header row 1
            headers = [
                "Credit Note No",
                "Credit Note Date",
                "Invoice No",
                "GRN No",
                "GRN Date",
                "Invoice Date",
                "Invoice Value",
                "Place Of Supply",
                "GSTIN",
                "Party",
                "Address",
                "Taxable Value",
                "GST 0%",
            ]
            for col, label in enumerate(headers):
                sheet.write(0, col, label, header_fmt)
            rates_start_col = len(headers)
            for idx, rate in enumerate(dynamic_rates):
                base_col = rates_start_col + (idx * 4)
                rate_label = str(rate.normalize()).rstrip("0").rstrip(".")
                sheet.write(0, base_col, "GST %s%%" % rate_label, header_fmt)

            # Header row 2
            for idx in range(len(dynamic_rates)):
                base = rates_start_col + (idx * 4)
                sheet.write(1, base, "GROSS", subheader_fmt)
                sheet.write(1, base + 1, "CGST", subheader_fmt)
                sheet.write(1, base + 2, "SGST", subheader_fmt)
                sheet.write(1, base + 3, "IGST", subheader_fmt)

            widths = {
                0: 18,
                1: 12,
                2: 20,
                3: 20,
                4: 12,
                5: 12,
                6: 14,
                7: 18,
                8: 18,
                9: 30,
                10: 40,
                11: 14,
                12: 12,
                13: 12,
                14: 10,
                15: 10,
                16: 10,
                17: 12,
                18: 10,
                19: 10,
                20: 10,
                21: 12,
                22: 10,
                23: 10,
                24: 10,
                25: 12,
                26: 10,
                27: 10,
                28: 10,
            }
            for col, width in widths.items():
                sheet.set_column(col, col, width)
            for idx in range(len(dynamic_rates)):
                base = rates_start_col + (idx * 4)
                sheet.set_column(base, base, 12)
                sheet.set_column(base + 1, base + 3, 10)

            row_idx = 2
            for row in rows:
                sheet.write(row_idx, 0, row["bill_no"], text_fmt)
                if row["bill_date"]:
                    sheet.write_datetime(row_idx, 1, row["bill_date"], date_fmt)
                else:
                    sheet.write(row_idx, 1, "", text_fmt)
                sheet.write(row_idx, 2, row["invoice_no"], text_fmt)
                sheet.write(row_idx, 3, row["grn_no"], text_fmt)
                if row["grn_date"]:
                    sheet.write_datetime(row_idx, 4, row["grn_date"], date_fmt)
                else:
                    sheet.write(row_idx, 4, "", text_fmt)
                if row["invoice_date"]:
                    sheet.write_datetime(row_idx, 5, row["invoice_date"], date_fmt)
                else:
                    sheet.write(row_idx, 5, "", text_fmt)
                sheet.write_number(row_idx, 6, float(row["invoice_value"]), num_fmt)
                sheet.write(row_idx, 7, row["place_of_supply"], text_fmt)
                sheet.write(row_idx, 8, row["gstin"], text_fmt)
                sheet.write(row_idx, 9, row["party"], text_fmt)
                sheet.write(row_idx, 10, row["address"], text_fmt)
                sheet.write_number(row_idx, 11, float(row["taxable_total"]), num_fmt)
                zero_bucket = row["buckets"].get(self._ZERO_BUCKET, {})
                sheet.write_number(row_idx, 12, float(zero_bucket.get("taxable", Decimal("0"))), num_fmt)

                for idx, rate in enumerate(dynamic_rates):
                    start_col = rates_start_col + (idx * 4)
                    bucket = row["buckets"].get(
                        rate,
                        {"taxable": Decimal("0"), "cgst": Decimal("0"), "sgst": Decimal("0"), "igst": Decimal("0")},
                    )
                    tax_amount = bucket["cgst"] + bucket["sgst"] + bucket["igst"]
                    gross_val = tax_amount if self.gross_mode == "tax_amount" else bucket["taxable"]
                    sheet.write_number(row_idx, start_col, float(gross_val), num_fmt)
                    sheet.write_number(row_idx, start_col + 1, float(bucket["cgst"]), num_fmt)
                    sheet.write_number(row_idx, start_col + 2, float(bucket["sgst"]), num_fmt)
                    sheet.write_number(row_idx, start_col + 3, float(bucket["igst"]), num_fmt)
                row_idx += 1

        finally:
            if workbook:
                workbook.close()
        return output.getvalue()
