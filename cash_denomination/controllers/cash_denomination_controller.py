from odoo import http,fields
from odoo.http import request
from datetime import date
from datetime import datetime, time
import pytz

class CashDenominationPageController(http.Controller):

    @http.route('/cash/denomination', type='http', auth='user', website=True)
    def cash_denomination_page(self, **kw):
        user = request.env.user

        cash_denomination_model = request.env['cash.denomination'].sudo()
        payment_model = request.env['account.payment'].sudo()
        payment_line_model = request.env['denomination.payment.lines'].sudo()

        counter_list = []

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

            existing_line = denomination.payment_ids.filtered(
                lambda l: l.payment_id.id == payment.id
            )

            if not existing_line:
                payment_line_model.create({
                    'denomination_id': denomination.id,
                    'payment_id': payment.id,
                })

            if denomination.counter not in counter_list:
                counter_list.append(denomination.counter)

        pending_denominations = cash_denomination_model.sudo().search([
            ('user', '=', user.id),
            ('state', '=', 'submit'),
            ('pending_amount', '>', 0)
        ])
        for pending in pending_denominations:
            if pending.counter not in counter_list:
                counter_list.append(pending.counter)
        denominations = [500, 200, 100, 50, 20, 10, 5, 2, 1]
        return request.render("cash_denomination.website_cash_denomination", {
            'counters': counter_list,
            'denominations': denominations,
        })

    @http.route('/get/payment/amount/by/counter', type='json', auth='user')
    def get_payment_amount_by_counter(self, counter_id):
        """Return total cash, cash in hand, and petty cash for the selected counter"""
        user = request.env.user
        cash_denomination_model = request.env['cash.denomination']
        cash_transfer_model = request.env['cash.transfer']
        domain = [  ('user', '=', user.id),
                    ('counter', '=', int(counter_id)),
                    ('state', '=', 'draft')
                  ]
        cash_denomination = cash_denomination_model.sudo().search(domain)
        transfer_amount = sum(cash_denomination.cash_transfer_ids.mapped('grand_total'))
        cash_in_hand = cash_denomination.total_in_hand
        cash_transfer_list = cash_transfer_model.sudo().search([
            ('state', '=', 'submit'),
            ('from_location', '=', int(counter_id)),
            ('from_user', '=', user.id),
        ])

        transfer_cash = sum(cash_transfer_list.mapped('grand_total'))
        transfer_list=[]
        for transfer in cash_transfer_list:
            if transfer.from_user != user:
                transfer_list.append({
                    'id': transfer.id,
                    'from_user': transfer.from_user.name,
                    'from_user_id': transfer.from_user.id,
                    'from_counter': transfer.from_location.bill_counter,
                    'from_counter_id': transfer.from_location.id,
                    'to_counter_id': transfer.to_location.id,
                    'date': str(transfer.date),
                    'grand_total': transfer.grand_total,
                })

        return {
            'total_cash': cash_in_hand,
            'transfer_cash': transfer_cash,
            'transfer_list': transfer_list,
            'transfer_amount': transfer_amount,
        }

    @http.route('/get/all/counter', type='json', auth='user')
    def get_all_counters(self):
        """Return users assigned to selected counter"""
        bill_counter_model = request.env['bill.counter']
        bill_counter_list = bill_counter_model.sudo().search([])
        location_list = []
        cashier_list = []
        for location in bill_counter_list:
            location_list.append({'id': location.id, 'name': location.bill_counter})
            for user in location.name:
                cashier_list.append({'id': user.id,'name': user.name,})

        return {
            'locations': location_list,
            'cashiers':cashier_list
        }

    @http.route(['/cash/denomination/submit'], type='http', auth='user', methods=['POST'], website=True, csrf=False)
    def cash_denomination_submit(self, **post):
        user = request.env.user
        counter_id = int(post.get('counter'))
        cash_denomination_model = request.env['cash.denomination']
        remark = post.get('remark') or ""

        cash_denomination = cash_denomination_model.sudo().search([
            ('user', '=', user.id),
            ('counter', '=', int(counter_id)),
            ('state', '=', 'draft')
        ],limit=1)

        if cash_denomination:
            line_values = []
            for key, value in post.items():
                if key.startswith('counts_') and value and int(value) > 0:
                    currency = key.split('_')[1]
                    line_values.append((0, 0, {
                        'counts': int(value),
                        'currency': currency,
                    }))
            cash_denomination.sudo().write({
                'denomination_line_ids': line_values,
                'remark': remark,
            })
        return request.redirect('/cash/denomination?success=1')

    @http.route('/get/denomination/details/by/counter', type='json', auth='user')
    def denomination_details_by_counter(self, counter_id):
        user = request.env.user
        cash_denomination_model = request.env['cash.denomination'].sudo()
        cash_denomination = cash_denomination_model.search([
            ('user', '=', user.id),
            ('counter', '=', int(counter_id)),
            ('state', '=', 'draft')
        ])
        denomination_details_dict = {}
        if cash_denomination:
            total_payment = sum(cash_denomination.payment_ids.mapped('amount'))
            total_accepted_transfer = sum(cash_denomination.accept_transfer_ids.mapped('amount'))
            total_pending_amount = sum(cash_denomination.pending_amount_ids.mapped('amount'))
            total_amount = total_payment + total_accepted_transfer + total_pending_amount
            denomination_details_dict = {
                "total_amount": total_amount,
                "total_denomination": sum(cash_denomination.denomination_line_ids.mapped('sub_total')),
                "total_transfer": sum(cash_denomination.cash_transfer_ids.mapped('grand_total')),
                "total_pending": cash_denomination.pending_amount,
                "counter": cash_denomination.counter.bill_counter,
                "date": cash_denomination.date,
                "cashier": user.name,
            }
        return denomination_details_dict


    @http.route('/cash/transfer/submit', type='http', auth='user', methods=['POST'], csrf=False, website=True)
    def cash_transfer_submit(self, **post):

        user = request.env.user
        from_counter = int(post.get('from_selected_counter'))
        to_counter = int(post.get('to_all_locations'))
        to_cashier = int(post.get('cashier_id'))
        date_str = post.get('created_date')
        cash_transfer_model = request.env['cash.transfer']
        cash_denomination_model = request.env['cash.denomination']

        cash_denomination = cash_denomination_model.sudo().search([
            ('user', '=', user.id),
            ('counter', '=', int(from_counter)),
            ('state', '=', 'draft')
        ], limit=1)
        denom_lines = []
        for key, val in post.items():
            if key.isdigit() and val and int(val) > 0:
                denom_lines.append((0, 0, {
                    'currency': key,
                    'counts': int(val),
                }))

        cash_transfer = cash_transfer_model.sudo().create({
            'date': date_str,
            'from_user': user.id,
            'to_user': int(to_cashier),
            'from_location': from_counter,
            'to_location': to_counter,
            'denomination_id': cash_denomination.id,
            'line_ids': denom_lines,
        })
        cash_transfer.write({'state': 'submit'})

        return request.redirect('/cash/denomination?transfer_success=1')


    @http.route('/cash/denomination/submit/to/accounts', type='http', auth='user', methods=['POST'], csrf=False, website=True)
    def cash_denomination_submit_to_accounts(self, **post):
        user = request.env.user
        counter_id = int(post.get('counter_id'))
        cash_denomination_model = request.env['cash.denomination']
        denomination_pending_model = request.env['denomination.payment.pending.lines']
        cash_denomination = cash_denomination_model.sudo().search([
            ('user', '=', user.id),
            ('counter', '=', int(counter_id)),
            ('state', '=', 'draft')
        ])

        if cash_denomination:
            if cash_denomination.denomination_line_ids:
                cash_denomination.sudo().write({
                    'state': 'submit'
                })

                payments = cash_denomination.payment_ids.mapped('payment_id')
                if payments:
                    payments.sudo().write({'is_denomination': True})

            if cash_denomination.pending_amount > 0:
                new_denomination = cash_denomination_model.sudo().create({
                    'date': fields.Date.today(),
                    'user': user.id,
                    'counter': cash_denomination.counter.id,
                    'state': 'draft'
                })
                if new_denomination:
                    denomination_pending_model.sudo().create({
                        'denomination_id': new_denomination.id,
                        'pending_denomination_id': cash_denomination.id,
                        'amount': cash_denomination.pending_amount
                    })

        return request.redirect('/cash/denomination?success=1')

    @http.route('/cancel/denomination/amount', type='json', auth='user')
    def cancel_denomination_entry(self, counter_id):
        user = request.env.user
        cash_denomination_model = request.env['cash.denomination']
        cash_denomination = cash_denomination_model.sudo().search([
            ('user', '=', user.id),
            ('counter', '=', int(counter_id)),
            ('state', '=', 'draft')
        ])

        if cash_denomination:
            cash_denomination.denomination_line_ids.unlink()
        return True

    @http.route('/cancel/transfer/amount', type='json', auth='user')
    def cancel_transfer_entry(self, counter_id):
        user = request.env.user
        cash_denomination_model = request.env['cash.denomination']
        cash_denomination = cash_denomination_model.sudo().search([
            ('user', '=', user.id),
            ('counter', '=', int(counter_id)),
            ('state', '=', 'draft')
        ])

        if cash_denomination:
            cash_denomination.cash_transfer_ids.unlink()
        return True
