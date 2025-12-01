from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_vendor_period = fields.Boolean(string="Enable GRN Period")
    vendor_period_start_date = fields.Date(string="Start Date")
    vendor_period_end_date = fields.Date(string="End Date")
    number_sequence = fields.Integer(string="Bill Sequence Number", default=1)

    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('account.enable_vendor_period', self.enable_vendor_period)
        params.set_param('account.vendor_period_start_date', self.vendor_period_start_date or '')
        params.set_param('account.vendor_period_end_date', self.vendor_period_end_date or '')
        params.set_param('account.number_sequence', self.number_sequence or 1)

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            enable_vendor_period=params.get_param('account.enable_vendor_period') == 'True',
            vendor_period_start_date=params.get_param('account.vendor_period_start_date') or False,
            vendor_period_end_date=params.get_param('account.vendor_period_end_date') or False,
            number_sequence=int(params.get_param('account.number_sequence') or 1),
        )
        return res
