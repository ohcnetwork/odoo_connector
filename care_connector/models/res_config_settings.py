# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    invoice_cash_rounding_id = fields.Many2one(
        "account.cash.rounding",
        string="Invoice Rounding",
        help="Default cash rounding method to apply on invoices created via Care connector",
    )

    care_credit_journal_id = fields.Many2one(
        "account.journal",
        string="Restricted Payment Journal",
        help="Journal that requires per-partner payment method validation. "
        "Payment method lines from this journal will be available as "
        "allowed methods on partners.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        rounding_id = icp.get_param("care_connector.invoice_cash_rounding_id", default=False)
        res["invoice_cash_rounding_id"] = int(rounding_id) if rounding_id else False
        credit_journal_id = icp.get_param("care_connector.care_credit_journal_id", default=False)
        res["care_credit_journal_id"] = int(credit_journal_id) if credit_journal_id else False
        return res

    def set_values(self):
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(
            "care_connector.invoice_cash_rounding_id",
            self.invoice_cash_rounding_id.id if self.invoice_cash_rounding_id else False,
        )
        icp.set_param(
            "care_connector.care_credit_journal_id",
            self.care_credit_journal_id.id if self.care_credit_journal_id else False,
        )

