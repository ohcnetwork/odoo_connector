from odoo import models, fields, api
from odoo.exceptions import UserError


class CashDenomination(models.Model):
    _name = 'cash.denomination'
    _description = 'Cash Denomination'
    _rec_name = "user"
    _order = 'id desc'

    date = fields.Date(string='Date', readonly=True)
    user = fields.Many2one('res.users',string='Person',readonly=True)
    counter = fields.Many2one('bill.counter',string='Counter',readonly=True)
    total_in_hand = fields.Char(string="Total in Hand",compute='_compute_total_in_hand',readonly=True)
    pending_amount = fields.Float(string="Pending Amount", default=0, readonly=True)
    remark = fields.Text(string="Remark")
    denomination_line_ids = fields.One2many('cash.denomination.line', 'denomination_id', string='Denomination Lines', readonly=True)
    payment_ids = fields.One2many('denomination.payment.lines', 'denomination_id', string='Payment Lines',
                                  readonly=True)
    accept_transfer_ids = fields.One2many('cash.transfer.accept', 'denomination_id', string='Accepted Payments',
                                          readonly=True)
    pending_amount_ids = fields.One2many('denomination.payment.pending.lines', 'denomination_id',string='Pending Payments',
                                         readonly=True)
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
    reject_reason = fields.Text(string="Reject Reason",readonly=True)


    @api.depends('payment_ids','denomination_line_ids')
    def _compute_total_in_hand(self):
        for rec in self:
            rec.pending_amount = 0
            total_payment = sum(rec.payment_ids.mapped('amount'))
            total_accepted_transfer = sum(rec.accept_transfer_ids.mapped('amount'))
            total_denomination = sum(rec.denomination_line_ids.mapped('sub_total'))
            total_transfer = sum(rec.cash_transfer_ids.mapped('grand_total'))
            total_pending = sum(rec.pending_amount_ids.mapped('amount'))
            total_spend = total_denomination + total_transfer
            total_accept = total_payment + total_accepted_transfer + total_pending
            total = total_accept - total_spend
            if total<=0:
                rec.total_in_hand = 0
            else:
                rec.total_in_hand = total
                rec.pending_amount = total


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
            account_move_model = self.env['account.move']
            config = self.env['account.head.config'].search([], limit=1)
            if not config:
                raise UserError("Please configure the Cash Denomination Accounts.")

            debit_account = config.debit_account_id.id
            credit_account = config.credit_account_id.id

            if not debit_account or not credit_account:
                raise UserError("Debit and Credit accounts must be set in Cash Denomination Configuration.")

            amount = sum(rec.denomination_line_ids.mapped('sub_total'))

            if amount <= 0:
                raise UserError("Grand total must be greater than zero to create a Journal Entry.")

            journal_model = self.env['account.journal']
            journal = journal_model.search([('type', '=', 'general')], limit=1)

            if not journal:
               return {'error': 'Miscellaneous Journal not found'}

            move_vals = {
                'date': rec.date,
                'ref': f"Cash Denomination - {rec.user.name}",
                'journal_id': journal.id,
                'line_ids': [
                    (0, 0, {
                        'account_id': debit_account,
                        'name': f"Cash Denomination by {rec.user.name}",
                        'debit': amount,
                        'credit': 0,
                    }),
                    (0, 0, {
                        'account_id': credit_account,
                        'name': f"Cash Denomination by {rec.user.name}",
                        'debit': 0,
                        'credit': amount,
                    }),
                ]
            }

            move = account_move_model.create(move_vals)
            move.action_post()
            rec.journal_entry_id = move.id
            self.write({'state': 'approved'})

    def action_reject(self):
        for rec in self:
            amount = sum(rec.denomination_line_ids.mapped('sub_total'))
            rec.pending_amount += amount
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Reason',
            'res_model': 'cash.denomination.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
    }


class CashDenominationLine(models.Model):
    _name = 'cash.denomination.line'
    _description = 'Cash Denomination Line'

    denomination_id = fields.Many2one('cash.denomination', string='Cash Denomination', ondelete='cascade')
    counts = fields.Integer(string='Counts', required=True, readonly=True)
    currency = fields.Selection(
        [('1', '1'), ('2', '2'), ('5', '5'), ('10', '10'), ('20', '20'), ('50', '50'), ('100', '100'), ('200', '200'),
         ('500', '500')],
        string='Currency', required=True, readonly=True)
    sub_total = fields.Float(string='Sub Total',compute='_compute_sub_total', store=True, readonly=True)
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
            line.sub_total = line.counts * int(line.currency)


class DenominationPaymentLines(models.Model):
    _name = 'denomination.payment.lines'
    _description = 'Cash Denomination Payment Lines'

    denomination_id = fields.Many2one('cash.denomination', string='Cash Denomination', ondelete='cascade')
    payment_id = fields.Many2one('account.payment', string='Payment', readonly=True)
    amount = fields.Monetary(
        string="Amount",
        related="payment_id.amount_signed",
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
    _description = 'Cash Transfer accept'

    denomination_id = fields.Many2one('cash.denomination', string='Cash Denomination', ondelete='cascade')
    cash_transfer_id = fields.Many2one('cash.transfer', string='Accepted transfers', readonly=True)
    amount = fields.Float(string='Amount', compute='_compute_total_transfer_amount', store=True)

    @api.depends('cash_transfer_id')
    def _compute_total_transfer_amount(self):
        for rec in self:
            rec.amount = sum(rec.cash_transfer_id.line_ids.mapped('sub_total'))



class DenominationPaymentPendingLines(models.Model):
    _name = 'denomination.payment.pending.lines'
    _description = 'Cash Denomination Payment Pending Lines'

    denomination_id = fields.Many2one('cash.denomination', string='Cash Denomination', ondelete='cascade')
    pending_denomination_id = fields.Many2one('cash.denomination', string='Pending Denominations', readonly=True)
    amount = fields.Float(string='Amount', store=True)