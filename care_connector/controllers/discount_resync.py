import json

from odoo import http
from odoo.http import request

from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.discount_resync import DiscountResyncApiRequest
from ..resources.discount_resync import DiscountResyncUtility


class DiscountResync(http.Controller):

    @http.route('/api/account/move/resync_discounts', type='http', auth='public', methods=['POST'], csrf=False)
    def resync_discounts(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            DiscountResyncUtility.check_enabled(user_env)
            data = json.loads(request.httprequest.data)
            request_data = DiscountResyncApiRequest(**data)
            results = DiscountResyncUtility.resync(user_env, request_data)

            json_response = {
                "success": True,
                "dry_run": request_data.dry_run,
                "all_or_nothing": request_data.all_or_nothing,
                "results": results,
            }
            return request.make_json_response(json_response, status=200)

        except PermissionError as e:
            error_response = {
                "success": False,
                "error_type": "PermissionError",
                "message": str(e),
            }
            return request.make_json_response(error_response, status=403)

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
