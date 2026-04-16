from odoo import fields, models, api
from odoo.exceptions import ValidationError


class PartnerPaymentMethodRule(models.Model):
    _name = "partner.payment.method.rule"
    _description = "Partner Allowed Payment Method Rule"
    _order = "date_from desc, id desc"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="cascade",
        index=True,
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Payment Method",
        required=True,
        ondelete="cascade",
    )
    restricted_journal_id = fields.Many2one(
        "account.journal",
        string="Restricted Journal",
        compute="_compute_restricted_journal_id",
    )
    date_from = fields.Date(
        string="Valid From",
        required=True,
        default=fields.Date.today,
    )
    date_to = fields.Date(
        string="Valid To",
        required=True,
        default=fields.Date.today,
    )

    @api.depends_context("uid")
    def _compute_restricted_journal_id(self):
        icp = self.env["ir.config_parameter"].sudo()
        journal_id = icp.get_param(
            "care_connector.care_credit_journal_id", default=False
        )
        journal_id = int(journal_id) if journal_id else False
        for rule in self:
            rule.restricted_journal_id = journal_id

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rule in self:
            if rule.date_from > rule.date_to:
                raise ValidationError("'Valid From' must be on or before 'Valid To'.")

    def is_valid_on(self, date):
        """Check if this rule is valid on the given date."""
        self.ensure_one()
        return self.date_from <= date <= self.date_to
