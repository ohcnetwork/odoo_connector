from odoo.http import request


class PartnerUtility:
    @classmethod
    def get_or_create_partner(cls, user_env, partner_data):
        """Retrieve or create partner"""
        try:
            res_partner_model = user_env["res.partner"]
            country_model = user_env["res.country"]
            state_model = user_env["res.country.state"]
            res_partner = res_partner_model.with_context(active_test=False).search(
                [("x_care_id", "=", partner_data.x_care_id)], limit=1
            )
            is_agent = True if partner_data.agent == True else False
            status = partner_data.status.value if partner_data.status else None
            if not res_partner:
                country = country_model.search([("code", "=", "IN")], limit=1)
                state = state_model.search(
                    [
                        ("name", "ilike", partner_data.state),
                        ("country_id", "=", country.id),
                    ],
                    limit=1,
                )

                res_partner = res_partner_model.create(
                    {
                        "name": partner_data.name,
                        "x_care_id": partner_data.x_care_id,
                        "x_care_id_type": "vendor",
                        "company_type": partner_data.partner_type.value,
                        "email": partner_data.email,
                        "vat": partner_data.pan,
                        "agent": is_agent,
                        "phone": partner_data.phone,
                        "country_id": country.id if country else False,
                        "state_id": state.id if state else False,
                    }
                )
            else:
                res_partner.name = partner_data.name
                res_partner.company_type = partner_data.partner_type.value
                res_partner.email = partner_data.email
                res_partner.vat = partner_data.pan
                res_partner.phone = partner_data.phone
                res_partner.agent = is_agent

            if status:
                if status == "retired" and res_partner.active:
                    res_partner.active = False
                elif status in ["draft", "active"] and not res_partner.active:
                    res_partner.active = True

            return res_partner

        except Exception as e:
            return {"error": f"Error while creating/updating partner: {str(e)}"}
