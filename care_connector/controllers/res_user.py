import json
from odoo import http
from odoo.http import request
from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.res_user import UserData
from ..resources.res_user import UserUtility


class ResUserController(http.Controller):
    @http.route(
        "/api/add/user", type="http", auth="public", methods=["POST"], csrf=False
    )
    def create_user(self, **kwargs):
        """API endpoint to create or update a res.users record"""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            data = json.loads(request.httprequest.data)
            request_data = UserData(**data)
            res_user = UserUtility.get_or_create_user(user_env, request_data)

            if res_user and "error" in res_user:
                raise ValueError(res_user["error"])

            if not res_user.id:
                raise ValueError(f"Failed to create user, err: {str(res_user)}")

            json_response = {
                "success": True,
                "message": "User created successfully",
                "user": {
                    "user_id": res_user.id,
                    "login": res_user.login,
                    "name": res_user.name,
                    "email": res_user.email,
                    "x_care_id": res_user.x_care_id,
                },
            }
            return request.make_json_response(json_response, status=200)

        except ValueError as e:
            error_response = {
                "success": False,
                "message": str(e),
            }
            return request.make_json_response(error_response, status=400)

        except Exception as err:
            error_response = {
                "success": False,
                "message": str(err),
            }
            return request.make_json_response(error_response, status=500)
