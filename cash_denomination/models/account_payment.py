from odoo import fields, models, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_denomination = fields.Boolean(string="Denomination Registered", default=False)