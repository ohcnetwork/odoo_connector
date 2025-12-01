from odoo import models, fields
from datetime import date
from odoo.exceptions import UserError
import io
import base64
import xlsxwriter

class TrialBalanceExcelWizard(models.TransientModel):
    _name = 'trial.balance.excel.wizard'
    _description = 'Trial Balance Excel Report Wizard'

    date_from = fields.Date(string="Date From", required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string="Date To", required=True, default=lambda self: date.today())

    def action_export_excel(self):
        if self.date_from > self.date_to:
            raise UserError("Start date cannot be after end date!")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Trial Balance")

        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#D9EAD3', 'border': 1, 'align': 'center'
        })
        bold_format = workbook.add_format({'bold': True, 'border': 1})
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        number_format = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#F9CB9C', 'border': 1, 'num_format': '#,##0.00'})

        sheet.merge_range('A1:E1', 'Trial Balance Report', workbook.add_format({
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

        account_move_line_model = self.env['account.move.line']
        move_lines = account_move_line_model.search(move_line_domain)

        if not move_lines:
            raise UserError("No transactions found for the selected period.")

        accounts = {}
        for line in move_lines:
            accounts.setdefault(line.account_id, []).append(line)

        sheet.write(row, 0, "Account Code", header_format)
        sheet.write(row, 1, "Account Name", header_format)
        sheet.write(row, 2, "Debit", header_format)
        sheet.write(row, 3, "Credit", header_format)
        sheet.write(row, 4, "Balance", header_format)
        row += 1

        total_debit = total_credit = total_balance = 0.0

        for account, lines in accounts.items():
            acc_debit = sum(l.debit for l in lines)
            acc_credit = sum(l.credit for l in lines)
            balance = acc_debit - acc_credit

            sheet.write(row, 0, account.code or '', text_format)
            sheet.write(row, 1, account.name or '', text_format)
            sheet.write_number(row, 2, acc_debit, number_format)
            sheet.write_number(row, 3, acc_credit, number_format)
            sheet.write_number(row, 4, balance, number_format)
            row += 1

            total_debit += acc_debit
            total_credit += acc_credit
            total_balance += balance

        sheet.write(row, 1, "Total", bold_format)
        sheet.write_number(row, 2, total_debit, total_format)
        sheet.write_number(row, 3, total_credit, total_format)
        sheet.write_number(row, 4, total_balance, total_format)

        sheet.set_column('A:A', 22)
        sheet.set_column('B:B', 40)
        sheet.set_column('C:E', 15)

        workbook.close()

        file_data = base64.b64encode(output.getvalue())
        output.close()

        file_name = f"Trial_Balance_{self.date_from}_to_{self.date_to}.xlsx"

        export_id = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'res_model': 'trial.balance.excel.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{export_id.id}?download=true",
            'target': 'new',
        }
