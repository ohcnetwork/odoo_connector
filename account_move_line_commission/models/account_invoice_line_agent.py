from odoo import models, fields, api

class AccountInvoiceLineAgent(models.Model):
    _inherit = 'account.invoice.line.agent'

    commission_state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string="Commission Status", compute="_compute_commission_state", store=True)

    @api.depends('invoice_id.state','invoice_id.matched_payment_ids.state')
    def _compute_commission_state(self):
        for rec in self:
            invoice = rec.invoice_id
            if not invoice:
                rec.commission_state = 'draft'
                continue

            payment_ids = invoice.matched_payment_ids
            if not payment_ids:
                rec.commission_state = 'draft'
                continue

            any_paid = any(payment.state == 'paid' for payment in payment_ids)
            all_cancelled = all(payment.state == 'canceled' for payment in payment_ids)
            if any_paid and invoice.state == 'posted':
                rec.commission_state = 'posted'

            if invoice.state == 'cancel':
                rec.commission_state = 'cancelled'
                continue

            if all_cancelled:
                rec.commission_state = 'cancelled'


