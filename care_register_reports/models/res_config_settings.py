from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    care_stock_sales_account_ids = fields.Many2many(
        related="company_id.care_stock_sales_account_ids",
        readonly=False,
    )
