import json
from odoo.http import request, Response
from odoo import http
from ..authentication.authenticate_user import UserAuthentication
from ..resources.account_account import ChartOfAccountUtility
from ..pydantic_models.account_move import AccountAccountApiRequest

class AccountAccount(http.Controller):

    @http.route('/api/get/all/accounts', type='http', auth='public', methods=['GET'], csrf=False)
    def account_account(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            account_account_list = ChartOfAccountUtility.get_all_account_account(user_env)
            if not account_account_list:
                raise ValueError("Failed to get the Accounts")

            json_response = {
                "success": True,
                "message": "Fetched all accounts",
                "accounts": account_account_list
            }
            return request.make_json_response(json_response, status=200)


        except Exception as err:
            error_response = {
                "success": False,
                "error_type": "ServerError",
                "message":str(err),
            }
            return request.make_json_response(error_response, status=500)





    @http.route('/api/v1/accounts/<int:account_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_account_account(self, account_id):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            if not account_id:
                raise ValueError("Account id is missing")

            account_account = ChartOfAccountUtility.get_account_account_by_id(user_env,account_id)

            if not account_account.exists():
                error_response = {
                    "success": False,
                    "error_type": "ValueError",
                    "message": f"Failed to fetch account with id  {account_id}",
                }
                return request.make_json_response(error_response, status=400)

            json_response = {
                "success": True,
                "message": "Accounts Fetched successfully",
                "accounts": {
                        "id": account_account.id,
                        "name": account_account.name,
                        "code": account_account.code,
                        "display_name": f"{account_account.code} - {account_account.name}"
                }
            }
            return request.make_json_response(json_response, status=200)

        except Exception as e:
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers={'Content-Type': 'application/json'}
            )


    @http.route('/api/accounts/search', type='http', auth='public', methods=['GET'], csrf=False)
    def search_accounts(self, **post):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = AccountAccountApiRequest(**data)
            accounts = ChartOfAccountUtility.get_accounts_by_name(user_env, request_data)
            if not accounts:
                error_response = {
                    "success": False,
                    "error_type": "ValueError",
                    "message": f"No account with Name  {request_data.search_key}",
                }
                return request.make_json_response(error_response, status=400)
            
            json_response = {
                "status": True,
                "count": len(accounts),
                "accounts": accounts
            }
            return request.make_json_response(json_response, status=200)

        except Exception as e:
            return {"status": False, "error": str(e)}