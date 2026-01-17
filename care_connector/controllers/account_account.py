import json
from odoo.http import request
from odoo import http
from ..authentication.authenticate_user import UserAuthentication
from ..resources.sponsor_company import SponsorCompanyUtility
from ..pydantic_models.sponsor_company import SponsorCompanySearchRequest


class AccountAccount(http.Controller):
    @http.route(
        "/api/v1/sponsor/<int:sponsor_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_sponsor_by_id(self, sponsor_id):
        """Get a sponsor company by ID."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            if not sponsor_id:
                raise ValueError("Sponsor ID is required")

            sponsor = SponsorCompanyUtility.get_sponsor_by_id(user_env, sponsor_id)

            return request.make_json_response(
                {
                    "success": True,
                    "count": len(sponsor),
                    "sponsor": sponsor,
                },
                status=200,
            )

        except Exception as e:
            return request.make_response(
                json.dumps({"success": False, "error": str(e)}),
                headers={"Content-Type": "application/json"},
            )

    @http.route(
        "/api/sponsors/search",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def search_sponsors(self, **post):
        """Search sponsor companies by name or code."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            data = json.loads(request.httprequest.data)
            request_data = SponsorCompanySearchRequest(**data)

            sponsors = SponsorCompanyUtility.search_sponsors(user_env, request_data)

            return request.make_json_response(
                {
                    "success": True,
                    "count": len(sponsors),
                    "sponsors": sponsors,
                },
                status=200,
            )

        except Exception as e:
            return request.make_response(
                json.dumps({"success": False, "error": str(e)}),
                headers={"Content-Type": "application/json"},
            )
