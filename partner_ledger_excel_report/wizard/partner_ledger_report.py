
from odoo import models, fields
from odoo.exceptions import UserError
from datetime import date
import io
import base64
import xlsxwriter

class PartnerLedgerExcelWizard(models.TransientModel):
    _name = 'partner.ledger.excel.wizard'
    _description = 'Partner Ledger Excel Report Wizard'

    date_from = fields.Date(string="Date From", required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string="Date To", required=True, default=lambda self: date.today())
    partner_ids = fields.Many2many(
        'res.partner',
        string="Partners",
        help="Select one or more partners. Leave empty to include all partners."
    )

    def action_export_excel(self):
        if self.date_from > self.date_to:
            raise UserError("Start date cannot be after end date!")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Partner Ledger")

        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'bg_color': '#B6D7A8'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1, 'align': 'center'})
        partner_format = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#FCE5CD'})
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        number_format = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '$ #,##0.00'})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#F9CB9C', 'border': 1, 'num_format': '$ #,##0.00'})

        sheet.merge_range('A1:H1', 'Partner Ledger Report', title_format)
        sheet.write('A2', f"From: {self.date_from}", workbook.add_format({'bold': True}))
        sheet.write('B2', f"To: {self.date_to}", workbook.add_format({'bold': True}))

        move_line_domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('partner_id', '!=', False),
        ]
        move_line_domain_rec = self.env['account.move.line']

        if self.partner_ids:
            move_line_domain.append(('partner_id', 'in', self.partner_ids.ids))

        move_lines = move_line_domain_rec.search(move_line_domain, order="partner_id, date asc, id asc")

        if not move_lines:
            raise UserError("No transactions found for the selected period.")

        partner_groups = {}
        for line in move_lines:
            partner = line.partner_id
            partner_groups.setdefault(partner, []).append(line)

        row = 4
        grand_total_debit = grand_total_credit = 0.0

        for partner, lines in partner_groups.items():
            total_debit = sum(l.debit for l in lines)
            total_credit = sum(l.credit for l in lines)

            sheet.write(row, 0, f"- {partner.name or 'Unknown Partner'}", partner_format)
            sheet.write_number(row, 5, total_debit, total_format)
            sheet.write_number(row, 6, total_credit, total_format)
            sheet.write_number(row, 7, total_debit - total_credit, total_format)
            row += 1

            headers = ["Date", "Due Date", "Journal", "Account", "Reference", "Debit", "Credit", "Balance"]
            for col, h in enumerate(headers):
                sheet.write(row, col, h, header_format)
            row += 1

            running_balance = 0.0
            for line in lines:
                running_balance += (line.debit - line.credit)

                sheet.write(row, 0, str(line.date or ''), text_format)
                sheet.write(row, 1, str(line.move_id.invoice_date_due or ''), text_format)
                sheet.write(row, 2, line.journal_id.code or '', text_format)
                sheet.write(row, 3, line.account_id.display_name or '', text_format)
                sheet.write(row, 4, line.move_id.name or '', text_format)
                sheet.write_number(row, 5, line.debit, number_format)
                sheet.write_number(row, 6, line.credit, number_format)
                sheet.write_number(row, 7, running_balance, number_format)
                row += 1

            row += 1  

            grand_total_debit += total_debit
            grand_total_credit += total_credit

        sheet.write(row, 4, "Grand Total", workbook.add_format({'bold': True, 'align': 'right'}))
        sheet.write_number(row, 5, grand_total_debit, total_format)
        sheet.write_number(row, 6, grand_total_credit, total_format)
        sheet.write_number(row, 7, grand_total_debit - grand_total_credit, total_format)

        sheet.set_column('A:A', 20)   
        sheet.set_column('B:B', 20)   
        sheet.set_column('C:C', 12)    
        sheet.set_column('D:D', 40)   
        sheet.set_column('E:E', 25)   
        sheet.set_column('F:F', 20)   
        sheet.set_column('G:G', 20)   
        sheet.set_column('H:H', 20)   

        workbook.close()

        file_data = base64.b64encode(output.getvalue())
        output.close()

        file_name = f"Partner_Ledger_{self.date_from}_to_{self.date_to}.xlsx"

        export_id = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'res_model': 'partner.ledger.excel.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{export_id.id}?download=true",
            'target': 'new',
        }
