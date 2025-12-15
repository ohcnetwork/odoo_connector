from odoo.http import request


class UserUtility:
    @classmethod
    def get_or_create_user(cls, user_env, user_data):
        """Retrieve or create a user"""
        try:
            x_care_id = user_data.x_care_id
            res_users_model = user_env["res.users"]
            country_model = user_env["res.country"]
            state_model = user_env["res.country.state"]
            existing_user = res_users_model.search(
                [("x_care_id", "=", x_care_id)], limit=1
            )
            # Fallback for existing users with no x_care_id
            if not existing_user.x_care_id:
                existing_user = res_users_model.search(
                    [("login", "=", user_data.login)], limit=1
                )

            user_type = user_data.user_type.value
            partner_data = user_data.partner_data
            is_agent = bool(partner_data.agent)

            if existing_user:
                existing_user.name = user_data.name
                # Update x_care_id if not already set
                if not existing_user.x_care_id:
                    existing_user.x_care_id = x_care_id
                partner = existing_user.partner_id
                partner.company_type = partner_data.partner_type.value
                partner.phone = partner_data.phone
                partner.l10n_in_pan = partner_data.pan
                partner.agent = is_agent
                return existing_user
            group_xml_id = (
                "base.group_portal" if user_type == "portal" else "base.group_user"
            )

            user_vals = {
                "name": user_data.name,
                "login": user_data.login,
                "email": user_data.email,
                "x_care_id": x_care_id,
                "groups_id": [(6, 0, [request.env.ref(group_xml_id).id])],
            }
            if user_data.password:
                user_vals["password"] = user_data.password

            res_user = res_users_model.create(user_vals)
            if not res_user:
                raise ValueError(f"User creation failed")

            res_partner = res_user.partner_id

            country = country_model.search([("code", "=", "IN")], limit=1)
            state = state_model.search(
                [
                    ("name", "ilike", partner_data.state),
                    ("country_id", "=", country.id),
                ],
                limit=1,
            )

            partner_vals = {
                "x_care_id": partner_data.x_care_id,
                "x_care_id_type": "user",
                "company_type": partner_data.partner_type.value,
                "email": partner_data.email,
                "phone": partner_data.phone,
                "l10n_in_pan": partner_data.pan,
                "country_id": country.id if country else False,
                "state_id": state.id if state else False,
                "agent": is_agent,
            }

            res_partner.write(partner_vals)
            return res_user

        except Exception as e:
            return {"error": f"Error while creating/updating user: {str(e)}"}
