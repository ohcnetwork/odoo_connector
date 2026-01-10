from odoo import fields, models


class AccountDiscountGroup(models.Model):
    _name = "account.discount.group"
    _description = "Discount Group"

    name = fields.Char(string="Group Name", required=True)
    x_care_id = fields.Char(string="Care ID", readonly=True)
