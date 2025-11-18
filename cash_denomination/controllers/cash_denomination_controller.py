from odoo import http
from odoo.http import request
from datetime import date
from datetime import datetime, time
import pytz

class CashDenominationPageController(http.Controller):

    @http.route('/cash/denomination', type='http', auth='user', website=True)
    def cash_denomination_page(self, **kw):
        user = request.env.user
        bill_counter_model = request.env['bill.counter']
        denominations = [500, 200, 100, 50, 20, 10, 5, 2, 1]
        logged_user_counter = bill_counter_model.with_user(user).search([('name', 'in', user.ids)], order='id asc')
        return request.render("cash_denomination.website_cash_denomination", {
            'counters': logged_user_counter,
            'denominations': denominations,
        })

    @http.route('/get/payment/amount/by/counter', type='json', auth='user')
    def get_payment_amount_by_counter(self, counter_id):
        """Return total cash, cash in hand, and petty cash for the selected counter"""
        user = request.env.user
        today = date.today()
        start_datetime = datetime.combine(today, time.min)
        end_datetime = datetime.combine(today, time.max)

        account_payment_model = request.env['account.payment']
        cash_transfer_model = request.env['cash.transfer']
        payments = account_payment_model.with_user(user).search([
            ('journal_id.type', '=', 'cash'),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'paid'),
            ('date', '=', today),
            ('location', '=', int(counter_id)),
            ('cashier', '=', user.id),
            ('is_submitted', '=', False),
        ])

        same_counter_transfers = cash_transfer_model.search([
                    ('counter', '=', int(counter_id)),
                    ('to_user', '=', int(counter_id)),
                    ('date', '=', today),  
                    ('is_counted', '=', False),
                    ])
                    
        same_counter_amount = sum(same_counter_transfers.mapped('grand_total'))
        total_invoiced_cash = sum(payments.mapped('amount'))
        cash_in_hand = 0
        total_cash = total_invoiced_cash - same_counter_amount
        return {
            'total_cash': total_cash,
            'same_counter_amount': same_counter_amount,
        }

    @http.route(['/cash/denomination/submit'], type='http', auth='user', methods=['POST'], website=True, csrf=False)
    def cash_denomination_submit(self, **post):

        counter = request.env['bill.counter']
        cash_denomination = request.env['cash.denomination']
        cash_transfer = request.env['cash.transfer']       
        cash_denomination_line = request.env['cash.denomination.line']
        cash_transfer_line = request.env['cash.denomination.transfer.line']
        payment_model = request.env['account.payment']
        remark = post.get('remark') or ""

        user = request.env.user
        counter_id = int(post.get('counter'))
        
        date_str = post.get('date')

        counter_rec = counter.with_user(user).browse(counter_id)
        
        line_values = []
        for key, value in post.items():
            if key.startswith('counts_') and value and int(value) > 0:
                currency = key.split('_')[1]
                line_values.append((0, 0, {
                    'counts': int(value),
                    'currency': currency,
                }))

        today = date.today()
        transfer_records = cash_transfer.with_user(user).search([
            ('date', '=', today),
            ('from_user', '=', user.id),
            ('counter', '=', counter_id),  
        ], limit=1)

        same_counter_transfers = request.env['cash.transfer'].search([
            ('counter', '=', counter_id),
            ('to_user', '=', counter_id),
            ('date', '=', today),
            ('is_counted', '=', False),
        ])
        same_counter_transfers.write({'is_counted': True})

       
        transfer_lines = []

        for transfer in transfer_records:
            for line in transfer.line_ids:
                transfer_lines.append((0, 0, {
                    'currency': line.currency,
                    'counts': line.counts,
                    'to_counter': transfer.to_user.id if transfer.to_user else False,
                }))

        cash_denomination.with_user(user).create({
            'date': date_str,
            'user': user.id,
            'counter': counter_rec.bill_counter,
            'line_ids': line_values,
            'transfer_line_ids': transfer_lines,
            'remark': remark,
        })

        payments = payment_model.with_user(user).search([
            ('location', '=', counter_id),
            ('cashier', '=', user.id),
            ('date', '=', date_str),
        ])

        if payments:
            payments.write({'is_submitted': True})
        else:
            print("No payment found to update submitted status")


        return request.redirect('/cash/denomination?success=1')

    @http.route('/get/all/counter', type='json', auth='user')
    def get_all_counters(self):
        """Return users assigned to selected counter"""
        bill_counter_rec = request.env['bill.counter'].search([])
        location_list = []
        for location in bill_counter_rec:
            location_list.append({'id': location.id, 'name': location.bill_counter})

        return {'locations': location_list}

    @http.route('/cash/transfer/submit', type='http', auth='user', methods=['POST'], csrf=False, website=True)
    def cash_transfer_submit(self, **post):

        user = request.env.user
        from_counter = int(post.get('from_selected_counter'))
        to_counter = int(post.get('to_all_locations'))
        date_str = post.get('created_date')
        transfer_model = request.env['cash.transfer']
        payment_model = request.env['account.payment']

        denom_lines = []
        for key, val in post.items():
            if key.isdigit() and val and int(val) > 0:
                denom_lines.append((0, 0, {
                    'currency': key,
                    'counts': int(val),
                }))

        transfer = transfer_model.with_user(user).create({
            'date': date_str,
            'from_user': user.id,
            'counter': from_counter,
            'to_user': to_counter,
            'line_ids': denom_lines,
        })

        today = date.today()

        if to_counter != from_counter:

            transfer_amount = 0
            for line in transfer.line_ids:
                transfer_amount += int(line.currency) * int(line.counts)

            if transfer_amount > 0:

                payments = payment_model.with_user(user).search([
                    ('cashier', '=', user.id),
                    ('location', '=', from_counter),
                    ('payment_type', '=', 'inbound'),
                    ('journal_id.type', '=', 'cash'),
                    ('state', '=', 'paid'),
                    ('date', '=', today),
                    ('is_submitted', '=', False),
                ])

                remaining = transfer_amount

                for payment in payments:
                    if remaining <= 0:
                        break

                    if payment.amount <= remaining:
                        remaining -= payment.amount
                        payment.amount = 0
                    else:
                        payment.amount -= remaining
                        remaining = 0

        return request.redirect('/cash/denomination?transfer_success=1')


    @http.route('/cash/transfer/pending', type='json', auth='user')
    def get_pending_transfers(self):
        user = request.env.user
        today = date.today()
        transfer_model = request.env['cash.transfer']
        
        transfers = transfer_model.with_user(user).search([
            ('state', '=', 'draft'),        
            ('date', '=', today),
        ])

        transfer_list = []
        cashier=[]
        for t in transfers:
            if t.to_user:
                cashier.append(t.from_user.id)
                transfer_list.append({
                    'id': t.id,
                    'from_user': t.from_user.name,
                    
                    'from_counter': t.counter.bill_counter,
                    'to_counter_id': t.to_user.id,
                    'date': str(t.date),
                    'grand_total': t.grand_total,
                })
        user_flag = True if user.id in cashier else False

        return {'transfers': transfer_list,'user_flag':user_flag}


    @http.route('/cash/transfer/respond', type='json', auth='user', methods=['POST'])
    def respond_transfer(self, transfer_id, action):
        """
        Respond to a cash transfer.
        action: 'accept' or 'reject'
        """
        user = request.env.user
        transfer_model = request.env['cash.transfer']
        payment_model = request.env['account.payment']
        journal_model = request.env['account.journal']

        transfer = transfer_model.with_user(user).browse(int(transfer_id))
        if not transfer or transfer.state != 'draft':
            return {'error': 'Invalid transfer'}

        transfer_amount = sum(line.sub_total for line in transfer.line_ids)

        if action == 'accept':
            payments = payment_model.with_user(user).search([
                ('cashier', '=', user.id),
                ('location', '=', transfer.to_user.id),
                ('payment_type', '=', 'inbound'),
                ('journal_id.type', '=', 'cash'),
                ('state', '=', 'paid'),
                ('date', '=', transfer.date),
                ('is_submitted', '=', False),
            ])

            if payments:
                payments[0].amount += transfer_amount
            else:
                journal = journal_model.with_user(user).search([('type', '=', 'cash')], limit=1)
                if journal:
                    payment_model.with_user(user).create({
                        'payment_type': 'inbound',
                        'journal_id': journal.id,
                        'amount': transfer_amount,
                        'date': transfer.date,
                        'cashier': user.id,
                        'location': transfer.to_user.id,
                        'state': 'paid',
                        'is_submitted': False,
                    })

            transfer.state = 'accepted'
            return {'success': True, 'added_amount': transfer_amount}

        elif action == 'reject':
            transfer.state = 'rejected'
            return {'success': True, 'added_amount': 0}

        return {'error': 'Invalid action'}


    @http.route('/cash/transfer/details', type='json', auth='user')
    def get_transfer_details(self, counter_id):
        """
        Return all transfers sent from and received by the selected counter.
        """

        today = date.today()
        user = request.env.user
        transfer_model = request.env['cash.transfer']

        transfers = transfer_model.with_user(user).search([
            ('date', '=', today),
        ])

        transfer_list = []
        for t in transfers:
            transfer_list.append({
                'id': t.id,
                'from_user': t.from_user.name,
                'from_counter': t.counter.bill_counter,
                'from_counter_id': t.counter.id,
                'to_counter_id': t.to_user.id if t.to_user else False,
                'to_counter_name': t.to_user.bill_counter if t.to_user else '',
                'date': str(t.date),
                'grand_total': t.grand_total,
                'state': t.state,
            })

        return {'transfers': transfer_list}