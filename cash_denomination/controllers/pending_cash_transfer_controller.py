from odoo import http, fields
from odoo.http import request


class PendingCashTransferPageController(http.Controller):

    @http.route('/cash/denomination/register', type='http', auth='user', website=True)
    def get_cash_denomination_register(self):
        return request.render("cash_denomination.website_cash_denomination_register")

    @http.route('/denomination/payment/transactions', type="http", auth="user", website=True)
    def view_cash_transfer_records(self):
        return request.render("cash_denomination.cash_transfer_records_template")

    @http.route('/pending/cash/transfer', type="http", auth="user", website=True)
    def view_pending_cash_transfer_records(self):
        counters = request.env['bill.counter'].sudo().search([])
        return request.render('cash_denomination.pending_cash_transfer_page', {
            'counters': counters,
        })

    @http.route('/cash/transfer/accepted', type='http', auth='user', website=True)
    def cash_transfer_accept_success(self, **kw):
        return request.render('cash_denomination.cash_transfer_accepted_page')

    @http.route('/check/cash/transfer/by/counter', type='json', auth='user', methods=['POST'])
    def check_cash_transfer_counter(self, counter_id):
        """Get pending cash transfers for a specific counter"""
        user = request.env.user
        cash_transfer_model = request.env['cash.transfer'].sudo()

        # Get pending transfers to this counter (excluding transfers from self)
        pending_transfers = cash_transfer_model.search([
            ('state', '=', 'submit'),
            ('to_location', '=', int(counter_id)),
            ('from_user', '!=', user.id),
        ])

        transfer_list = []
        for transfer in pending_transfers:
            denomination_list = []
            for line in transfer.line_ids:
                denomination_list.append({
                    "id": line.id,
                    "counts": line.counts,
                    "amount": line.currency,
                    "total": line.sub_total,
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
        """Accept a pending cash transfer"""
        user = request.env.user
        cash_denomination_model = request.env['cash.denomination'].sudo()
        cash_transfer_model = request.env['cash.transfer'].sudo()
        transfer_accept_model = request.env['cash.transfer.accept'].sudo()

        # Find the transfer by name
        cash_transfer = cash_transfer_model.search([
            ('name', '=', counter_name),
            ('state', '=', 'submit'),
        ], limit=1)

        if not cash_transfer:
            return {'error': 'Transfer not found or already processed'}

        # Update transfer status
        cash_transfer.write({
            'accepted_by': user.id,
            'state': 'accepted',
        })

        # Get or create denomination for the receiving counter
        current_location = cash_transfer.to_location
        cash_denomination = cash_denomination_model.search([
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

        # Create accept record to track the received transfer
        transfer_accept_model.create({
            'denomination_id': cash_denomination.id,
            'cash_transfer_id': cash_transfer.id,
        })

        return {'success': True, 'message': 'Transfer accepted successfully'}

    @http.route('/cash/transfer/amount/reject', type='json', auth='user', methods=['POST'])
    def cash_transfer_amount_reject(self, transfer_number, reject_reason):
        """Reject a pending cash transfer"""
        user = request.env.user
        cash_transfer_model = request.env['cash.transfer'].sudo()

        # Find the transfer
        cash_transfer = cash_transfer_model.search([
            ('name', '=', transfer_number),
            ('state', '=', 'submit'),
        ], limit=1)

        if not cash_transfer:
            return {'error': 'Transfer not found or already processed'}

        # Update transfer status - DO NOT create accept record for rejections
        cash_transfer.write({
            'state': 'rejected',
            'rejected_by': user.id,
            'reject_reason': reject_reason or 'No reason provided',
        })

        # The rejected transfer amount should go back to the sender's pending amount
        # This is handled automatically by the compute field in cash_denomination
        # since we filter by state in the calculation

        return {'success': True, 'message': 'Transfer rejected successfully'}

    @http.route('/get/my/transfers', type='json', auth='user', methods=['POST'])
    def get_my_transfers(self, counter_id=None):
        """Get transfers made by the current user"""
        user = request.env.user
        cash_transfer_model = request.env['cash.transfer'].sudo()

        domain = [('from_user', '=', user.id)]
        if counter_id:
            domain.append(('from_location', '=', int(counter_id)))

        transfers = cash_transfer_model.search(domain, order='id desc', limit=20)

        transfer_list = []
        for transfer in transfers:
            transfer_list.append({
                'id': transfer.id,
                'name': transfer.name,
                'to_counter': transfer.to_location.bill_counter,
                'date': str(transfer.date),
                'grand_total': transfer.grand_total,
                'state': transfer.state,
                'reject_reason': transfer.reject_reason or '',
            })

        return {'transfer_list': transfer_list}
