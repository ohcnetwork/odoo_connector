import json
from odoo import http,registry, fields
from odoo.http import request, Response
from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.product_category import CategoryData
from ..resources.product_category import CategoryUtility


class ProductCategory(http.Controller):

    @http.route('/api/add/category', type='http', auth='public', methods=['POST'], csrf=False)
    def create_update_category(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = CategoryData(**data)
            product_category = CategoryUtility.get_or_create_category(user_env, request_data)

            if not product_category.id:
                raise ValueError(f"Failed to create the Category, err:{str(product_category)}")

            json_response = {
                    "success": True,
                    "message": "Product created successfully",
                    "Category": {
                        "Category_id": product_category.id,
                        "product_name": product_category.name,
                        "x_care_id": product_category.x_care_id,
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