from datetime import datetime
from odoo import http, fields
from .res_partner import PartnerUtility
from .payment_method_line import PaymentMethodLineUtility


class InvoicePaymentUtility:

    @classmethod
    def get_or_create_invoice_payment(cls, user_env, request_data):
        try:
            x_care_id = request_data.x_care_id
            journal_x_care_id = request_data.journal_x_care_id
            amount = request_data.amount
            journal_input = request_data.journal_input.value
            payment_date = request_data.payment_date
            partner_data = request_data.partner_data
            payment_mode = request_data.payment_mode
            customer_type = request_data.customer_type
            counter_data = request_data.counter_data
            bank_reference = request_data.bank_reference
            payment_method_line_id = request_data.payment_method_line_id
            account_move_model = user_env["account.move"]
            account_journal_model = user_env['account.journal']
            account_payment_model = user_env['account.payment']
            a_p_r_transient_model = user_env['account.payment.register']

            bill_counter = cls.get_or_create_bill_counter(user_env, counter_data)
            existing_payment = account_payment_model.search([('x_care_id', '=', x_care_id)], limit=1)
            if existing_payment:
                raise ValueError(f"'{x_care_id}' already paid")

            account_journal = account_journal_model.sudo().search([
                ('x_care_journal_code', '=', journal_input.lower())
            ], limit=1)

            # If no journal found by care code, check if this maps to a payment method line
            # (e.g. 'card' and 'debit' are configured as payment method lines on a bank journal)
            payment_method_line = None
            if not account_journal:
                pml, journal_from_pml = PaymentMethodLineUtility.get_payment_method_line_by_care_code(
                    user_env, journal_input.lower()
                )
                if pml and journal_from_pml:
                    account_journal = journal_from_pml
                    payment_method_line = pml

            if not account_journal:
                raise ValueError(
                    f"No journal or payment method configured for Care Connector code '{journal_input}'. "
                    f"Please set the 'Care Connector Code' on the appropriate journal "
                    f"or the 'Care Payment Code' on a payment method line."
                )

            # Validate payment_method_line_id for credit payments
            if journal_input.lower() == 'credit':
                if not payment_method_line_id:
                    raise ValueError(
                        "payment_method_line_id is required for credit (Care of Account) payments. "
                        "Use GET /api/payment/method/lines to fetch available payment methods."
                    )
                # Validate that the payment method line belongs to this journal
                payment_method_line = PaymentMethodLineUtility.validate_payment_method_line_for_journal(
                    user_env, payment_method_line_id, account_journal.id
                )

            # Find cash session if this is a cash payment
            cash_session = None
            if account_journal.type == 'cash':
                cash_session = cls._find_open_cash_session(
                    user_env,
                    counter_data.cashier_id,
                    counter_data.x_care_id
                )
                if not cash_session:
                    raise ValueError(
                        f"No open cash session for user {counter_data.cashier_id} "
                        f"at counter {counter_data.x_care_id}. Please open a session first."
                    )

            existing_invoice = None
            if journal_x_care_id:
                existing_invoice = account_move_model.search([('x_care_id', '=', journal_x_care_id)], limit=1)

            if existing_invoice:
                if existing_invoice.state != 'posted':
                    raise ValueError(f"Invoice {existing_invoice.name} is not posted")
                if existing_invoice.payment_state == 'paid':
                    raise ValueError(f"Invoice {existing_invoice.name} is already marked as paid. No further payment can be processed")

                ctx = {
                    'active_model': 'account.move',
                    'active_ids': [existing_invoice.id],
                    'active_id': existing_invoice.id,
                }

                payment_register_vals = {
                    'amount': amount,
                    'journal_id': account_journal.id,
                    'payment_date': payment_date or fields.Date.today(),
                    'bank_reference': bank_reference
                }
                # Add payment_method_line_id when resolved (credit or payment-code-based)
                if payment_method_line:
                    payment_register_vals['payment_method_line_id'] = payment_method_line.id

                account_payment = a_p_r_transient_model.with_context(ctx).create(
                    payment_register_vals
                )._create_payments()
                if not account_payment:
                    raise ValueError(f"Payment creation failed")
                account_payment.x_care_id = x_care_id
                account_payment.location = bill_counter.get('bill_counter_id')
                account_payment.cashier = bill_counter.get('user_id')
                if cash_session:
                    account_payment.cash_session_id = cash_session.id

                return account_payment

            else:
                partner = PartnerUtility.get_or_create_partner(user_env, partner_data)

                if isinstance(partner, dict) and partner.get("error"):
                    raise ValueError(f"Partner creation failed: {partner.get('error')}")

                if not partner:
                    raise ValueError(f"Create or retrieve partner is failed ")

                payment_type = 'outbound' if payment_mode.value == "send" else 'inbound'

                partner_type_str = 'supplier' if customer_type.value == 'vendor' else 'customer'
                try:
                    payment_vals = {
                        'x_care_id': x_care_id,
                        'payment_type': payment_type,
                        'partner_type': partner_type_str,
                        'partner_id': partner.id,
                        'amount': amount,
                        'journal_id': account_journal.id,
                        'date': payment_date or fields.Date.today(),
                        'location': bill_counter.get('bill_counter_id'),
                        'cashier': bill_counter.get('user_id'),
                        'bank_reference': bank_reference
                    }
                    # Add payment_method_line_id when resolved (credit or payment-code-based)
                    if payment_method_line:
                        payment_vals['payment_method_line_id'] = payment_method_line.id
                    if cash_session:
                        payment_vals['cash_session_id'] = cash_session.id
                except Exception as e:
                    raise ValueError(str(e))
                account_payment = account_payment_model.create(payment_vals)
                if not account_payment:
                    raise ValueError(f"Payment creation failed")
                account_payment.action_post()
                return account_payment

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def _find_open_cash_session(cls, user_env, external_user_id, counter_x_care_id):
        """Find an open cash session for the given user and counter."""
        cash_session_model = user_env['cash.session']
        bill_counter_model = user_env['bill.counter']

        # Find the counter
        counter = bill_counter_model.search([
            ('x_care_id', '=', counter_x_care_id)
        ], limit=1)

        if not counter:
            return None

        # Find open session
        return cash_session_model.search([
            ('external_user_id', '=', external_user_id),
            ('counter_id', '=', counter.id),
            ('status', '=', 'open')
        ], limit=1)

    @classmethod
    def _cancel_invoice_payment(cls, user_env, request_data):
        try:
            x_care_id = request_data.x_care_id
            reason = request_data.reason
            account_payment_model = user_env['account.payment']

            existing_payment = account_payment_model.search([('x_care_id', '=', x_care_id)], limit=1)

            if not existing_payment:
                raise ValueError(f"No payment found with x_care_id: {x_care_id}")

            if existing_payment.state == 'canceled':
                raise ValueError(f"{x_care_id} payment already cancelled")

            # Use Odoo's native cancellation method
            # This properly handles reconciliation and state changes
            existing_payment.action_cancel()

            return existing_payment

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def get_or_create_bill_counter(cls, user_env, counter_data):
        try:
            x_care_id = counter_data.x_care_id
            cashier_x_care_id = counter_data.cashier_id
            counter_name = counter_data.counter_name
            bill_counter_model = user_env['bill.counter']
            res_users_model = user_env['res.users']

            res_user = res_users_model.search([('partner_id.x_care_id', '=', cashier_x_care_id)], limit=1)
            bill_counter = bill_counter_model.search([('x_care_id', '=', x_care_id)], limit=1)

            if not bill_counter:
                bill_counter = bill_counter_model.create({
                    'x_care_id': x_care_id,
                    'name': [(6, 0, [res_user.id])] if res_user else [],
                    'bill_counter': counter_name,
                })
            else:
                bill_counter.bill_counter = counter_name

            if res_user and res_user.id not in bill_counter.name.ids:
                bill_counter.sudo().write({
                    'name': [(4, res_user.id)]
                })
            return {
                'bill_counter_id': bill_counter.id if bill_counter else False,
                'user_id': res_user.id if res_user else False
            }

        except Exception as e:
            raise ValueError(str(e))
