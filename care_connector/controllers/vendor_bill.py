import json

from odoo import http
from odoo.http import request

from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.account_move import VendorBillApiRequest
from ..resources.vendor_bill import VendorBillUtility


class VendorBill(http.Controller):
    """Care moving a completed delivery order back to draft, or cancelling it."""

    @http.route('/api/account/move/vendor-bill/reopen', type='http', auth='public', methods=['POST'], csrf=False)
    def reopen_vendor_bill(self, **kwargs):
        return self._respond(VendorBillUtility.reopen)

    @http.route('/api/account/move/vendor-bill/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    def cancel_vendor_bill(self, **kwargs):
        return self._respond(VendorBillUtility.cancel)

    def _respond(self, action):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = VendorBillApiRequest.model_validate(data)
            move = action(user_env, request_data)

            json_response = {
                "success": True,
                # None when the order never had a bill, e.g. it was never completed
                "invoice": {
                    "id": move.id,
                    "name": move.name,
                    "state": move.state,
                }
                if move
                else None,
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
                "message": str(err),
            }
            return request.make_json_response(error_response, status=500)
