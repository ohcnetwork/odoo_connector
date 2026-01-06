from datetime import datetime
from odoo import http,registry, fields
from .res_partner import PartnerUtility


class InvoicePaymentUtility:

    @classmethod
    def get_or_create_invoice_payment(cls,user_env,request_data):
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
            account_move_model = user_env["account.move"]
            account_journal_model = user_env['account.journal']
            account_payment_model = user_env['account.payment']
            a_p_r_transient_model = user_env['account.payment.register']

            bill_counter = cls.get_or_create_bill_counter(user_env, counter_data)
            existing_payment = account_payment_model.search([('x_care_id', '=', x_care_id)], limit=1)
            if existing_payment:
                raise ValueError(f"'{x_care_id}' already paid")

            account_journal = account_journal_model.sudo().search([
                '|', '|',
                ('name', 'ilike', journal_input),
                ('code', 'ilike', journal_input),
                ('type', '=', journal_input.lower())
            ], limit=1)

            if not account_journal:
                raise ValueError(f"No journal found for '{journal_input}'")
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

                account_payment = a_p_r_transient_model.with_context(ctx).create({
                    'amount': amount,
                    'journal_id': account_journal.id,
                    'payment_date': payment_date or fields.Date.today(),
                    'bank_reference': bank_reference
                })._create_payments()
                if not account_payment:
                    raise ValueError(f"Payment creation failed")
                account_payment.x_care_id = x_care_id
                account_payment.location = bill_counter.get('bill_counter_id')
                account_payment.cashier = bill_counter.get('user_id')

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
    def _cancel_invoice_payment(cls, user_env, request_data):
        try:
            x_care_id = request_data.x_care_id
            reason = request_data.reason
            account_payment_model = user_env['account.payment']
            a_m_r_model = user_env['account.move.reversal']
            account_move_model = user_env["account.move"]
            existing_payment = account_payment_model.search([('x_care_id', '=', x_care_id)], limit=1)

            if not existing_payment:
                raise ValueError(f"No payment found with x_care_id: {x_care_id}")

            if existing_payment.cancel_status:
                raise ValueError(f"{x_care_id} payment Already cancelled  ")

            journal_entry = existing_payment.move_id
            if not journal_entry:
                raise ValueError("No journal entry linked to this payment.")

            reversal_wizard = a_m_r_model.with_context(
                active_model='account.move',
                active_ids=[journal_entry.id]
            ).create({
                'reason': reason,
                'journal_id': journal_entry.journal_id.id,
                'date': fields.Date.today(),
            })
            reversal_wizard.reverse_moves()

            reversed_move = account_move_model.search([
                ('reversed_entry_id', '=', journal_entry.id)
            ], limit=1)
            if not reversed_move:
                raise ValueError("Reversal failed — no reversed move created.")

            existing_payment.cancel_status = True
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
