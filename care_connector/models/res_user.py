from odoo import fields, models


class ResUsers(models.Model):
    """Inheriting res.users"""

    _inherit = "res.users"

    x_care_id = fields.Char(string="Care User ID")
