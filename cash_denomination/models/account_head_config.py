from odoo import models, fields


class AccountHeadConfig(models.Model):
    _name = "account.head.config"
    _description = "Account Head Configuration for Cash Denomination"

    name = fields.Char(
        string="Configuration Name",
        default="Cash Denomination Config",
        required=True
    )
    debit_account_id = fields.Many2one(
        "account.account",
        string="Counter Account (Debit)",
        required=True,
        domain=[('deprecated', '=', False)],
        help="This account will be debited when the counter sends cash (e.g., Main Cash Account)."
    )
    credit_account_id = fields.Many2one(
        "account.account",
        string="Counter Account (Credit)",
        required=True,
        domain=[('deprecated', '=', False)],
        help="This account will be credited when cash is received from counter (e.g., Counter Cash Account)."
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    _sql_constraints = [
        ('unique_company_config', 'UNIQUE(company_id)',
         'Only one cash denomination configuration is allowed per company!')
    ]
