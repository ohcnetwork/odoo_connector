import json
from odoo.http import request, Response
from odoo import http
from ..authentication.authenticate_user import UserAuthentication
from ..resources.account_account import ChartOfAccountUtility
from ..pydantic_models.account_move import AccountPaymentMethodApiRequest


class AccountAccount(http.Controller):

    @http.route('/api/get/all/payment/methods', type='http', auth='public', methods=['GET'], csrf=False)
    def account_payment_methods(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            account_payment_method_list = ChartOfAccountUtility.get_all_account_payment_method(user_env)
            if not account_payment_method_list:
                raise ValueError("Failed to get the Accounts Payment Method List")

            json_response = {
                "success": True,
                "message": "Fetched all payment methods",
                "payment_methods": account_payment_method_list
            }
            return request.make_json_response(json_response, status=200)


        except Exception as err:
            error_response = {
                "success": False,
                "error_type": "ServerError",
                "message": str(err),
            }
            return request.make_json_response(error_response, status=500)

    @http.route('/api/v1/payment/method/<int:method_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_account_payment_method_by_id(self, method_id):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            if not method_id:
                raise ValueError("Payment method id is missing")

            account_payment_method = ChartOfAccountUtility.get_account_payment_method_by_id(user_env, method_id)

            if not account_payment_method.exists():
                error_response = {
                    "success": False,
                    "error_type": "ValueError",
                    "message": f"Failed to fetch payment method with id  {method_id}",
                }
                return request.make_json_response(error_response, status=400)

            json_response = {
                "success": True,
                "message": "Payment Method Fetched successfully",
                "payment_method": {
                    "id": account_payment_method.id,
                    "name": account_payment_method.name
                }
            }
            return request.make_json_response(json_response, status=200)

        except Exception as e:
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers={'Content-Type': 'application/json'}
            )

    @http.route('/api/accounts/search', type='http', auth='public', methods=['GET'], csrf=False)
    def search_account_payment_method_by_name(self, **post):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = AccountPaymentMethodApiRequest(**data)
            account_payment_method = ChartOfAccountUtility.get_account_payment_method_by_name(user_env, request_data)
            if not account_payment_method:
                error_response = {
                    "success": False,
                    "error_type": "ValueError",
                    "message": f"No Payment Method with Name  {request_data.search_key}",
                }
                return request.make_json_response(error_response, status=400)

            json_response = {
                "status": True,
                "count": len(account_payment_method),
                "payment_methods": account_payment_method
            }
            return request.make_json_response(json_response, status=200)

        except Exception as e:
            return {"status": False, "error": str(e)}