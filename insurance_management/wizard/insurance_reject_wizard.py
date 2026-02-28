
from odoo import models, fields

class InsuranceRejectWizard(models.TransientModel):
    _name = 'insurance.reject.wizard'
    _description = 'Insurance Rejection Wizard'

    reason = fields.Text(string="Rejection Reason", required=True)
    customer_insurance_id = fields.Many2one('customer.insurance', string="Customer Insurance")

    def action_submit_reason(self):
        """Store the reason & update state to rejected."""
        cust = self.customer_insurance_id
        cust.rejection_reason = self.reason
        cust.state = 'reject'
        return {'type': 'ir.actions.act_window_close'}
