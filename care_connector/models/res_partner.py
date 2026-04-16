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
    x_care_credit_journal_id = fields.Many2one(
        "account.journal",
        string="Restricted Journal",
        compute="_compute_care_credit_journal_id",
        help="Technical field: journal from Care Connector settings, "
        "used to filter allowed payment method lines.",
    )

    @api.depends_context("uid")
    def _compute_care_credit_journal_id(self):
        icp = self.env["ir.config_parameter"].sudo()
        journal_id = icp.get_param("care_connector.care_credit_journal_id", default=False)
        journal_id = int(journal_id) if journal_id else False
        for partner in self:
            partner.x_care_credit_journal_id = journal_id


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