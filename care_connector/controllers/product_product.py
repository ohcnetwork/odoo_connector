import json
from odoo import http
from odoo.http import request, Response
from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.product_product import ProductData
from ..resources.product_product import ProductUtility


class ProductProduct(http.Controller):

    @http.route('/api/add/product', type='http', auth='public', methods=['POST'], csrf=False)
    def create_update_product(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = ProductData(**data)
            product_product = ProductUtility.get_or_create_product(user_env, request_data)

            if not product_product.id:
                raise ValueError(f"Failed to create the product, err:{str(product_product)}")

            json_response = {
                "success": True,
                "message": "Product created successfully",
                "product": {
                    "product_id": product_product.id,
                    "product_name": product_product.name,
                    "x_care_id": product_product.x_care_id,
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