from odoo import models, _
from odoo.exceptions import ValidationError


class TDSVendorExcelReport(models.AbstractModel):
    _name = "report.vendor_tds_auto_apply.tds_vendor_excel_report"
    _inherit = "report.report_xlsx.abstract"
    _description = "TDS Vendor Excel Report"

    def _get_data(self, data):
        domain = [
            ("date", ">=", data["date_from"]),
            ("date", "<=", data["date_to"]),
            ('vendor_tds', '>', 0),
            ("move_type", "=", "in_invoice")
        ]
        if data.get("vendor_ids"):
            domain.append(("partner_id", "in", data["vendor_ids"]))

        account_move_recs = self.env["account.move"].search(domain)
        tds_list = []
        for move in account_move_recs:
            tds_move_recs = self.env["account.move"].search([('l10n_in_withholding_ref_move_id','=',move.id)])
            if tds_move_recs:
                for tds_move in tds_move_recs:
                    tds_lines = tds_move.line_ids.filtered(lambda l: l.tax_ids)
                    for line in tds_lines:
                        tds_list.append({
                            "inv_name": move.name,
                            "vendor": move.partner_id.name,
                            "tds_tax_name": line.tax_ids.name,
                            "tds_tax_amount": abs(line.l10n_in_withhold_tax_amount),
                            "tds_date": tds_move.date,
                        })

        if not tds_list:
            raise ValidationError(_("No records found...!!!"))
        return tds_list

    def generate_xlsx_report(self, workbook, data, records):
        sheet = workbook.add_worksheet(_("TDS Vendor Report"))

        title_format = workbook.add_format({
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "font_size": 14,
        })
        info_format = workbook.add_format({
            "align": "left",
            "valign": "vcenter",
            "font_size": 11,
        })
        header_format = workbook.add_format({
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        text_format = workbook.add_format({
            "border": 1,
            "align": "center"
        })
        num_format = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        total_format = workbook.add_format({
            "bold": True,
            "align": "right",
            "border": 1,
            "num_format": "#,##0.00"
        })

        sheet.merge_range("A1:D1", "TDS Vendor Report", title_format)
        sheet.write("A3", "Date From:", info_format)
        sheet.write("B3", data.get("date_from") or "")
        sheet.write("C3", "Date To:", info_format)
        sheet.write("D3", data.get("date_to") or "")

        headers = ["Date", "Vendor", "Bill No","Vendor TDS"]
        for col, header in enumerate(headers):
            sheet.write(5, col, header, header_format)
            sheet.set_column(col, col, 20)

        row = 6
        grand_tds = 0.0

        records = self._get_data(data)

        for rec in records:
            tds_amount = rec['tds_tax_amount'] or 0.0
            sheet.write(row, 0, rec['tds_date'].strftime("%d-%m-%Y") if rec['tds_date'] else "", text_format)
            sheet.write(row, 1, rec['vendor'] or "", text_format)
            sheet.write(row, 2, rec['inv_name'] or "", text_format)
            sheet.write_number(row, 3, tds_amount, num_format)
            grand_tds += tds_amount
            row += 1

        row += 1
        sheet.write(row, 2, "Grand Total", header_format)
        sheet.write(row, 3, grand_tds, total_format)
