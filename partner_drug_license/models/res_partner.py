from odoo import fields, models


class ResPartner(models.Model):
    """Inheriting res.partner to add Drug License Number field"""
    _inherit = "res.partner"

    drug_license_number = fields.Char(string='Drug License Number')
