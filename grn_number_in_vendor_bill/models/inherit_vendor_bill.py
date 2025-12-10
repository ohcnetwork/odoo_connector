from odoo import models, fields, api
from datetime import date, datetime

class AccountMove(models.Model):
    _inherit = 'account.move'

    grn_number = fields.Integer(string='GRN No.', readonly=True, copy=False)

    def action_post(self):
        """Assign vendor bill number when the bill is confirmed (posted)"""
        for move in self:
            if move.move_type == 'in_invoice':

                params = self.env['ir.config_parameter'].sudo()

                enable_period = params.get_param('account.enable_vendor_period') == 'True'
                start_date = params.get_param('account.vendor_period_start_date')
                end_date = params.get_param('account.vendor_period_end_date')
                seq_num = int(params.get_param('account.number_sequence') or 1)

                if enable_period and start_date and end_date:

                    today = date.today()
                    start = fields.Date.from_string(start_date)
                    end = fields.Date.from_string(end_date)

                    if start <= today <= end:
                        move.grn_number = seq_num

                        params.set_param('account.number_sequence', seq_num + 1)

        return super(AccountMove, self).action_post()