# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = "account.move"

    insurance_tag = fields.Char(
        string="Insurance Tag",
        store=True,
        copy=False,
        help="Tag to identify invoices for insurance claims",
    )
    is_insurance = fields.Boolean(
        string="Is Insurance",
        compute="_compute_is_insurance",
        inverse="_inverse_is_insurance",
        store=True,
        help="Check this to mark as an insurance invoice",
    )
    insurance_claim_id = fields.Many2one(
        "insurance.claim",
        string="Insurance Claim",
        readonly=True,
        copy=False,
    )
    insurance_company_id = fields.Many2one(
        "insurance.company",
        string="Insurance Company",
        copy=False,
        help="Insurance company associated with this invoice",
    )
    doctor = fields.Char(
        string="Doctor",
        copy=False,
    )
    room_number = fields.Char(
        string="Room No",
        copy=False,
    )
    admission_date = fields.Datetime(
        string="Admission Date",
        copy=False,
    )
    discharge_date = fields.Datetime(
        string="Discharge Date",
        copy=False,
    )
    x_account = fields.Char(
        string="Account",
        copy=False,
        help="Account identifier from Care",
    )
    ip_bill_no = fields.Char(
        string="IP Bill Number",
        copy=False,
        help="IP Bill Number from Care",
    )

    @api.depends("insurance_tag")
    def _compute_is_insurance(self):
        """Check if this invoice is tagged for insurance."""
        # Use same parameter as old module for API compatibility
        insurance_tag = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("res.config.settings.insurance_tag_setting", default="")
        )
        for move in self:
            move.is_insurance = bool(
                move.insurance_tag and move.insurance_tag == insurance_tag
            )

    def _inverse_is_insurance(self):
        """Set or clear insurance_tag based on is_insurance checkbox."""
        insurance_tag = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("res.config.settings.insurance_tag_setting", default="")
        )
        for move in self:
            if move.is_insurance:
                move.insurance_tag = insurance_tag
            else:
                move.insurance_tag = False


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    insurance_tag = fields.Char(
        string="Insurance Tag",
        related="move_id.insurance_tag",
        store=True,
        readonly=True,
    )
