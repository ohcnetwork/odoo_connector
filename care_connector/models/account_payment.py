from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    x_care_id = fields.Char(string='Care ID')
    cancel_status = fields.Boolean(string="Cancelled", default=False)
    location = fields.Many2one('bill.counter', string='Location')
    cashier = fields.Many2one('res.users', string='Cashier')
    cash_session_id = fields.Many2one(
        'cash.session',
        string='Cash Session',
        index=True,
        help='Cash session this payment belongs to'
    )