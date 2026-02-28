from odoo import fields, models


class ResPartner(models.Model):
    """Inheriting res.partner"""

    _inherit = "res.partner"

    x_care_id = fields.Char(string="Care Partner ID")
    x_care_id_type = fields.Selection(
        [("user", "User"), ("vendor", "Vendor")],
        string="Care ID Type",
        help="Indicates whether this Care ID belongs to a User or Vendor",
    )
