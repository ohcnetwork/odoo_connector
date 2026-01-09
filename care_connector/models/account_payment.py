from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    x_care_id = fields.Char(string='Care ID')
    cancel_status = fields.Boolean(string="Cancelled", default=False)
    location = fields.Many2one('bill.counter', string='Location')
    cashier = fields.Many2one('res.users', string='Cashier')
    # Note: cash_session_id field is defined in cash_denomination module
    # to avoid circular dependency (cash.session model is defined there)