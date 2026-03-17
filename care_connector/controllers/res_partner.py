import json
from odoo import http
from odoo.http import request, Response
from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.res_partner import PartnerData
from ..resources.res_partner import PartnerUtility


class ResPartner(http.Controller):
    @http.route(
        "/api/add/partner", type="http", auth="public", methods=["POST"], csrf=False
    )
    def create_update_partner(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = PartnerData(**data)
            res_partner = PartnerUtility.get_or_create_partner(user_env, request_data)

            if res_partner and "error" in res_partner:
                raise ValueError(res_partner["error"])

            if not res_partner.id:
                raise ValueError(f"Failed to create partner, err: {str(res_partner)}")

            json_response = {
                "success": True,
                "message": "Partner created successfully",
                "partner": {
                    "partner_id": res_partner.id,
                    "partner_name": res_partner.name,
                    "x_care_id": res_partner.x_care_id,
                    "x_care_id_type": "vendor",
                    "ref": res_partner.ref,
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
