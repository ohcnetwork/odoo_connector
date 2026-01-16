import json
from odoo.http import request, Response
from odoo import http
from ..authentication.authenticate_user import UserAuthentication
from ..resources.insurance_company import InsuranceCompanyUtility
from ..pydantic_models.insurance_company import InsuranceCompanySearchRequest


class InsuranceCompany(http.Controller):

    @http.route('/api/v1/insurance/company/<int:company_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_insurance_company_by_id(self, company_id):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            if not company_id:
                raise ValueError("Insurance company id is missing")

            insurance_company = InsuranceCompanyUtility.get_insurance_company_by_id(user_env, company_id)

            json_response = {
                "success": True,
                "count": len(insurance_company),
                "insurance_company": insurance_company
            }
            return request.make_json_response(json_response, status=200)

        except Exception as e:
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers={'Content-Type': 'application/json'}
            )

    @http.route('/api/insurance/companies/search', type='http', auth='public', methods=['GET'], csrf=False)
    def search_insurance_companies(self, **post):
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = InsuranceCompanySearchRequest(**data)
            insurance_companies = InsuranceCompanyUtility.search_insurance_companies(user_env, request_data)

            json_response = {
                "success": True,
                "count": len(insurance_companies),
                "insurance_companies": insurance_companies
            }
            return request.make_json_response(json_response, status=200)

        except Exception as e:
            return request.make_response(
                json.dumps({"success": False, "error": str(e)}),
                headers={'Content-Type': 'application/json'}
            )

