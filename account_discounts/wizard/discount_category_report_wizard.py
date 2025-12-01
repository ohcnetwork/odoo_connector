
from odoo import models, fields
from odoo.exceptions import UserError
from datetime import date
import io
import base64
import xlsxwriter

class DiscountCategWizard(models.TransientModel):
    _name = 'discount.categ.wizard'
    _description = 'Discount Category Wizard'

    date_from = fields.Date(string="Date From", required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string="Date To", required=True, default=lambda self: date.today())

    def action_disc_export_excel(self):
        if self.date_from > self.date_to:
            raise UserError("Start date cannot be after end date!")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Discount Report")

        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'bg_color': '#B6D7A8'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1, 'align': 'center'})
        text_format = workbook.add_format({'border': 1, 'align': 'left'})
        number_format = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '$ #,##0.00'})

        sheet.merge_range('A1:H1', 'Discount Category Wise Report', title_format)
        sheet.write('A2', f"From: {self.date_from}", workbook.add_format({'bold': True}))
        sheet.write('B2', f"To: {self.date_to}", workbook.add_format({'bold': True}))

        move_line_domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('product_id.is_disc_item', '=', True)
        ]
        move_line_domain_rec = self.env['account.move.line']

        move_lines = move_line_domain_rec.search(move_line_domain, order="date asc, id asc")

        if not move_lines:
            raise UserError("No transactions found for the selected period.")

        disc_summary = {}
        for line in move_lines:
            product_disc = line.product_id.discount_group
            if product_disc.id not in disc_summary:
                disc_summary[product_disc.id] = {
                    'discount_name': product_disc.name,
                    'total_discount': 0,
                }

            disc_summary[product_disc.id]['total_discount'] += line.price_unit

        row = 4
        sheet.write_row(row, 0, ["Discount", "Total Discount"], header_format)
        row += 1

        # Write Data
        for product_id, data in disc_summary.items():
            sheet.write(row, 0, data['discount_name'], text_format)
            sheet.write(row, 1, data['total_discount'], number_format)
            row += 1
        #

        workbook.close()

        file_data = base64.b64encode(output.getvalue())
        output.close()

        file_name = f"Discount_Report_{self.date_from}_to_{self.date_to}.xlsx"

        export_id = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'res_model': 'discount.categ.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{export_id.id}?download=true",
            'target': 'new',
        }
