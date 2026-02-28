from odoo import models, fields
from odoo.exceptions import UserError
from datetime import date
import io
import base64
import xlsxwriter

class BankReconciliationWizard(models.TransientModel):
    _name = 'bank.reconciliation.wizard'
    _description = 'Bank Reconciliation Wizard'

    date_from = fields.Date(string="Date From", required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string="Date To", required=True, default=lambda self: date.today())
    account_id = fields.Many2one('account.account', string='Bank', required=True,domain=[('account_type', '=', 'asset_cash')])
    options = fields.Selection([
        ('reconciled', 'Reconciled'),
        ('unreconciled', 'Unreconciled'),
        ('both', 'Both')
    ], string='Reconcile Options', tracking=True)



    def action_reconcile_export_excel(self):
        if self.date_from > self.date_to:
            raise UserError("Start date cannot be after end date!")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Bank Reconciliation Report")

        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'bg_color': '#B6D7A8'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1, 'align': 'center'})
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        number_format = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '₹ 0.00'})

        sheet.merge_range('A1:H1', 'Bank Reconciliation Report', title_format)
        sheet.write('A2', f"From: {self.date_from}", workbook.add_format({'bold': True}))
        sheet.write('B2', f"To: {self.date_to}", workbook.add_format({'bold': True}))

        row = 4
        headers = ['Date', 'Entry Name', 'Partner', 'Label', 'Debit', 'Credit','Balance', 'Reconcile Date']
        for col, header in enumerate(headers):
            sheet.write(row, col, header, header_format)

        move_line_domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('account_id', '=', self.account_id.id),
            ('move_id.state', '=', 'posted'),
        ]

        if self.options == 'reconciled':
            move_line_domain.append(('reconcile_date', '!=', False))

        elif self.options == 'unreconciled':
            move_line_domain.append(('reconcile_date', '=', False))


        move_lines = self.env['account.move.line'].search(move_line_domain)
        if not move_lines:
            raise UserError("No transactions found for the selected period.")

        row += 1
        total_debit = total_credit = total_balance = 0
        for line in move_lines:
            sheet.write(row, 0, str(line.date), text_format)
            sheet.write(row, 1, line.move_id.name, text_format)
            sheet.write(row, 2, line.partner_id.name or '', text_format)
            sheet.write(row, 3, line.name or '', text_format)
            sheet.write(row, 4, line.debit, number_format)
            sheet.write(row, 5, line.credit, number_format)
            sheet.write(row, 6, line.balance, number_format)
            sheet.write(row, 7, str(line.reconcile_date or ''), text_format)

            total_debit += line.debit
            total_credit += line.credit
            total_balance += line.balance
            row += 1

        # Totals
        row += 1
        sheet.write(row, 3, "TOTAL", header_format)
        sheet.write(row, 4, total_debit, number_format)
        sheet.write(row, 5, total_credit, number_format)
        sheet.write(row, 6, total_balance, number_format)

        # Download
        workbook.close()
        file_data = base64.b64encode(output.getvalue())
        output.close()

        file_name = f"Bank_Reconciliation_Report_{self.date_from}_to_{self.date_to}.xlsx"

        export_id = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'res_model': 'bank.reconciliation.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{export_id.id}?download=true",
            'target': 'new',
        }