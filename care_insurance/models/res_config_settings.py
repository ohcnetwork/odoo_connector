# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Use same field name as old module for API compatibility
    insurance_tag_setting = fields.Char(
        string="Insurance Tag",
        help="Default tag to identify insurance invoices",
    )
    insurance_default_journal_id = fields.Many2one(
        "account.journal",
        string="Default Insurance Journal",
        help="Default journal for insurance claim journal entries",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        res["insurance_tag_setting"] = icp.get_param(
            "res.config.settings.insurance_tag_setting", default=""
        )
        journal_id = icp.get_param("care_insurance.default_journal_id", default=False)
        res["insurance_default_journal_id"] = int(journal_id) if journal_id else False
        return res

    def set_values(self):
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(
            "res.config.settings.insurance_tag_setting",
            self.insurance_tag_setting or "",
        )
        icp.set_param(
            "care_insurance.default_journal_id",
            self.insurance_default_journal_id.id
            if self.insurance_default_journal_id
            else False,
        )
