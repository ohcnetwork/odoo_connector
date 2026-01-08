from odoo import models, fields, api
from odoo.exceptions import UserError


class CashTransfer(models.Model):
    _name = 'cash.transfer'
    _description = 'Cash Transfer'
    _order = 'created_at desc'

    # === SESSIONS ===
    from_session_id = fields.Many2one(
        'cash.session',
        string='From Session',
        required=True,
        index=True,
        ondelete='restrict'
    )
    to_session_id = fields.Many2one(
        'cash.session',
        string='To Session',
        required=True,
        index=True,
        ondelete='restrict'
    )

    # === AMOUNT ===
    amount = fields.Float(string='Amount', required=True)
    denominations = fields.Json(
        string='Denominations',
        help='Breakdown of currency denominations (required for main cash transfers)'
    )

    # === STATUS ===
    status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', required=True, index=True)

    # === CREATED BY (Care identity) ===
    created_by_ext_id = fields.Char(string='Created By ID', required=True)
    created_by_name = fields.Char(string='Created By Name', required=True)
    created_at = fields.Datetime(
        string='Created At',
        default=fields.Datetime.now,
        required=True
    )

    # === RESOLVED BY ===
    resolved_by_ext_id = fields.Char(string='Resolved By ID')
    resolved_by_name = fields.Char(string='Resolved By Name')
    resolved_at = fields.Datetime(string='Resolved At')
    reject_reason = fields.Text(string='Reject Reason')

    # === ACCOUNTING ===
    journal_entry_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True
    )

    # === RELATED FIELDS FOR DISPLAY ===
    from_user_name = fields.Char(
        related='from_session_id.external_user_name',
        string='From User',
        store=True
    )
    from_counter_name = fields.Char(
        related='from_session_id.counter_id.bill_counter',
        string='From Counter',
        store=True
    )
    to_user_name = fields.Char(
        related='to_session_id.external_user_name',
        string='To User',
        store=True
    )
    to_counter_name = fields.Char(
        related='to_session_id.counter_id.bill_counter',
        string='To Counter',
        store=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Validate from_session is open
            from_session = self.env['cash.session'].browse(vals.get('from_session_id'))
            if from_session.status != 'open':
                raise UserError('Cannot create transfer from a closed session')

            # Validate to_session is open
            to_session = self.env['cash.session'].browse(vals.get('to_session_id'))
            if to_session.status != 'open':
                raise UserError('Cannot create transfer to a closed session')

            # Validate amount is positive
            amount = vals.get('amount', 0)
            if amount <= 0:
                raise UserError('Transfer amount must be positive')

            # Validate sender has enough available balance
            # available_balance = expected_amount - pending_outgoing_transfers
            available = from_session.available_balance
            if amount > available:
                raise UserError(
                    f'Insufficient balance. '
                    f'Available: {available:.2f}, Requested: {amount:.2f}. '
                    f'(Expected: {from_session.expected_amount:.2f}, '
                    f'Pending outgoing: {from_session.pending_outgoing_amount:.2f})'
                )

        return super().create(vals_list)

    def action_accept(self, resolved_by_ext_id, resolved_by_name):
        """Accept a pending transfer. Creates journal entry only for Main Cash transfers."""
        self.ensure_one()

        if self.status != 'pending':
            raise UserError('Only pending transfers can be accepted')

        to_counter = self.to_session_id.counter_id
        journal_entry = None

        # Only create journal entry if destination is Main Cash
        if to_counter.is_main_cash:
            company = self.env.company

            # Validate company configuration
            if not company.counter_cash_journal_id:
                raise UserError('Counter Cash Journal is not configured. Please configure it in Company Settings.')
            if not company.main_cash_journal_id:
                raise UserError('Main Cash Journal is not configured. Please configure it in Company Settings.')

            # Get accounts from journals
            counter_cash_account = company.counter_cash_journal_id.default_account_id
            main_cash_account = company.main_cash_journal_id.default_account_id

            if not counter_cash_account:
                raise UserError('Counter Cash Journal does not have a default account configured.')
            if not main_cash_account:
                raise UserError('Main Cash Journal does not have a default account configured.')

            # Create journal entry in Main Cash Journal
            # Dr Main Cash Account (money coming in to main cash)
            # Cr Counter Cash Account (money leaving counter)
            move_vals = {
                'journal_id': company.main_cash_journal_id.id,
                'ref': f'Cash Transfer: {self.from_session_id.counter_id.bill_counter} → Main Cash',
                'date': fields.Date.today(),
                'line_ids': [
                    (0, 0, {
                        'account_id': main_cash_account.id,
                        'name': f'Cash from {self.from_session_id.external_user_name} @ {self.from_session_id.counter_id.bill_counter}',
                        'debit': self.amount,
                        'credit': 0,
                    }),
                    (0, 0, {
                        'account_id': counter_cash_account.id,
                        'name': f'Transfer to Main Cash',
                        'debit': 0,
                        'credit': self.amount,
                    }),
                ]
            }

            move = self.env['account.move'].create(move_vals)
            move.action_post()
            journal_entry = move

        # Update transfer status (for both Counter→Counter and Counter→Main Cash)
        self.write({
            'status': 'accepted',
            'journal_entry_id': journal_entry.id if journal_entry else False,
            'resolved_by_ext_id': resolved_by_ext_id,
            'resolved_by_name': resolved_by_name,
            'resolved_at': fields.Datetime.now(),
        })

        return True

    def action_reject(self, resolved_by_ext_id, resolved_by_name, reason=None):
        """Reject a pending transfer."""
        self.ensure_one()

        if self.status != 'pending':
            raise UserError('Only pending transfers can be rejected')

        self.write({
            'status': 'rejected',
            'resolved_by_ext_id': resolved_by_ext_id,
            'resolved_by_name': resolved_by_name,
            'resolved_at': fields.Datetime.now(),
            'reject_reason': reason,
        })

        return True

    def action_cancel(self, cancelled_by_ext_id, cancelled_by_name, reason=None):
        """Cancel a pending transfer (by the sender)."""
        self.ensure_one()

        if self.status != 'pending':
            raise UserError('Only pending transfers can be cancelled')

        self.write({
            'status': 'cancelled',
            'resolved_by_ext_id': cancelled_by_ext_id,
            'resolved_by_name': cancelled_by_name,
            'resolved_at': fields.Datetime.now(),
            'reject_reason': reason,  # Reuse reject_reason field for cancel reason
        })

        return True

    def action_view_journal_entry(self):
        """Open the related journal entry."""
        self.ensure_one()
        if not self.journal_entry_id:
            raise UserError('No journal entry linked to this transfer')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'res_id': self.journal_entry_id.id,
            'view_mode': 'form',
            'target': 'current',
        }