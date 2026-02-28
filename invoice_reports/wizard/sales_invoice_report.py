from odoo import models, fields
from datetime import date
import io
import xlsxwriter
import base64

class SalesInvoiceExcelWizard(models.TransientModel):
    _name = 'sales.invoice.excel.wizard'
    _description = 'Sales Invoice Excel Report Wizard'

    date_from = fields.Date(
        string="Date From",
        required=True,
        default=lambda self: date.today().replace(day=1)
    )
    date_to = fields.Date(
        string="Date To",
        required=True,
        default=lambda self: date.today()
    )

    section_type = fields.Selection([
        ('sales', 'Sales Invoice'),
        ('sales_return', 'Sales Return'),
    ], string="Section", default='sales', required=True)

    def action_print_excel(self):
        """Generate Excel report for sales invoices or sales returns with dynamic tax columns"""
        move_type = 'out_invoice' if self.section_type == 'sales' else 'out_refund'

        invoice_model = self.env['account.move']
        invoices = invoice_model.search([
            ('move_type', '=', move_type),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('state', '=', 'posted'),
        ])

        all_taxes = set()
        for inv in invoices:
            for line in inv.invoice_line_ids:
                for tax in line.tax_ids:
                    all_taxes.add(tax.name)

        all_taxes = sorted(all_taxes) 

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Sales Invoice Report')

        sheet.set_column(0, 5 + len(all_taxes), 20)

        header = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center'})
        text = workbook.add_format({'border': 1})
        title_format = workbook.add_format({
            'bold': True, 'font_size': 14,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#B7DEE8'
        })

        title_text = 'SALES INVOICE REPORT' if self.section_type == 'sales' else 'SALES RETURN REPORT'
        sheet.merge_range(0, 0, 0, 5 + len(all_taxes), title_text, title_format)

        base_headers = [
            'Bill No',
            'Bill Date',
            'Invoice Value',
            'Place of Supply',
            'Party',
            'Taxable Value',
        ]
        headers = base_headers + list(all_taxes)

        for col, title in enumerate(headers):
            sheet.write(2, col, title, header)

        row = 3
        for inv in invoices:
            tax_amounts = {tax_name: 0.0 for tax_name in all_taxes}

            for line in inv.invoice_line_ids:
                taxes_data = line.tax_ids.compute_all(
                    line.price_unit,
                    inv.currency_id,
                    line.quantity,
                    product=line.product_id,
                    partner=inv.partner_id
                )
                for tax_detail in taxes_data.get('taxes', []):
                    tax_name = tax_detail['name']
                    tax_amount = tax_detail['amount']
                    if tax_name in tax_amounts:
                        tax_amounts[tax_name] += tax_amount

            place_of_supply = ''
            if inv.partner_id.state_id:
                place_of_supply = f"{inv.partner_id.state_id.code} - {inv.partner_id.state_id.name}"

            sheet.write(row, 0, inv.name or '', text)
            sheet.write(row, 1, str(inv.invoice_date or ''), text)
            sheet.write(row, 2, round(inv.amount_total, 2), text)
            sheet.write(row, 3, place_of_supply, text)
            sheet.write(row, 4, inv.partner_id.name or '', text)
            sheet.write(row, 5, round(inv.amount_untaxed, 2), text)

            for i, tax_name in enumerate(all_taxes, start=6):
                sheet.write(row, i, round(tax_amounts.get(tax_name, 0.0), 2), text)

            row += 1

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        section_label = "Sales" if self.section_type == 'sales' else "Sales_Return"
        file_name = f'{section_label}_Invoice_Report_{self.date_from}_{self.date_to}.xlsx'

        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'res_model': 'sales.invoice.excel.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
