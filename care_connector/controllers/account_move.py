import json
from odoo.http import request, Response
from odoo import http
from ..pydantic_models.account_move import AccountMoveApiRequest,AccountMoveReturnApiRequest,BillType
from ..authentication.authenticate_user import UserAuthentication
from ..resources.account_move import AccountUtility
from ..resources.vendor_bill import VendorBillUtility

class AccountMove(http.Controller):

    @http.route('/api/account/move', type='http', auth='public', methods=['POST'], csrf=False)
    def account_move(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = AccountMoveApiRequest(**data)
            # Care completes a delivery order again after moving it back to draft, so its bill may already exist
            if request_data.bill_type == BillType.vendor and not request_data.is_refund:
                account_move = VendorBillUtility.create_or_update(user_env, request_data)
            else:
                account_move = AccountUtility.get_or_create_account_move(user_env, request_data)

            if not account_move.id:
                raise ValueError(f"Failed to create/retrieve the Invoice, {str(account_move)}")

            json_response = {
                "success": True,
                "message": "Invoice created successfully",
                "invoice": {
                    "id": account_move.id,
                    "name": account_move.name,
                    "partner": account_move.partner_id.name,
                    "invoice_date": str(account_move.invoice_date),
                    "amount_total": account_move.amount_total,
                    # grn_number comes from grn_number_in_vendor_bill, which may not be installed
                    "grn_number": (account_move["grn_number"] or None)
                    if "grn_number" in account_move._fields
                    else None,
                }
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
                "message":str(err),
            }
            return request.make_json_response(error_response, status=500)

    @http.route('/api/account/move/return', type='http', auth='public', methods=['POST'], csrf=False)
    def account_move_return(self, **kwargs):
        try:
            
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = AccountMoveReturnApiRequest(**data)

            account_move = AccountUtility._cancel_account_move(user_env, request_data)
            if not account_move.id:
                raise ValueError(f"Failed to cancel the Invoice, {str(account_move)}")

            json_response = {
                "success": True,
                "message": "Invoice cancelled successfully",
                "invoice": {
                    "id": account_move.id,
                    "name": account_move.name,
                    "partner": account_move.partner_id.name,
                }
            }
            return request.make_json_response(json_response, status=200)
        except Exception as e:
            error_response = {
                "success": False,
                "error_type": "ServerError",
                "message": str(e),
            }
            return request.make_json_response(error_response, status=500)
