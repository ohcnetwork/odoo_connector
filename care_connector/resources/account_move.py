from datetime import datetime
from .res_partner import PartnerUtility
from .account_account import ChartOfAccountUtility
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AccountUtility:
    @classmethod
    def get_or_create_account_move(cls, user_env, request_data):
        try:
            x_care_id = request_data.x_care_id
            partner_data = request_data.partner_data
            invoice_items = request_data.invoice_items
            insurance_tag = request_data.insurance_tag
            payment_method_id = request_data.payment_method_id
            x_identifier = request_data.x_identifier
            x_created_by = request_data.x_created_by
            payment_reference = request_data.payment_reference

            account_move = user_env["account.move"]
            existing_invoice = account_move.search(
                [("x_care_id", "=", x_care_id)], limit=1
            )

            if existing_invoice:
                raise ValueError("Invoice already exists")

            res_partner = PartnerUtility.get_or_create_partner(user_env, partner_data)
            bill_type = request_data.bill_type.value
            invoice_date = request_data.invoice_date
            due_date = request_data.due_date
            invoice_number = request_data.invoice_number
            if invoice_number:
                existing_invoice = account_move.search(
                    [("name", "=", invoice_number)], limit=1
                )
                if existing_invoice:
                    raise ValueError(
                        f"Invoice already exists with name {invoice_number}"
                    )

            move_type = "out_invoice"
            if bill_type == "vendor":
                move_type = "in_invoice"

            move_data_dict = {
                "x_care_id": x_care_id,
                "name": invoice_number,
                "res_partner": res_partner,
                "invoice_items": invoice_items,
                "invoice_date": invoice_date,
                "due_date": due_date,
                "move_type": move_type,
            }
            account_move = cls._create_account_move(user_env, move_data_dict)
            if not account_move:
                raise ValueError("Failed to create the Invoice")

            if insurance_tag:
                settings = user_env['res.config.settings'].sudo().get_values()
                setting_tag = settings.get('insurance_tag_setting')
                if setting_tag and setting_tag in insurance_tag:
                    account_move.write({
                        'insurance_tag': setting_tag
                    })

            if payment_method_id:
                account_payment_method_line_model = user_env["account.payment.method.line"]
                account_payment_method = account_payment_method_line_model.search([
                    ("id", "=", int(payment_method_id))], limit=1)
                if not account_payment_method.id:
                    raise ValueError(account_payment_method)
                account_move.write({
                    'preferred_payment_method_line_id': account_payment_method.id
                })

            if x_identifier or x_created_by or payment_reference:
                account_move.write({
                    'x_identifier': x_identifier,
                    'x_created_by': x_created_by,
                    'payment_reference': payment_reference,
                })

            return account_move
        except Exception as e:
            raise Exception(f"{str(e)}")

    @classmethod
    def get_or_create_account_move_return(cls, user_env, request_data):
        try:
            x_care_id = request_data.x_care_id
            partner_data = request_data.partner_data
            invoice_items = request_data.invoice_items
            reason = request_data.reason if request_data.reason else None
            account_move = user_env["account.move"]
            a_m_r_model = user_env["account.move.reversal"]
            existing_invoice = account_move.search(
                [("x_care_id", "=", x_care_id)], limit=1
            )

            if existing_invoice:
                existing_credit_note = account_move.search(
                    [("reversed_entry_id", "=", existing_invoice.id)], limit=1
                )
                if existing_credit_note:
                    raise ValueError(
                        f"This invoice has already been reversed and a credit note [{str(existing_credit_note.name)}] exists."
                    )

                reversal_wizard = a_m_r_model.with_context(
                    {
                        "active_ids": [existing_invoice.id],
                        "active_id": existing_invoice.id,
                        "active_model": "account.move",
                    }
                ).create(
                    {
                        "reason": reason,
                        "journal_id": existing_invoice.journal_id.id,
                    }
                )
                if not reversal_wizard:
                    raise ValueError("Failed to reverse the Invoice")
                reversal_wizard.reverse_moves()

                credit_note = account_move.search(
                    [
                        ("reversed_entry_id", "=", existing_invoice.id),
                        ("move_type", "in", ["out_refund", "in_refund"]),
                    ],
                    limit=1,
                )

                if not credit_note:
                    raise ValueError("Failed to create Credit note")

                credit_note.x_care_id = f"RE/{credit_note.x_care_id}"
                credit_note.action_post()
                return credit_note

            else:
                res_partner = PartnerUtility.get_or_create_partner(
                    user_env, partner_data
                )
                bill_type = request_data.bill_type.value
                invoice_date = request_data.invoice_date
                due_date = request_data.due_date

                move_type = "out_refund"
                if bill_type == "vendor":
                    move_type = "in_refund"

                move_data_dict = {
                    "x_care_id": x_care_id,
                    "res_partner": res_partner,
                    "invoice_items": invoice_items,
                    "invoice_date": invoice_date,
                    "due_date": due_date,
                    "move_type": move_type,
                }
                account_move = cls._create_account_move(user_env, move_data_dict)
                if not account_move.id:
                    raise ValueError(
                        f"Failed to create the Invoice, err:{str(account_move)}"
                    )
                return {
                    "success": True,
                    "invoice_id": account_move.id,
                    "invoice_name": account_move.name,
                }

        except Exception as e:
            raise Exception(f"{str(e)}")

    @classmethod
    def _create_account_move(cls, user_env, move_data):
        try:
            x_care_id = move_data.get("x_care_id")
            name = move_data.get("name")
            res_partner = move_data.get("res_partner")
            invoice_items = move_data.get("invoice_items")
            invoice_date = move_data.get("invoice_date")
            due_date = move_data.get("due_date")
            move_type = move_data.get("move_type")
            account_move_model = user_env["account.move"]
            res_partner_model = user_env["res.partner"]

            invoice_line_list = []
            for item in invoice_items:
                discount_ids = []
                if item.discounts:
                    discount_ids = cls._get_or_create_discounts(
                        user_env, item.discounts
                    )
                product_data = item.product_data
                product_product_model = user_env["product.product"]
                product = product_product_model.search(
                    [("x_care_id", "=", product_data.x_care_id)], limit=1
                )
                if not product:
                    raise ValueError(
                        f"Product with id {product_data.x_care_id} is not exists"
                    )

                agent_ids = []
                if item.agent_id:
                    agent_res_partner = res_partner_model.search(
                        [("x_care_id", "=", item.agent_id)], limit=1
                    )
                    if agent_res_partner and agent_res_partner.agent:
                        agent_ids = [
                            (
                                0,
                                0,
                                {
                                    "agent_id": agent_res_partner.id,
                                    "commission_id": agent_res_partner.commission_id.id
                                    if agent_res_partner.commission_id
                                    else False,
                                },
                            )
                        ]

                billed_qty, free_qty = cls._calculate_quantities(
                    item.quantity, item.free_qty, move_type
                )

                invoice_line_vals = {
                    "product_id": product.id,
                    "quantity": billed_qty,
                    "received_qty": item.quantity,
                    "free_qty": free_qty,
                    "price_unit": item.sale_price,
                    "x_care_id": item.x_care_id,
                    "agent_ids": agent_ids,
                    "account_discount": discount_ids,
                }

                move_line_model = user_env["account.move.line"]
                missing_fields = [
                    f
                    for f in invoice_line_vals.keys()
                    if f not in move_line_model._fields
                ]

                if missing_fields:
                    raise UserError(
                        _(
                            "Invoice creation failed. The following required fields are missing: "
                            "%s"
                        )
                        % ", ".join(missing_fields)
                    )

                invoice_line_list.append((0, 0, invoice_line_vals))

            invoice_date = datetime.strptime(invoice_date, "%d-%m-%Y").date()
            due_date = datetime.strptime(due_date, "%d-%m-%Y").date()
            account_move = account_move_model.create(
                {
                    "move_type": move_type,
                    "partner_id": res_partner.id,
                    "x_care_id": x_care_id,
                    "invoice_date": invoice_date,
                    "invoice_date_due": due_date,
                    "invoice_line_ids": invoice_line_list,
                }
            )
            if not account_move:
                raise ValueError("Failed to create the Invoice")

            if name:
                account_move.write({"name": name})
            if move_type == "out_invoice":
                account_move.action_post()
            return account_move

        except Exception as e:
            raise Exception(f"{str(e)}")

    @classmethod
    def _get_or_create_discounts(cls, user_env, discount_data):
        try:
            discount_group_model = user_env["account.discount.groups"]
            product_template_model = user_env["product.template"]
            group_id = None
            disc_product_ids = []
            for disc in discount_data:
                disc_type = disc.discount_type.value
                if disc.discount_group:
                    group = disc.discount_group
                    discount_group = discount_group_model.search(
                        [("x_care_id", "=", group.x_care_id)], limit=1
                    )

                    if not discount_group:
                        discount_group = discount_group_model.create(
                            {"x_care_id": group.x_care_id, "name": group.name}
                        )
                    elif discount_group.name != group.name:
                        discount_group.name = group.name

                    group_id = discount_group.id
                domain = [
                    ("is_disc_item", "=", True),
                    ("discount_group", "=", group_id),
                ]

                if disc_type == "amount":
                    domain.append(("disc_amount", "=", disc.rate))
                else:
                    domain.append(("disc_percent", "=", disc.rate))

                discount_product = product_template_model.search(domain, limit=1)

                if not discount_product:
                    vals = {
                        "name": disc.name,
                        "is_disc_item": True,
                        "discount_group": group_id,
                        "list_price": disc.disc_amt,
                    }
                    if disc_type == "amount":
                        vals["disc_amount"] = disc.rate
                    else:
                        vals["disc_percent"] = disc.rate
                    discount_product = product_template_model.create(vals)

                if discount_product.list_price != disc.disc_amt:
                    discount_product.list_price = disc.disc_amt
                disc_product_ids.append(discount_product.id)

            return disc_product_ids

        except Exception as e:
            raise Exception(f"{str(e)}")

    @classmethod
    def _calculate_quantities(cls, received_qty, free_qty, move_type):
        """
        Calculate billed and free quantities based on move type.
        For vendor bills (in_invoice), billed_qty = received_qty - free_qty.
        For other types, free_qty is ignored.
        """
        if move_type != "in_invoice" or free_qty <= 0:
            return received_qty, 0.0

        if free_qty > received_qty:
            return received_qty, 0.0

        return received_qty - free_qty, free_qty

    @classmethod
    def _cancel_account_move(cls, user_env, request_data):
        try:
            x_care_id = request_data.x_care_id
            partial_reconcile_model = user_env['account.partial.reconcile']
            account_move_model = user_env["account.move"]
            existing_invoice = account_move_model.search([('x_care_id', '=', x_care_id)], limit=1)

            if not existing_invoice:
                raise ValueError(f"No Invoice exists for id {x_care_id}")

            partial_recs = partial_reconcile_model.search([
                '|',
                ('debit_move_id.move_id', '=', existing_invoice.id),
                ('credit_move_id.move_id', '=', existing_invoice.id)
            ])

            if partial_recs:
                partial_recs.unlink()

            if existing_invoice.state == 'posted':
                existing_invoice.button_draft()

            existing_invoice.button_cancel()

            return existing_invoice

        except Exception as e:
            raise Exception(f"{str(e)}")
