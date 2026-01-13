import json
from odoo import http
from odoo.http import request
from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.hr_employee import EmployeeData
from ..resources.hr_employee import EmployeeUtility

class HrEmployeeAPI(http.Controller):

    @http.route('/api/hr/employee/create', type='http', auth='public', methods=['POST'], csrf=False)
    def create_hr_employee(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = EmployeeData(**data)
            hr_employee = EmployeeUtility.get_or_create_employee(user_env, request_data)
            json_response = {
                "success": True,
                "message": "Employee created successfully",
                "employee": {
                    "id": hr_employee.id,
                    "name": hr_employee.name,
                }
            }
            return request.make_json_response(json_response, status=200)

        except Exception as err:
            error_response = {
                "success": False,
                "error_type": "ServerError",
                "message": str(err),
            }
            return request.make_json_response(error_response, status=500)

