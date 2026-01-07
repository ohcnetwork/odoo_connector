from odoo import http,fields
from odoo.http import request
from datetime import date
from datetime import datetime, time

class pendingCashTransferPageController(http.Controller):    
    
    
    @http.route('/cash/denomination/register',type='http', auth='user', website=True)
    def get_cash_denomination_register(self):

        return request.render("cash_denomination.website_cash_denomination_register")

    @http.route('/denomination/payment/transactions', type="http", auth="user", website=True)
    def view_cash_transfer_records(self):

        return request.render("cash_denomination.cash_transfer_records_template")

    @http.route('/pending/cash/transfer', type="http", auth="user", website=True)
    def view_pending_cash_transfer_records(self):
        user = request.env.user
        cash_transfer_model = request.env['cash.transfer']
        cash_transfer_list = cash_transfer_model.sudo().search([
            ('state', '=', 'submit'),
            ('to_user', '=', user.id),
        ])
        counter_ids = list(set(cash_transfer_list.mapped('to_location').ids))
        counters = request.env['bill.counter'].sudo().search([('id', 'in', counter_ids)])
        return request.render('cash_denomination.pending_cash_transfer_page',
            {
                'counters': counters,
            })

    @http.route('/cash/transfer/accepted', type='http', auth='user', website=True)
    def cash_transfer_accept_success(self, **kw):
        return request.render(
            'cash_denomination.cash_transfer_accepted_page'
        )


    @http.route('/check/cash/transfer/by/counter', type='json', auth='user', methods=['POST'])
    def check_cash_transfer_counter(self, counter_id):
        cash_transfer_model = request.env['cash.transfer']
        cash_transfer_list = cash_transfer_model.sudo().search([
            ('state', '=', 'submit'),
            ('to_location', '=', int(counter_id)),
        ], limit=1)
        transfer_list = []
        denomination_list =[]
        for transfer in cash_transfer_list:
            if transfer.line_ids:
                for line in transfer.line_ids:
                    denomination_list.append({
                        "id":line.id,
                        "counts":line.counts,
                        "amount":line.currency,
                        "total":line.sub_total,
                    })
            transfer_list.append({
                'id': transfer.id,
                'name': transfer.name,
                'from_user': transfer.from_user.name,
                'from_user_id': transfer.from_user.id,
                'from_counter': transfer.from_location.bill_counter,
                'from_counter_id': transfer.from_location.id,
                'to_counter': transfer.to_location.bill_counter,
                'to_counter_id': transfer.to_location.id,
                'date': str(transfer.date),
                'grand_total': transfer.grand_total,
                'denomination_list': denomination_list,
            })
        return {'transfer_list': transfer_list}

    @http.route('/cash/transfer/amount/accept', type='json', auth='user', methods=['POST'])
    def cash_transfer_amount_accept(self, counter_name):
        user = request.env.user
        cash_denomination_model = request.env['cash.denomination']
        cash_transfer_model = request.env['cash.transfer']
        transfer_accept_model = request.env['cash.transfer.accept']
        cash_transfer = cash_transfer_model.sudo().search([
            ('name', '=', counter_name),
        ], limit=1)

        if cash_transfer:
            cash_transfer.write({
                'accepted_by': user.id,
                'state': 'accepted',
            })

            current_location = cash_transfer.to_location
            cash_denomination = cash_denomination_model.sudo().search([
                ('user', '=', user.id),
                ('counter', '=', current_location.id),
                ('state', '=', 'draft')
            ], limit=1)

            if not cash_denomination:
                cash_denomination = cash_denomination_model.create({
                    'date': fields.Date.today(),
                    'user': user.id,
                    'counter': current_location.id,
                    'state': 'draft'
                })

            transfer_accept_model.sudo().create({
                'denomination_id': cash_denomination.id,
                'cash_transfer_id': cash_transfer.id,
            })
        return True


    @http.route('/cash/transfer/amount/reject', type='json', auth='user', methods=['POST'])
    def cash_transfer_amount_reject(self, transfer_number, reject_reason):
        user = request.env.user
        cash_transfer_model = request.env['cash.transfer']
        transfer_accept_model = request.env['cash.transfer.accept']
        cash_transfer = cash_transfer_model.sudo().search([
            ('name', '=', transfer_number)
        ], limit=1)

        if not cash_transfer:
            return {'error': 'Transfer not found'}

        cash_transfer.sudo().write({
            'state': 'rejected',
            'rejected_by': user.id,
            'reject_reason': reject_reason,
        })
        transfer_accept_model.sudo().create({
            'denomination_id': cash_transfer.denomination_id.id,
            'cash_transfer_id': cash_transfer.id,
        })

        return True



