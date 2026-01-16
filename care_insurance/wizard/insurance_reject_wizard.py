# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class InsuranceRejectWizard(models.TransientModel):
    _name = "insurance.reject.wizard"
    _description = "Insurance Claim Rejection Wizard"

    claim_id = fields.Many2one(
        "insurance.claim",
        string="Insurance Claim",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Rejection Reason",
        required=True,
    )

    def action_reject(self):
        """Reject the insurance claim with the given reason."""
        self.ensure_one()

        if not self.reason:
            raise UserError(_("Please enter a rejection reason."))

        if self.claim_id.state != "confirmed":
            raise UserError(_("Only confirmed claims can be rejected."))

        self.claim_id.write({
            "state": "rejected",
            "rejection_reason": self.reason,
        })

        return {"type": "ir.actions.act_window_close"}

