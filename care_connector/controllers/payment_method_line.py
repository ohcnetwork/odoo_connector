from odoo import http
from odoo.http import request
from ..authentication.authenticate_user import UserAuthentication
from ..resources.payment_method_line import PaymentMethodLineUtility


class PaymentMethodLineController(http.Controller):
    """Controller for fetching payment method lines (Care of Accounts / Credits).

    These endpoints allow CARE to fetch available payment methods that can be
    used for credit payments (charity, sponsor, fund payments on behalf of patients).
    """

    @http.route('/api/payment/method/lines', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payment_method_lines(self, **kwargs):
        """Fetch all inbound payment method lines for credit journals.

        Query Parameters:
            journal_type (optional): The care connector code to filter by.
                                    Defaults to 'credit'.

        Returns:
            JSON response with list of payment method lines:
            {
                "success": true,
                "payment_methods": [
                    {
                        "id": 42,
                        "name": "Rotary Charity Fund",
                        "code": "PM-CARE-ROTARY",
                        "journal_id": 14,
                        "journal_name": "Charity / Sponsorship Journal"
                    }
                ]
            }
        """
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            journal_type = kwargs.get('journal_type', 'credit')

            payment_methods = PaymentMethodLineUtility.get_payment_method_lines(
                user_env, journal_type
            )

            json_response = {
                "success": True,
                "payment_methods": payment_methods
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

    @http.route('/api/payment/method/lines/<int:line_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payment_method_line(self, line_id, **kwargs):
        """Fetch a specific payment method line by ID.

        Path Parameters:
            line_id: The ID of the payment method line

        Returns:
            JSON response with payment method line details
        """
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            pml = PaymentMethodLineUtility.get_payment_method_line_by_id(user_env, line_id)

            json_response = {
                "success": True,
                "payment_method": {
                    "id": pml.id,
                    "name": pml.name,
                    "code": pml.code if hasattr(pml, 'code') else None,
                    "journal_id": pml.journal_id.id,
                    "journal_name": pml.journal_id.name,
                    "payment_type": pml.payment_type,
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
                "message": f"Unexpected error: {str(err)}",
            }
            return request.make_json_response(error_response, status=500)
