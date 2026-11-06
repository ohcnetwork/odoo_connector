import json

from odoo import http
from odoo.http import request

from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.account_move import VendorBillApiRequest
from ..resources.vendor_bill import VendorBillUtility


class VendorBill(http.Controller):
    """Care moving a completed delivery order back to draft or cancelling it, and reading posted bills back."""

    @http.route('/api/account/move/vendor-bill/reopen', type='http', auth='public', methods=['POST'], csrf=False)
    def reopen_vendor_bill(self, **kwargs):
        return self._respond(VendorBillUtility.reopen)

    @http.route('/api/account/move/vendor-bill/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    def cancel_vendor_bill(self, **kwargs):
        return self._respond(VendorBillUtility.cancel)

    @http.route('/api/account/move/vendor-bill/lines', type='http', auth='public', methods=['GET'], csrf=False)
    def posted_vendor_bill_lines(self, after_id=0, limit=2000, **kwargs):
        """
        Lines of posted vendor bills that came from Care, a page at a time. Care stores their cost on its
        receipt lines to value stock. To read them all, ask again with `after_id` set to `next_after_id`
        until it is null.
        """
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            limit = int(limit)
            lines = VendorBillUtility.posted_lines(user_env, int(after_id), limit)

            json_response = {
                "success": True,
                "lines": lines,
                # None once this page was the last
                "next_after_id": lines[-1]["id"] if len(lines) == limit else None,
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
