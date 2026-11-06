import base64
from collections import defaultdict
from datetime import date
from decimal import Decimal
import io

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import date_utils


class SalesRegisterBase(models.AbstractModel):
    """Shared by the sales and sales return registers: which invoice lines count, their GST
    by slab, and the sheet layout of the hospital's old billing software."""

    _name = "care.sales.register.base"
    _description = "Sales Register Base"

    date_from = fields.Date(required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(required=True, default=lambda self: date_utils.end_of(date.today(), "month"))
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    account_ids = fields.Many2many(
        "account.account",
        string="Accounts",
        check_company=True,
        domain="[('account_type', 'in', ('income', 'income_other'))]",
        default=lambda self: self.env.company.care_stock_sales_account_ids,
        help="Only invoice lines posted to these accounts are counted. Defaults to the stock sales "
        "accounts in Accounting settings. Leave empty to count every line.",
    )
    show_cancelled = fields.Boolean(
        string="Show Cancelled Bills",
        help="List bills cancelled after posting, with CANCELLED as the party and zero amounts.",
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
    # Set by each register.
    _SHEET_NAME = ""
    _FILE_PREFIX = ""

    @api.onchange("date_from")
    def _onchange_date_from(self):
        if self.date_from:
            self.date_to = date_utils.end_of(self.date_from, "month")

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Date From cannot be greater than Date To."))

    @api.onchange("company_id")
    def _onchange_company_id_accounts(self):
        self.account_ids = self.company_id.care_stock_sales_account_ids

    def action_export_excel(self):
        self.ensure_one()
        xlsx_content = self._build_xlsx_bytes()
        filename = "%s_%s_to_%s.xlsx" % (self._FILE_PREFIX, self.date_from, self.date_to)
        self.write(
            {
                "file_data": base64.b64encode(xlsx_content),
                "file_name": filename,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/?model=%s&id=%s&field=file_data&filename_field=file_name&download=true"
            % (self._name, self.id),
            "target": "self",
        }

    def _move_types(self):
        raise NotImplementedError

    def _counted_lines(self, move):
        lines = move.invoice_line_ids.filtered(lambda line: line.display_type == "product")
        if self.account_ids:
            lines = lines.filtered(lambda line: line.account_id in self.account_ids)
        return lines

    def _gst_component(self, tax):
        group = (tax.tax_group_id.name or "").upper()
        if "CGST" in group:
            return "cgst"
        if "SGST" in group or "UTGST" in group:
            return "sgst"
        if "IGST" in group:
            return "igst"
        return None

    def _empty_bucket(self):
        return {"taxable": Decimal("0"), "cgst": Decimal("0"), "sgst": Decimal("0"), "igst": Decimal("0")}

    def _move_amounts(self, move):
        """Taxable value and GST per slab of the move's counted lines, and their invoice value.

        GST comes from each line's own tax details, rounded to the move's tax journal items, so a
        bill with lines on other accounts brings in only the GST of its counted lines. The invoice
        value is the bill total when every line counts, otherwise the counted lines with their GST.
        Amounts keep the document's sign: positive for invoices and credit notes alike.
        """
        lines = self._counted_lines(move)
        counted_ids = set(lines.ids)
        currency = move.company_currency_id
        buckets = defaultdict(self._empty_bucket)
        buckets[self._ZERO_BUCKET]
        base_lines, _tax_lines = move._get_rounded_base_and_tax_lines()
        for base_line in base_lines:
            line = base_line["record"]
            if line.id not in counted_ids:
                continue
            rate = Decimal("0")
            components = self._empty_bucket()
            for tax_data in base_line["tax_details"]["taxes_data"]:
                component = self._gst_component(tax_data["tax"])
                if not component:
                    continue
                rate += abs(Decimal(str(tax_data["tax"].amount)))
                components[component] += Decimal(str(currency.round(tax_data["tax_amount"])))
            bucket = buckets[rate.quantize(self._RATE_PRECISION)]
            bucket["taxable"] += Decimal(str(line.price_subtotal))
            for component in ("cgst", "sgst", "igst"):
                bucket[component] += components[component]

        all_lines = move.invoice_line_ids.filtered(lambda line: line.display_type == "product")
        if lines == all_lines:
            invoice_value = Decimal(str(move.amount_total))
        else:
            invoice_value = sum(
                (bucket["taxable"] + bucket["cgst"] + bucket["sgst"] + bucket["igst"] for bucket in buckets.values()),
                Decimal("0"),
            )
        return dict(buckets), invoice_value

    def _place_of_supply(self, move):
        state = move.l10n_in_state_id or move.partner_id.commercial_partner_id.state_id
        if not state:
            return ""
        name = (state.name or "").upper()
        return "%s - %s" % (state.l10n_in_tin, name) if state.l10n_in_tin else name

    def _prepare_rows(self):
        self.ensure_one()
        state_domain = [("state", "=", "posted")]
        if self.show_cancelled:
            state_domain = ["|", ("state", "=", "posted"), "&", ("state", "=", "cancel"), ("posted_before", "=", True)]
        domain = [
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", self._move_types()),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
            *state_domain,
        ]
        if self.account_ids:
            domain.append(("invoice_line_ids.account_id", "in", self.account_ids.ids))

        moves = self.env["account.move"].search(domain, order="invoice_date, name, id")
        if not moves:
            raise ValidationError(_("No records found for the selected filters."))

        rows = []
        for move in moves:
            row = {
                "bill_no": move.name or "",
                "bill_date": move.invoice_date or move.date,
                "place_of_supply": self._place_of_supply(move),
            }
            if move.state == "cancel":
                row.update(party=_("CANCELLED"), invoice_value=Decimal("0"), buckets={})
            else:
                buckets, invoice_value = self._move_amounts(move)
                row.update(
                    party=move.partner_id.commercial_partner_id.name or "",
                    invoice_value=invoice_value,
                    buckets=buckets,
                )
            rows.append(row)
        return rows

    def _build_xlsx_bytes(self):
        rows = self._prepare_rows()
        used_rates = {
            rate
            for row in rows
            for rate, values in row["buckets"].items()
            if rate != self._ZERO_BUCKET and any(values.values())
        }
        rates = sorted(used_rates.union(self._FIXED_RATES))
        empty = self._empty_bucket()

        output = io.BytesIO()
        workbook = None
        try:
            import xlsxwriter

            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            sheet = workbook.add_worksheet(self._SHEET_NAME)

            header_fmt = workbook.add_format({"bold": True, "align": "center", "border": 1})
            text_fmt = workbook.add_format({"border": 1})
            num_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
            date_fmt = workbook.add_format({"border": 1, "num_format": "dd-mm-yyyy"})
            total_text_fmt = workbook.add_format({"bold": True, "border": 1})
            total_num_fmt = workbook.add_format({"bold": True, "border": 1, "num_format": "#,##0.00"})

            headers = [
                "Bill No",
                "Bill Date",
                "Invoice Value",
                "Place Of Supply",
                "Party",
                "Taxable Value",
                "GST 0%",
            ]
            for col, label in enumerate(headers):
                sheet.write(0, col, label, header_fmt)
            rates_start_col = len(headers)
            for idx, rate in enumerate(rates):
                base = rates_start_col + (idx * 4)
                rate_label = str(rate.normalize()).rstrip("0").rstrip(".")
                sheet.merge_range(0, base, 0, base + 3, "GST %s%%" % rate_label, header_fmt)
                sheet.write(1, base, "GROSS", header_fmt)
                sheet.write(1, base + 1, "CGST", header_fmt)
                sheet.write(1, base + 2, "SGST", header_fmt)
                sheet.write(1, base + 3, "IGST", header_fmt)
            # Amount columns from Invoice Value onwards, totalled in the last row.
            column_count = rates_start_col + len(rates) * 4

            widths = [20, 12, 14, 18, 30, 14, 12]
            for col, width in enumerate(widths):
                sheet.set_column(col, col, width)
            for idx in range(len(rates)):
                base = rates_start_col + (idx * 4)
                sheet.set_column(base, base, 12)
                sheet.set_column(base + 1, base + 3, 10)

            totals = [Decimal("0")] * column_count
            amount_cols = [2, 5, 6] + list(range(rates_start_col, column_count))

            row_idx = 2
            for row in rows:
                buckets = row["buckets"]
                values = [Decimal("0")] * column_count
                values[2] = row["invoice_value"]
                values[5] = sum(
                    (bucket["taxable"] for rate, bucket in buckets.items() if rate != self._ZERO_BUCKET),
                    Decimal("0"),
                )
                values[6] = buckets.get(self._ZERO_BUCKET, empty)["taxable"]
                for idx, rate in enumerate(rates):
                    base = rates_start_col + (idx * 4)
                    bucket = buckets.get(rate, empty)
                    tax_amount = bucket["cgst"] + bucket["sgst"] + bucket["igst"]
                    values[base] = tax_amount if self.gross_mode == "tax_amount" else bucket["taxable"]
                    values[base + 1] = bucket["cgst"]
                    values[base + 2] = bucket["sgst"]
                    values[base + 3] = bucket["igst"]

                sheet.write(row_idx, 0, row["bill_no"], text_fmt)
                if row["bill_date"]:
                    sheet.write_datetime(row_idx, 1, row["bill_date"], date_fmt)
                else:
                    sheet.write(row_idx, 1, "", text_fmt)
                sheet.write(row_idx, 3, row["place_of_supply"], text_fmt)
                sheet.write(row_idx, 4, row["party"], text_fmt)
                for col in amount_cols:
                    sheet.write_number(row_idx, col, float(values[col]), num_fmt)
                    totals[col] += values[col]
                row_idx += 1

            sheet.write(row_idx, 0, _("Total"), total_text_fmt)
            for col in (1, 3, 4):
                sheet.write(row_idx, col, "", total_text_fmt)
            for col in amount_cols:
                sheet.write_number(row_idx, col, float(totals[col]), total_num_fmt)

        finally:
            if workbook:
                workbook.close()
        return output.getvalue()
