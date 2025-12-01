from odoo import models, fields
from datetime import date
import io
import xlsxwriter
import base64


class VendorBillExcelWizard(models.TransientModel):
    _name = 'vendor.bill.excel.wizard'
    _description = 'Vendor Bill Excel Report Wizard'

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
        ('purchase', 'Purchase Bills'),
        ('purchase_return', 'Purchase Returns'),
    ], string="Section", default='purchase', required=True)

    def action_print_excel(self):
        move_type = 'in_invoice' if self.section_type == 'purchase' else 'in_refund'
        bill_model = self.env['account.move']
        bills = bill_model.search([
            ('move_type', '=', move_type),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('state', '=', 'posted'),
        ])

        all_tax_names = set()
        for bill in bills:
            for line in bill.invoice_line_ids:
                for tax in line.tax_ids:
                    all_tax_names.add(tax.name)
        all_tax_names = sorted(all_tax_names)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Vendor Bill Report')

        header = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center'})
        text = workbook.add_format({'border': 1})
        num_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        title_format = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center',
            'valign': 'vcenter', 'bg_color': '#B7DEE8'
        })

        title_text = 'VENDOR BILL REPORT' if self.section_type == 'purchase' else 'PURCHASE RETURN REPORT'
        total_columns = 8 + len(all_tax_names)
        last_col_letter = chr(65 + total_columns - 1)
        sheet.merge_range(f'A1:{last_col_letter}1', title_text, title_format)

        headers = [
            'Bill No', 'Bill Date', 'Payment Date', 'Payment No', 'Invoice Value',
            'Place of Supply', 'GSTIN', 'Party', 'Address', 'Taxable Value'
        ] + all_tax_names

        for col, title in enumerate(headers):
            sheet.write(2, col, title, header)
            sheet.set_column(col, col, 18)

        row = 3
        for bill in bills:
            total_taxable = 0.0
            total_invoice_value = bill.amount_total
            tax_summary = {tax_name: 0.0 for tax_name in all_tax_names}

            for line in bill.invoice_line_ids:
                tax_data = line.tax_ids.compute_all(
                    line.price_unit,
                    bill.currency_id,
                    line.quantity,
                    product=line.product_id,
                    partner=bill.partner_id
                )
                total_taxable += tax_data.get('total_excluded', 0.0)
                for t in tax_data.get('taxes', []):
                    tax_summary[t['name']] = tax_summary.get(t['name'], 0.0) + t['amount']

            payment_date = ''
            payment_number = ''
            if bill.payment_state == 'paid':
                payment_model = self.env['account.payment']
                payments = payment_model.search([
                    ('move_id.line_ids.matched_debit_ids.debit_move_id.move_id', '=', bill.id)
                ]) | payment_model.search([
                    ('move_id.line_ids.matched_credit_ids.credit_move_id.move_id', '=', bill.id)
                ])
                if payments:
                    payment_date = ', '.join([str(p.date) for p in payments])
                    payment_number = ', '.join([p.name for p in payments])

            place_supply = ''
            if bill.partner_id.state_id:
                place_supply = f"{bill.partner_id.state_id.code or ''} - {bill.partner_id.state_id.name or ''}"

            gstin = bill.partner_id.vat or ''

            address = ', '.join(filter(None, [
                bill.partner_id.street or '',
                bill.partner_id.city or '',
                bill.partner_id.state_id.name or '',
                bill.partner_id.zip or ''
            ]))

            sheet.write(row, 0, bill.name or '', text)
            sheet.write(row, 1, str(bill.invoice_date or ''), text)
            sheet.write(row, 2, payment_date or '', text)
            sheet.write(row, 3, payment_number or '', text)
            sheet.write(row, 4, total_invoice_value, num_format)
            sheet.write(row, 5, place_supply, text)
            sheet.write(row, 6, gstin, text)
            sheet.write(row, 7, bill.partner_id.name or '', text)
            sheet.write(row, 8, address, text)
            sheet.write(row, 9, total_taxable, num_format)

            for i, tax_name in enumerate(all_tax_names, start=10):
                sheet.write(row, i, tax_summary.get(tax_name, 0.0), num_format)

            row += 1

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        section_label = "Purchase_Bills" if self.section_type == 'purchase' else "Purchase_Returns"
        file_name = f'{section_label}_Report_{self.date_from}_{self.date_to}.xlsx'

        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'res_model': 'vendor.bill.excel.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
