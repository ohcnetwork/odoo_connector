import json
from odoo import http
from odoo.http import request, Response
from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.account_move_payment import AccountMovePaymentApiRequest,AccountPaymentCancelApiRequest
from ..resources.account_move_payment import InvoicePaymentUtility


class AccountMovePayment(http.Controller):
    @http.route('/api/account/move/payment', type='http', auth='public', methods=['POST'], csrf=False)
    def account_move_payment(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = AccountMovePaymentApiRequest(**data)
            account_payment = InvoicePaymentUtility.get_or_create_invoice_payment(user_env, request_data)

            if not account_payment.id:
                raise ValueError(f"Failed to create the payment, error: {str(account_payment)}")

            json_response = {
                "success": True,
                "message": "Payment processed successfully",
                "payment": {
                    "id": account_payment.id,
                    "name": account_payment.name,
                    "amount": account_payment.amount,
                    "partner": account_payment.partner_id.name,
                    "journal": account_payment.journal_id.name,
                    "payment_type": account_payment.payment_type,
                    "state": account_payment.state,
                    "date": str(account_payment.date),
                },
            }

            return request.make_json_response(json_response, status=200)

        except ValueError as e:
            error_response = {
                "success": False,
                "error_type": "ValueError",
                "message": str(e),
            }
            return request.make_json_response(error_response, status=400)

        except Exception as err:
            error_response = {
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}",
            }
            return request.make_json_response(error_response, status=500)



    @http.route('/api/account/move/payment/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    def account_move_payment_cancel(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = AccountPaymentCancelApiRequest(**data)
            account_payment = InvoicePaymentUtility._cancel_invoice_payment(user_env, request_data)

            if not account_payment.id:
                raise ValueError(f"Failed to create the payment, error: {str(account_payment)}")

            json_response = {
                "success": True,
                "message": "Payment Cancelled successfully",
                "payment": {
                    "id": account_payment.id,
                    "name": account_payment.name,
                    "amount": account_payment.amount,
                    "partner": account_payment.partner_id.name,
                    "journal": account_payment.journal_id.name,
                    "payment_type": account_payment.payment_type,
                    "state": account_payment.state,
                    "date": str(account_payment.date),
                },
            }

            return request.make_json_response(json_response, status=200)

        except ValueError as e:
            error_response = {
                "success": False,
                "error_type": "ValueError",
                "message": str(e),
            }
            return request.make_json_response(error_response, status=400)

        except Exception as err:
            error_response = {
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}",
            }
            return request.make_json_response(error_response, status=500)