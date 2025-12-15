from odoo import models, api
from odoo.exceptions import UserError

class CustomerInsurance(models.Model):
    _inherit = 'customer.insurance'

    def print_insurance_voucher(self):
        for record in self:
            lines = record.invoice_line_ids
            if not lines:
                raise UserError("Cannot print Insurance Voucher because there are no invoice lines.")

            lines_show_in_report = record.invoice_line_ids.filtered(lambda l: l.show_in_report)
            if not lines_show_in_report:
                raise UserError("Cannot print Insurance Voucher because Your are Not Enable the Show in Inshurance Check Box")


        return self.env.ref('account_insurance_voucher.action_report_insurance_bill').report_action(self)