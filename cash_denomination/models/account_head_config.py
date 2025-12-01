from odoo import models, fields

class AccountHeadConfig(models.Model):
    _name = "account.head.config"
    _description = "Account Head Configuration for Cash Transfer"

    debit_account_id = fields.Many2one(
        "account.account",
        string="Counter Account",
        required=True,
        help="This account will be used on the debit side when the counter sends cash."
    )

    credit_account_id = fields.Many2one(
        "account.account",
        string="Receiving Account",
        required=True,
        domain=[('deprecated', '=', False)],
        help="This account will be used on the credit side when a counter receives payment."
    )
