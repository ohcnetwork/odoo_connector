from odoo import models, fields, api
from odoo.exceptions import UserError


class CashDenomination(models.Model):
    _name = 'cash.denomination'
    _description = 'Cash Denomination'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "display_name"
    _order = 'id desc'

    date = fields.Date(string='Date', readonly=True)
    user = fields.Many2one('res.users', string='Person', readonly=True)
    counter = fields.Many2one('bill.counter', string='Counter', readonly=True)
    total_in_hand = fields.Float(
        string="Total in Hand",
        compute='_compute_total_in_hand',
        store=True,
        readonly=True
    )
    pending_amount = fields.Float(
        string="Pending Amount",
        compute='_compute_total_in_hand',
        store=True,
        readonly=True
    )
    remark = fields.Text(string="Remark")
    denomination_line_ids = fields.One2many(
        'cash.denomination.line',
        'denomination_id',
        string='Denomination Lines',
        readonly=True
    )
    payment_ids = fields.One2many(
        'denomination.payment.lines',
        'denomination_id',
        string='Payment Lines',
        readonly=True
    )
    accept_transfer_ids = fields.One2many(
        'cash.transfer.accept',
        'denomination_id',
        string='Accepted Payments',
        readonly=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)
    cash_transfer_ids = fields.One2many(
        'cash.transfer',
        'denomination_id',
        string='Cash Transfers'
    )
    journal_entry_id = fields.Many2one('account.move', string="Journal Entry", readonly=True)
    reject_reason = fields.Text(string="Reject Reason", readonly=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('user', 'counter', 'date')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.user:
                parts.append(rec.user.name)
            if rec.counter:
                parts.append(rec.counter.bill_counter)
            if rec.date:
                parts.append(str(rec.date))
            rec.display_name = ' - '.join(parts) if parts else f'Denomination #{rec.id}'

    @api.depends(
        'payment_ids',
        'payment_ids.amount',
        'denomination_line_ids',
        'denomination_line_ids.sub_total',
        'accept_transfer_ids',
        'accept_transfer_ids.amount',
        'cash_transfer_ids',
        'cash_transfer_ids.grand_total',
        'cash_transfer_ids.state'
    )
    def _compute_total_in_hand(self):
        for rec in self:
            # Total received from payments
            total_payment = sum(rec.payment_ids.mapped('amount'))
            
            # Total received from accepted transfers
            total_accepted_transfer = sum(rec.accept_transfer_ids.mapped('amount'))
            
            # Total submitted via denomination
            total_denomination = sum(rec.denomination_line_ids.mapped('sub_total'))
            
            # Total transferred out (only count submitted/accepted, not rejected)
            active_transfers = rec.cash_transfer_ids.filtered(
                lambda t: t.state in ('submit', 'accepted')
            )
            total_transfer = sum(active_transfers.mapped('grand_total'))
            
            # Calculate totals
            total_received = total_payment + total_accepted_transfer
            total_spent = total_denomination + total_transfer
            balance = total_received - total_spent
            
            rec.total_in_hand = max(balance, 0)
            rec.pending_amount = max(balance, 0)

    def action_open_cash_transfer(self):
        """Open Cash Transfer Records related to this denomination"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cash Transfers',
            'res_model': 'cash.transfer',
            'view_mode': 'list,form',
            'domain': [('denomination_id', '=', self.id)],
            'context': {'default_denomination_id': self.id},
            'target': 'current',
        }

    def open_journal_entry(self):
        self.ensure_one()
        if not self.journal_entry_id:
            raise UserError("No Journal Entry linked to this record.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'res_id': self.journal_entry_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_approve(self):
        for rec in self:
            config = self.env['account.head.config'].search([], limit=1)
            if not config:
                raise UserError("Please configure the Cash Denomination Accounts.")

            debit_account = config.debit_account_id
            credit_account = config.credit_account_id

            if not debit_account or not credit_account:
                raise UserError("Debit and Credit accounts must be set in Cash Denomination Configuration.")

            amount = sum(rec.denomination_line_ids.mapped('sub_total'))

            if amount <= 0:
                raise UserError("Grand total must be greater than zero to create a Journal Entry.")

            journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
            if not journal:
                raise UserError("Miscellaneous Journal not found. Please create a general journal.")

            move_vals = {
                'date': rec.date or fields.Date.today(),
                'ref': f"Cash Denomination - {rec.user.name}",
                'journal_id': journal.id,
                'line_ids': [
                    (0, 0, {
                        'account_id': debit_account.id,
                        'name': f"Cash Denomination by {rec.user.name}",
                        'debit': amount,
                        'credit': 0,
                    }),
                    (0, 0, {
                        'account_id': credit_account.id,
                        'name': f"Cash Denomination by {rec.user.name}",
                        'debit': 0,
                        'credit': amount,
                    }),
                ]
            }

            move = self.env['account.move'].create(move_vals)
            move.action_post()
            rec.write({
                'journal_entry_id': move.id,
                'state': 'approved'
            })

    def action_reject(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Reason',
            'res_model': 'cash.denomination.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    def action_reset_to_draft(self):
        """Allow resetting rejected denominations back to draft for correction"""
        self.ensure_one()
        if self.state != 'rejected':
            raise UserError("Only rejected denominations can be reset to draft.")
        self.write({
            'state': 'draft',
            'reject_reason': False,
        })
        # Clear denomination lines so user can re-enter
        self.denomination_line_ids.unlink()


class CashDenominationLine(models.Model):
    _name = 'cash.denomination.line'
    _description = 'Cash Denomination Line'

    denomination_id = fields.Many2one(
        'cash.denomination',
        string='Cash Denomination',
        ondelete='cascade'
    )
    counts = fields.Integer(string='Counts', required=True, readonly=True)
    currency = fields.Selection([
        ('1', '1'),
        ('2', '2'),
        ('5', '5'),
        ('10', '10'),
        ('20', '20'),
        ('50', '50'),
        ('100', '100'),
        ('200', '200'),
        ('500', '500'),
        ('2000', '2000'),
    ], string='Denomination', required=True, readonly=True)
    sub_total = fields.Float(
        string='Sub Total',
        compute='_compute_sub_total',
        store=True,
        readonly=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id.id,
        readonly=True
    )

    @api.depends('counts', 'currency')
    def _compute_sub_total(self):
        for line in self:
            line.sub_total = line.counts * int(line.currency or 0)


class DenominationPaymentLines(models.Model):
    _name = 'denomination.payment.lines'
    _description = 'Cash Denomination Payment Lines'

    denomination_id = fields.Many2one(
        'cash.denomination',
        string='Cash Denomination',
        ondelete='cascade'
    )
    payment_id = fields.Many2one('account.payment', string='Payment', readonly=True)
    amount = fields.Monetary(
        string="Amount",
        related="payment_id.amount",
        readonly=True,
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='payment_id.currency_id',
        readonly=True
    )


class CashTransferAccept(models.Model):
    _name = 'cash.transfer.accept'
    _description = 'Cash Transfer Accept'

    denomination_id = fields.Many2one(
        'cash.denomination',
        string='Cash Denomination',
        ondelete='cascade'
    )
    cash_transfer_id = fields.Many2one(
        'cash.transfer',
        string='Accepted Transfer',
        readonly=True
    )
    amount = fields.Float(
        string='Amount',
        compute='_compute_total_transfer_amount',
        store=True
    )

    @api.depends('cash_transfer_id', 'cash_transfer_id.grand_total')
    def _compute_total_transfer_amount(self):
        for rec in self:
            rec.amount = rec.cash_transfer_id.grand_total if rec.cash_transfer_id else 0
