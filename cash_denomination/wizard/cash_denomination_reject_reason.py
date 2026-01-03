from odoo import models, fields
from odoo.exceptions import UserError


class CashDenominationRejectWizard(models.TransientModel):
    _name = 'cash.denomination.reject.wizard'
    _description = 'Cash Denomination Reject Reason Wizard'

    reject_reason = fields.Text(string="Reject Reason", required=True)

    def action_confirm_reject(self):
        """Apply rejection reason to the cash denomination record"""
        self.ensure_one()
        
        active_id = self.env.context.get('active_id')
        if not active_id:
            raise UserError("No active record found to reject.")
        
        denomination = self.env['cash.denomination'].browse(active_id)
        if not denomination.exists():
            raise UserError("The cash denomination record no longer exists.")
        
        if denomination.state != 'submit':
            raise UserError("Only submitted denominations can be rejected.")

        denomination.write({
            'state': 'rejected',
            'reject_reason': self.reject_reason
        })
        
        # Post a message to the chatter for audit trail
        denomination.message_post(
            body=f"Denomination rejected. Reason: {self.reject_reason}",
            message_type='notification'
        )

        return {"type": "ir.actions.act_window_close"}
