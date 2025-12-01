from odoo import models, fields
from datetime import date
import io
import xlsxwriter
import base64
from collections import defaultdict

class InvoiceHSNExcelWizard(models.TransientModel):
    _name = 'invoice.hsn.excel.wizard'
    _description = 'Invoice HSN Excel Report Wizard'

    date_from = fields.Date(string="Date From", required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string="Date To", required=True, default=lambda self: date.today())

    def action_print_excel(self):
        invoice_model = self.env['account.move']
        invoices = invoice_model.search([
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('state', '=', 'posted'),
        ])

        invoices = invoices.filtered(lambda inv: any(line.product_id.l10n_in_hsn_code for line in inv.invoice_line_ids))

        all_taxes = set()
        for inv in invoices:
            for line in inv.invoice_line_ids:
                for tax in line.tax_ids:
                    all_taxes.add(tax.name)

        all_taxes = sorted(list(all_taxes))

        data = defaultdict(lambda: {
            'description': '',
            'uom': '',
            'qty': 0,
            'total_value': 0,
            'taxable_value': 0,
            'taxes': {tax: 0 for tax in all_taxes}
        })

        for inv in invoices:
            for line in inv.invoice_line_ids.filtered(lambda l: l.product_id.l10n_in_hsn_code):
                hsn = line.product_id.l10n_in_hsn_code or ''
                key = (hsn, line.product_id.display_name)

                tax_data = line.tax_ids.compute_all(
                    line.price_unit,
                    inv.currency_id,
                    line.quantity,
                    product=line.product_id,
                    partner=inv.partner_id
                )

                data[key]['description'] = line.product_id.display_name or ''
                data[key]['uom'] = line.product_uom_id.name or ''
                data[key]['qty'] += line.quantity
                data[key]['total_value'] += line.price_total
                data[key]['taxable_value'] += line.price_subtotal

                for t in tax_data.get('taxes', []):
                    tax_name = t['name']
                    if tax_name in data[key]['taxes']:
                        data[key]['taxes'][tax_name] += t['amount']

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('HSN Report')

        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center'})
        text_fmt = workbook.add_format({'border': 1})
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#B7DEE8'
        })

        sheet.merge_range('A1:K1', 'HSN WISE TAX REPORT', title_fmt)

        base_headers = [
            'HSN', 'Description', 'UQC', 'Total Quantity',
            'Total Value', 'Taxable Value'
        ]
        headers = base_headers + all_taxes

        for col, title in enumerate(headers):
            sheet.write(2, col, title, header_fmt)
            sheet.set_column(col, col, 18)

        row = 3
        for (hsn, desc), vals in data.items():
            sheet.write(row, 0, hsn, text_fmt)
            sheet.write(row, 1, desc, text_fmt)
            sheet.write(row, 2, vals['uom'], text_fmt)
            sheet.write(row, 3, vals['qty'], text_fmt)
            sheet.write(row, 4, round(vals['total_value'], 2), text_fmt)
            sheet.write(row, 5, round(vals['taxable_value'], 2), text_fmt)

            col = 6
            for tax_name in all_taxes:
                tax_amt = vals['taxes'].get(tax_name, 0)
                sheet.write(row, col, round(tax_amt, 2) if tax_amt else 0, text_fmt)
                col += 1

            row += 1

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        attachment = self.env['ir.attachment'].create({
            'name': f'HSN_Tax_Report_{self.date_from}_{self.date_to}.xlsx',
            'type': 'binary',
            'datas': file_data,
            'res_model': 'invoice.hsn.excel.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
