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

            if invoice.state == 'cancel':
                rec.commission_state = 'cancelled'
                continue

            payments = invoice.matched_payment_ids

            if not payments:
                rec.commission_state = 'draft'
                continue

            any_paid = any(p.state == 'paid' for p in payments)

            all_cancelled = all(p.state == 'canceled' for p in payments)

            if any_paid:
                rec.commission_state = 'posted'
            elif all_cancelled:
                rec.commission_state = 'cancelled'
            else:
                rec.commission_state = 'draft'

