# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class InsuranceCompany(models.Model):
    _name = "insurance.company"
    _description = "Insurance Company"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        string="Insurance Company Name",
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string="Code",
        tracking=True,
    )
    description = fields.Text(string="Description")
    account_id = fields.Many2one(
        "account.account",
        string="Receivable Account",
        help="Account used for insurance receivables when claims are approved",
        tracking=True,
        check_company=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    claim_count = fields.Integer(
        string="Claims",
        compute="_compute_claim_count",
    )

    @api.depends()
    def _compute_claim_count(self):
        claim_data = self.env["insurance.claim"].read_group(
            domain=[("insurance_company_id", "in", self.ids)],
            fields=["insurance_company_id"],
            groupby=["insurance_company_id"],
        )
        mapped_data = {
            data["insurance_company_id"][0]: data["insurance_company_id_count"]
            for data in claim_data
        }
        for company in self:
            company.claim_count = mapped_data.get(company.id, 0)

    def action_view_claims(self):
        self.ensure_one()
        return {
            "name": _("Insurance Claims"),
            "type": "ir.actions.act_window",
            "res_model": "insurance.claim",
            "view_mode": "list,form",
            "domain": [("insurance_company_id", "=", self.id)],
            "context": {"default_insurance_company_id": self.id},
        }
