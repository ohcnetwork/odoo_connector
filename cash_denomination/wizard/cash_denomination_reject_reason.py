from odoo import models, fields, api
from odoo.exceptions import UserError

class CashDenominationRejectWizard(models.TransientModel):
    _name = 'cash.denomination.reject.wizard'
    _description = 'Cash Denomination Reject Reason Wizard'

    reject_reason = fields.Text(string="Reject Reason", required=True)

    def action_confirm_reject(self):
        """Apply rejection reason to the record"""
        denomination = self.env['cash.denomination'].browse(self.env.context.get('active_id'))

        denomination.write({
            'state': 'rejected',
            'reject_reason': self.reject_reason
        })

        return {"type": "ir.actions.act_window_close"}
