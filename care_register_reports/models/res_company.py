from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    care_stock_sales_account_ids = fields.Many2many(
        "account.account",
        "care_register_company_stock_sales_account_rel",
        "company_id",
        "account_id",
        string="Stock Sales Accounts",
        help="Income accounts that stock sales post to. The sales registers count only lines on these accounts by default.",
    )
