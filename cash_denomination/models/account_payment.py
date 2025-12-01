from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_submitted = fields.Boolean(string="Submitted", default=False, readonly=True)