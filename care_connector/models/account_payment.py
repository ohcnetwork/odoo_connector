from odoo import fields, models, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    x_care_id = fields.Char(string='Care ID')
    cancel_status = fields.Boolean(string="Cancelled", default=False)
    location = fields.Many2one('bill.counter', string='Location')
    cashier = fields.Many2one('res.users', string='Cashier')
    x_care_url = fields.Char(
        string="Care URL",
        compute="_compute_care_url",
        store=False,
    )

    @api.depends('x_care_id')
    def _compute_care_url(self):
        """Compute the Care URL based on care_id."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('care.base_url', default='')
        for record in self:
            if record.x_care_id and base_url:
                # Placeholder URL pattern for payments
                record.x_care_url = f"{base_url}/payments/{record.x_care_id}"
            else:
                record.x_care_url = False
