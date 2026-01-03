from odoo import http, fields
from odoo.http import request


class CashDenominationPageController(http.Controller):

    @http.route('/cash/denomination', type='http', auth='user', website=True)
    def cash_denomination_page(self, **kw):
        """
        Main cash denomination page.
        Shows counters that have:
        1. New unprocessed payments (is_denomination = False)
        2. Existing draft denominations with pending amounts
        """
        user = request.env.user
        cash_denomination_model = request.env['cash.denomination'].sudo()
        payment_model = request.env['account.payment'].sudo()
        payment_line_model = request.env['denomination.payment.lines'].sudo()

        counter_set = set()  # Use set to avoid duplicates

        # Step 1: Process new payments and create/update denominations
        payments = payment_model.search([
            ('partner_type', '=', 'customer'),
            ('journal_id.type', '=', 'cash'),
            ('state', '=', 'paid'),
            ('cashier', '=', user.id),
            ('is_denomination', '=', False),
        ])

        for payment in payments:
            if not payment.location:
                continue

            denomination = cash_denomination_model.search([
                ('user', '=', payment.cashier.id),
                ('counter', '=', payment.location.id),
                ('state', '=', 'draft')
            ], limit=1)

            if not denomination:
                denomination = cash_denomination_model.create({
                    'date': fields.Date.today(),
                    'user': payment.cashier.id,
                    'counter': payment.location.id,
                    'state': 'draft'
                })

            # Check if payment is already linked
            existing_line = denomination.payment_ids.filtered(
                lambda l: l.payment_id.id == payment.id
            )

            if not existing_line:
                payment_line_model.create({
                    'denomination_id': denomination.id,
                    'payment_id': payment.id,
                })

            counter_set.add(denomination.counter)

        # Step 2: Also include counters with existing draft denominations that have pending amounts
        # This fixes the bug where counters disappear after submitting
        existing_draft_denominations = cash_denomination_model.search([
            ('user', '=', user.id),
            ('state', '=', 'draft'),
        ])

        for denomination in existing_draft_denominations:
            # Include if there's any pending amount or payments
            if denomination.pending_amount > 0 or denomination.payment_ids:
                counter_set.add(denomination.counter)

        # Step 3: Also check for rejected denominations that need resubmission
        rejected_denominations = cash_denomination_model.search([
            ('user', '=', user.id),
            ('state', '=', 'rejected'),
        ])

        for denomination in rejected_denominations:
            counter_set.add(denomination.counter)

        # Convert set to list and filter out False/None values
        counter_list = [c for c in counter_set if c]

        denominations = [2000, 500, 200, 100, 50, 20, 10, 5, 2, 1]
        return request.render("cash_denomination.website_cash_denomination", {
            'counters': counter_list,
            'denominations': denominations,
        })

    @http.route('/get/payment/amount/by/counter', type='json', auth='user')
    def get_payment_amount_by_counter(self, counter_id):
        """Return total cash, cash in hand, and petty cash for the selected counter"""
        user = request.env.user
        cash_denomination_model = request.env['cash.denomination'].sudo()
        cash_transfer_model = request.env['cash.transfer'].sudo()

        # Get current draft denomination for this counter
        cash_denomination = cash_denomination_model.search([
            ('user', '=', user.id),
            ('counter', '=', int(counter_id)),
            ('state', '=', 'draft')
        ], limit=1)

        # Calculate transfer amount (only submitted/accepted transfers)
        transfer_amount = 0
        if cash_denomination:
            active_transfers = cash_denomination.cash_transfer_ids.filtered(
                lambda t: t.state in ('submit', 'accepted')
            )
            transfer_amount = sum(active_transfers.mapped('grand_total'))

        cash_in_hand = cash_denomination.total_in_hand if cash_denomination else 0

        # Get pending transfers to this counter from other users
        pending_transfers = cash_transfer_model.search([
            ('state', '=', 'submit'),
            ('to_location', '=', int(counter_id)),
            ('from_user', '!=', user.id),  # Exclude transfers from self
        ])

        transfer_cash = sum(pending_transfers.mapped('grand_total'))
        transfer_list = []

        for transfer in pending_transfers:
            transfer_list.append({
                'id': transfer.id,
                'name': transfer.name,
                'from_user': transfer.from_user.name,
                'from_user_id': transfer.from_user.id,
                'from_counter': transfer.from_location.bill_counter,
                'from_counter_id': transfer.from_location.id,
                'to_counter_id': transfer.to_location.id,
                'date': str(transfer.date),
                'grand_total': transfer.grand_total,
            })

        # Also check for rejected denomination that needs attention
        rejected_denomination = cash_denomination_model.search([
            ('user', '=', user.id),
            ('counter', '=', int(counter_id)),
            ('state', '=', 'rejected')
        ], limit=1)

        return {
            'total_cash': cash_in_hand,
            'transfer_cash': transfer_cash,
            'transfer_list': transfer_list,
            'transfer_amount': transfer_amount,
            'has_rejected': bool(rejected_denomination),
            'reject_reason': rejected_denomination.reject_reason if rejected_denomination else '',
        }

    @http.route('/get/all/counter', type='json', auth='user')
    def get_all_counters(self):
        """Return all available counters for transfer destination"""
        bill_counter_model = request.env['bill.counter'].sudo()
        bill_counter_list = bill_counter_model.search([])
        location_list = [
            {'id': location.id, 'name': location.bill_counter}
            for location in bill_counter_list
        ]
        return {'locations': location_list}

    @http.route('/cash/denomination/submit', type='http', auth='user', methods=['POST'], website=True)
    def cash_denomination_submit(self, **post):
        """Submit cash denomination for a counter"""
        user = request.env.user
        counter_id = int(post.get('counter'))
        cash_denomination_model = request.env['cash.denomination'].sudo()
        remark = post.get('remark') or ""

        # First check for rejected denomination to reset
        rejected_denomination = cash_denomination_model.search([
            ('user', '=', user.id),
            ('counter', '=', counter_id),
            ('state', '=', 'rejected')
        ], limit=1)

        if rejected_denomination:
            # Reset the rejected denomination to draft
            rejected_denomination.write({
                'state': 'draft',
                'reject_reason': False,
            })
            rejected_denomination.denomination_line_ids.unlink()

        # Get the draft denomination
        cash_denomination = cash_denomination_model.search([
            ('user', '=', user.id),
            ('counter', '=', counter_id),
            ('state', '=', 'draft')
        ], limit=1)

        if not cash_denomination:
            return request.redirect('/cash/denomination?error=no_denomination')

        # Build denomination lines from form data
        line_values = []
        for key, value in post.items():
            if key.startswith('counts_') and value:
                try:
                    count = int(value)
                    if count > 0:
                        currency = key.split('_')[1]
                        line_values.append((0, 0, {
                            'counts': count,
                            'currency': currency,
                        }))
                except (ValueError, IndexError):
                    continue

        if not line_values:
            return request.redirect('/cash/denomination?error=no_counts')

        # Update denomination with lines and submit
        cash_denomination.write({
            'denomination_line_ids': line_values,
            'remark': remark,
            'state': 'submit',
            'date': fields.Date.today(),  # Update date to submission date
        })

        # Mark associated payments as denomination processed
        payments = cash_denomination.payment_ids.mapped('payment_id')
        if payments:
            payments.write({'is_denomination': True})

        return request.redirect('/cash/denomination?success=1')

    @http.route('/cash/transfer/submit', type='http', auth='user', methods=['POST'], website=True)
    def cash_transfer_submit(self, **post):
        """Submit cash transfer to another counter"""
        user = request.env.user
        from_counter = int(post.get('from_selected_counter'))
        to_counter = int(post.get('to_all_locations'))
        date_str = post.get('created_date')

        cash_transfer_model = request.env['cash.transfer'].sudo()
        cash_denomination_model = request.env['cash.denomination'].sudo()

        # Validate: cannot transfer to same counter
        if from_counter == to_counter:
            return request.redirect('/cash/denomination?error=same_counter')

        # Get source denomination
        cash_denomination = cash_denomination_model.search([
            ('user', '=', user.id),
            ('counter', '=', from_counter),
            ('state', '=', 'draft')
        ], limit=1)

        if not cash_denomination:
            return request.redirect('/cash/denomination?error=no_denomination')

        # Build denomination lines
        denom_lines = []
        for key, val in post.items():
            if key.isdigit() and val:
                try:
                    count = int(val)
                    if count > 0:
                        denom_lines.append((0, 0, {
                            'currency': key,
                            'counts': count,
                        }))
                except ValueError:
                    continue

        if not denom_lines:
            return request.redirect('/cash/denomination?error=no_counts')

        # Create transfer
        cash_transfer = cash_transfer_model.create({
            'date': date_str or fields.Date.today(),
            'from_user': user.id,
            'from_location': from_counter,
            'to_location': to_counter,
            'denomination_id': cash_denomination.id,
            'line_ids': denom_lines,
            'state': 'submit',
        })

        return request.redirect('/cash/denomination?transfer_success=1')
