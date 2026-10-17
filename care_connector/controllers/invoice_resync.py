import json

from odoo import http
from odoo.http import request

from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.invoice_resync import InvoiceResyncApiRequest
from ..resources.invoice_resync import InvoiceResyncUtility


class InvoiceResync(http.Controller):

    @http.route('/api/account/move/resync', type='http', auth='public', methods=['POST'], csrf=False)
    def resync_invoices(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            # model_validate rejects a body that isn't a JSON object (e.g. [] or null) as a 400
            request_data = InvoiceResyncApiRequest.model_validate(data)
            results = InvoiceResyncUtility.resync(user_env, request_data)

            json_response = {
                "success": True,
                "dry_run": request_data.dry_run,
                "results": results,
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
