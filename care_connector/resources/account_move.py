from datetime import datetime
from .res_partner import PartnerUtility
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
            if isinstance(res_partner, dict) and "error" in res_partner:
                raise ValueError(res_partner["error"])
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

            is_refund = getattr(request_data, "is_refund", False)

            if is_refund:
                # Credit note types
                move_type = "out_refund"
                if bill_type == "vendor":
                    move_type = "in_refund"
            else:
                # Invoice types
                move_type = "out_invoice"
                if bill_type == "vendor":
                    move_type = "in_invoice"

            bill_number = request_data.bill_number
            bill_date = request_data.bill_date

            move_data_dict = {
                "x_care_id": x_care_id,
                "name": invoice_number,
                "bill_number": bill_number,
                "bill_date": bill_date,
                "res_partner": res_partner,
                "invoice_items": invoice_items,
                "invoice_date": invoice_date,
                "due_date": due_date,
                "move_type": move_type,
                "doctor": request_data.doctor,
                "room_number": request_data.room_number,
                "admission_date": request_data.admission_date,
                "discharge_date": request_data.discharge_date,
                "x_account": request_data.x_account,
                "ip_bill_no": request_data.ip_bill_no,
            }
            account_move = cls._create_account_move(user_env, move_data_dict)
            if not account_move:
                raise ValueError("Failed to create the Invoice")

            if insurance_tag:
                settings = user_env["res.config.settings"].sudo().get_values()
                setting_tag = settings.get("insurance_tag_setting")
                if setting_tag and setting_tag in insurance_tag:
                    account_move.write({"insurance_tag": setting_tag})

            if x_identifier or x_created_by or payment_reference:
                account_move.write(
                    {
                        "x_identifier": x_identifier,
                        "x_created_by": x_created_by,
                        "payment_reference": payment_reference,
                    }
                )

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
                if isinstance(res_partner, dict) and "error" in res_partner:
                    raise ValueError(res_partner["error"])
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
            bill_number = move_data.get("bill_number")
            bill_date = move_data.get("bill_date")
            res_partner = move_data.get("res_partner")
            invoice_items = move_data.get("invoice_items")
            invoice_date = move_data.get("invoice_date")
            due_date = move_data.get("due_date")
            move_type = move_data.get("move_type")
            account_move_model = user_env["account.move"]

            invoice_line_list = []
            for item in invoice_items:
                # Calculate discount info using native discount field
                discount_info = cls._calculate_discount(
                    user_env, item.discounts, item.sale_price
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

                commission_user_id = False
                if item.agent_id:
                    res_users_model = user_env["res.users"]
                    commission_user = res_users_model.search(
                        [("x_care_id", "=", item.agent_id)], limit=1
                    )
                    if commission_user:
                        commission_user_id = commission_user.id

                billed_qty, free_qty = cls._calculate_quantities(
                    item.quantity, item.free_qty, move_type
                )

                # For credit notes, ensure price_unit is positive
                # Odoo handles the sign internally based on move_type
                price_unit = item.sale_price
                if move_type in ("out_refund", "in_refund") and price_unit < 0:
                    price_unit = abs(price_unit)

                invoice_line_vals = {
                    "product_id": product.id,
                    "quantity": billed_qty,
                    "received_qty": item.quantity,
                    "free_qty": free_qty,
                    "price_unit": price_unit,
                    "x_care_id": item.x_care_id,
                    "discount": discount_info.get(
                        "discount_percent", 0.0
                    ),  # Native Odoo discount field
                }

                # Add discount group if available
                if discount_info.get("discount_group_id"):
                    invoice_line_vals["discount_group_id"] = discount_info[
                        "discount_group_id"
                    ]

                if commission_user_id:
                    invoice_line_vals["commission_user_id"] = commission_user_id

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

            # Get invoice rounding setting
            icp = user_env["ir.config_parameter"].sudo()
            rounding_id = icp.get_param(
                "care_connector.invoice_cash_rounding_id", default=False
            )

            move_vals = {
                "move_type": move_type,
                "partner_id": res_partner.id,
                "x_care_id": x_care_id,
                "invoice_date": invoice_date,
                "invoice_date_due": due_date,
                "invoice_line_ids": invoice_line_list,
            }

            if rounding_id:
                move_vals["invoice_cash_rounding_id"] = int(rounding_id)

            account_move = account_move_model.create(move_vals)
            if not account_move:
                raise ValueError("Failed to create the Invoice")

            if name:
                account_move.write({"name": name})

            # Set bill_number (as reference) and bill_date for vendor bills
            if move_type in ("in_invoice", "in_refund"):
                vendor_bill_updates = {}
                if bill_number:
                    vendor_bill_updates["ref"] = bill_number
                if bill_date:
                    vendor_bill_updates["invoice_date"] = datetime.strptime(
                        bill_date, "%d-%m-%Y"
                    ).date()
                if vendor_bill_updates:
                    account_move.write(vendor_bill_updates)

            # Set doctor, hospital dates, room number, and account
            doctor = move_data.get("doctor")
            room_number = move_data.get("room_number")
            admission_date = move_data.get("admission_date")
            discharge_date = move_data.get("discharge_date")
            x_account = move_data.get("x_account")
            ip_bill_no = move_data.get("ip_bill_no")

            hospital_fields = {}
            if doctor:
                hospital_fields["doctor"] = doctor
            if room_number:
                hospital_fields["room_number"] = room_number
            if admission_date:
                hospital_fields["admission_date"] = datetime.strptime(
                    admission_date, "%d-%m-%Y %H:%M:%S"
                )
            if discharge_date:
                hospital_fields["discharge_date"] = datetime.strptime(
                    discharge_date, "%d-%m-%Y %H:%M:%S"
                )
            if x_account:
                hospital_fields["x_account"] = x_account
            if ip_bill_no:
                hospital_fields["ip_bill_no"] = ip_bill_no
            if hospital_fields:
                account_move.write(hospital_fields)

            if move_type in ("out_invoice", "out_refund"):
                account_move.action_post()
            return account_move

        except Exception as e:
            raise Exception(f"{str(e)}")

    @classmethod
    def _calculate_discount(cls, user_env, discount_data, price_unit):
        """
        Calculate total discount percentage for native Odoo discount field.

        Args:
            user_env: Odoo environment
            discount_data: List of discount objects from Care
            price_unit: Unit price of the product (for converting fixed amounts to %)

        Returns:
            dict with 'discount_percent' and optionally 'discount_group_id'
        """
        if not discount_data:
            return {"discount_percent": 0.0}

        try:
            discount_group_model = user_env["account.discount.group"]
            total_discount_percent = 0.0
            group_id = None

            for disc in discount_data:
                disc_type = disc.discount_type.value

                # Get or create discount group for tracking
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

                # Calculate discount percentage
                if disc_type == "factor":
                    # Already a percentage
                    total_discount_percent += disc.rate
                elif disc_type == "amount" and price_unit > 0:
                    # Convert fixed amount to percentage
                    percent = (disc.rate / price_unit) * 100
                    total_discount_percent += percent

            # Cap at 100%
            total_discount_percent = min(total_discount_percent, 100.0)

            result = {"discount_percent": round(total_discount_percent, 2)}
            if group_id:
                result["discount_group_id"] = group_id

            return result

        except Exception as e:
            raise Exception(f"Error calculating discount: {str(e)}")

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
            partial_reconcile_model = user_env["account.partial.reconcile"]
            account_move_model = user_env["account.move"]
            existing_invoice = account_move_model.search(
                [("x_care_id", "=", x_care_id)], limit=1
            )

            if not existing_invoice:
                raise ValueError(f"No Invoice exists for id {x_care_id}")

            partial_recs = partial_reconcile_model.search(
                [
                    "|",
                    ("debit_move_id.move_id", "=", existing_invoice.id),
                    ("credit_move_id.move_id", "=", existing_invoice.id),
                ]
            )

            if partial_recs:
                partial_recs.unlink()

            if existing_invoice.state == "posted":
                existing_invoice.button_draft()

            existing_invoice.button_cancel()

            return existing_invoice

        except Exception as e:
            raise Exception(f"{str(e)}")
