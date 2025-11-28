from odoo import models, fields
from datetime import date
import io
import xlsxwriter
import base64


class PartnerAgedExcelWizard(models.TransientModel):
    _name = 'partner.aged.excel.wizard'
    _description = 'Partner Aged Report Excel Wizard'

    date_from = fields.Date(
        string="Start Date",
        required=True,
        default=lambda self: date.today().replace(day=1)
    )
    date_to = fields.Date(
        string="At Date",
        required=True,
        default=lambda self: date.today()
    )

    partners_ids = fields.Many2many(
    'res.partner',
    string="Partners"
    )

    report_type = fields.Selection([
        ('receivable', 'Aged Receivable'),
        ('payable', 'Aged Payable'),
        ('both', 'Both Receivable & Payable'),
    ], string="Report Type", default='receivable', required=True)

    def action_print_excel(self):

        account_move_model = self.env['account.move']
        move_domain = [
            ('state', '=', 'posted'),
            ('amount_residual', '!=', 0),
        ]

        if self.report_type == 'receivable':
            move_domain.append(('move_type', 'in', ['out_invoice', 'out_refund']))
        elif self.report_type == 'payable':
            move_domain.append(('move_type', 'in', ['in_invoice', 'in_refund']))
        else:
            move_domain.append(('move_type', 'in', [
                'out_invoice', 'out_refund',
                'in_invoice', 'in_refund'
            ]))

        if self.partners_ids:
            move_domain.append(('partner_id', 'in', self.partners_ids.ids))
            
        invoices = account_move_model.search(move_domain)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Partner Aged Report')

        sheet.set_column(0, 10, 20)

        header = workbook.add_format({
            'bold': True, 'bg_color': '#D3D3D3',
            'border': 1, 'align': 'center'
        })
        text = workbook.add_format({'border': 1})
        title_format = workbook.add_format({
            'bold': True, 'font_size': 14,
            'align': 'center', 'bg_color': '#B7DEE8'
        })

        sheet.merge_range(0, 0, 0, 9, "PARTNER AGED REPORT", title_format)

        headers = [
            "Partner",
            "Invoice No",
            "Invoice Date",
            "At Date",
            "1 - 30",
            "30 - 60",
            "60 - 90",
            "90 - 120",
            "Older",
            "Total",
        ]

        for col, title in enumerate(headers):
            sheet.write(2, col, title, header)

        def get_bucket(inv):
            today = self.date_to
            due = inv.invoice_date_due

            if not due:
                return "older"

            days = (today - due).days

            if days <= 0:
                return "at_date"

            if 1 <= days <= 30:
                return "1_30"
            elif 31 <= days <= 60:
                return "30_60"
            elif 61 <= days <= 90:
                return "60_90"
            elif 91 <= days <= 120:
                return "90_120"
            else:
                return "older"

        row = 3

        for inv in invoices:

            bucket_vals = {
                'at_date': 0,
                '1_30': 0,
                '30_60': 0,
                '60_90': 0,
                '90_120': 0,
                'older': 0,
            }

            residual = inv.amount_residual
            bucket = get_bucket(inv)
            bucket_vals[bucket] = residual

            sheet.write(row, 0, inv.partner_id.name or "", text)
            sheet.write(row, 1, inv.name or "", text)
            sheet.write(row, 2, str(inv.invoice_date or ""), text)
            sheet.write(row, 3, bucket_vals['at_date'], text)
            sheet.write(row, 4, bucket_vals['1_30'], text)
            sheet.write(row, 5, bucket_vals['30_60'], text)
            sheet.write(row, 6, bucket_vals['60_90'], text)
            sheet.write(row, 7, bucket_vals['90_120'], text)
            sheet.write(row, 8, bucket_vals['older'], text)
            sheet.write(row, 9, residual, text)

            row += 1

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        file_name = f'Partner_Aged_Report_{self.date_from}_{self.date_to}.xlsx'

        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'res_model': 'partner.aged.excel.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
