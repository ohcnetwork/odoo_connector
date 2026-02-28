from odoo import models, fields
from datetime import date
from odoo.exceptions import UserError
import io
import base64
import xlsxwriter

class GeneralLedgerExcelWizard(models.TransientModel):
    _name = 'general.ledger.excel.wizard'
    _description = 'General Ledger Excel Report Wizard'

    date_from = fields.Date(string="Date From", required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string="Date To", required=True, default=lambda self: date.today())

    def action_export_excel(self):
        if self.date_from > self.date_to:
            raise UserError("Start date cannot be after end date!")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("General Ledger")

        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#D9EAD3', 'border': 1, 'align': 'center'
        })
        bold_format = workbook.add_format({'bold': True, 'border': 1})
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        number_format = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#F9CB9C', 'border': 1, 'num_format': '#,##0.00'})

        sheet.merge_range('A1:H1', 'General Ledger Report', workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center', 'bg_color': '#B6D7A8'
        }))
        sheet.write('A2', f"From: {self.date_from}", bold_format)
        sheet.write('B2', f"To: {self.date_to}", bold_format)

        row = 4
        col = 0

        move_line_domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        account_move_lie_model = self.env['account.move.line']
        move_lines = account_move_lie_model.search(move_line_domain, order="account_id, date asc")

        if not move_lines:
            raise UserError("No transactions found for the selected period.")

        account_groups = {}
        for line in move_lines:
            account = line.account_id
            account_groups.setdefault(account, []).append(line)

        grand_total_debit = grand_total_credit = grand_total_balance = 0.0

        for account, lines in account_groups.items():
            sheet.write(row, 0, f"{account.code or ''} {account.name or ''}", bold_format)
            row += 1

            sheet.write(row, 0, "Date", header_format)
            sheet.write(row, 1, "Journal", header_format)
            sheet.write(row, 2, "Partner", header_format)
            sheet.write(row, 3, "Move", header_format)
            sheet.write(row, 4, "Label", header_format)
            sheet.write(row, 5, "Debit", header_format)
            sheet.write(row, 6, "Credit", header_format)
            sheet.write(row, 7, "Balance", header_format)
            row += 1

            total_debit = total_credit = total_balance = 0.0

            for line in lines:
                balance = line.debit - line.credit
                total_balance += balance
                total_debit += line.debit
                total_credit += line.credit

                sheet.write(row, 0, str(line.date or ''), text_format)
                sheet.write(row, 1, line.journal_id.code or '', text_format)
                sheet.write(row, 2, line.partner_id.name or '', text_format)
                sheet.write(row, 3, line.move_id.name or '', text_format)
                sheet.write(row, 4, line.name or '', text_format)
                sheet.write_number(row, 5, line.debit, number_format)
                sheet.write_number(row, 6, line.credit, number_format)
                sheet.write_number(row, 7, balance, number_format)
                row += 1

            sheet.write(row, 4, "Subtotal", bold_format)
            sheet.write_number(row, 5, total_debit, total_format)
            sheet.write_number(row, 6, total_credit, total_format)
            sheet.write_number(row, 7, total_balance, total_format)
            row += 2

            grand_total_debit += total_debit
            grand_total_credit += total_credit
            grand_total_balance += total_balance

        sheet.write(row, 4, "Grand Total", bold_format)
        sheet.write_number(row, 5, grand_total_debit, total_format)
        sheet.write_number(row, 6, grand_total_credit, total_format)
        sheet.write_number(row, 7, grand_total_balance, total_format)

        sheet.set_column('A:A', 20)  
        sheet.set_column('B:B', 15)  
        sheet.set_column('C:C', 30)   
        sheet.set_column('D:D', 30)   
        sheet.set_column('E:E', 45)   
        sheet.set_column('F:H', 15)   


        workbook.close()

        file_data = base64.b64encode(output.getvalue())
        output.close()

        file_name = f"General_Ledger_{self.date_from}_to_{self.date_to}.xlsx"

        export_id = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'res_model': 'general.ledger.excel.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{export_id.id}?download=true",
            'target': 'new',
        }
