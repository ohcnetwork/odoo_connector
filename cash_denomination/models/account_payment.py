from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    cash_session_id = fields.Many2one(
        'cash.session',
        string='Cash Session',
        index=True,
        help='Cash session this payment belongs to'
    )
