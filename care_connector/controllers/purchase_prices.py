from pydantic import ValidationError as SchemaError

from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request

from ..authentication.authenticate_user import UserAuthentication
from ..resources.purchase_prices import PurchasePrices


class CarePurchasePrices(http.Controller):
    @http.route(
        "/api/purchases/monthly-prices",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def monthly_prices(self, **kwargs):
        return self.respond(PurchasePrices.read, kwargs)

    @http.route(
        "/api/purchases/metadata",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def purchase_metadata(self, **kwargs):
        return self.respond(PurchasePrices.metadata)

    @staticmethod
    def respond(action, data=None):
        try:
            env = UserAuthentication.get_authenticated_user(
                request.httprequest.headers.get("Authorization")
            )
        except ValueError:
            return request.make_json_response(
                {
                    "success": False,
                    "message": "Valid Basic authentication is required.",
                },
                status=401,
                headers={"WWW-Authenticate": 'Basic realm="Care purchases"'},
            )
        try:
            if data is None:
                data = request.get_json_data()
            if not isinstance(data, dict):
                raise ValidationError("The purchase request must be a JSON object.")
            with env.cr.savepoint():
                result = action(env, data)
            return request.make_json_response(
                {"success": True, **result}, headers={"Cache-Control": "no-store"}
            )
        except AccessError as error:
            return request.make_json_response(
                {"success": False, "message": str(error)}, status=403
            )
        except (ValidationError, SchemaError, ValueError) as error:
            return request.make_json_response(
                {"success": False, "message": str(error)}, status=400
            )
