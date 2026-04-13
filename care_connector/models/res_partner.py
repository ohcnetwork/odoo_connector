from odoo import fields, models, api


class ResPartner(models.Model):
    """Inheriting res.partner"""

    _inherit = "res.partner"

    x_care_id = fields.Char(string="Care Partner ID")
    x_care_id_type = fields.Selection(
        [("user", "User"), ("vendor", "Vendor")],
        string="Care ID Type",
        help="Indicates whether this Care ID belongs to a User or Vendor",
    )
    x_gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        string="Gender",
    )
    x_birthdate = fields.Date(string="Date of Birth")
    x_age = fields.Integer(
        string="Age",
        compute="_compute_age",
        store=True,
    )
    x_allowed_payment_method_line_ids = fields.One2many(
        "partner.payment.method.rule",
        "partner_id",
        string="Allowed Payment Methods",
    )

    @api.depends("x_birthdate")
    def _compute_age(self):
        today = fields.Date.today()
        for partner in self:
            if partner.x_birthdate:
                birthdate = partner.x_birthdate
                partner.x_age = today.year - birthdate.year - (
                    (today.month, today.day) < (birthdate.month, birthdate.day)
                )
            else:
                partner.x_age = 0