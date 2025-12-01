from odoo import models , fields , api

from odoo import models, fields

class AccountAccountInherit(models.Model):
    _inherit = 'account.account'

    bank_cash_type = fields.Selection([
        ('bank', 'Bank'),
        ('cash', 'Cash'),
    ], string="Bank/Cash Type")

