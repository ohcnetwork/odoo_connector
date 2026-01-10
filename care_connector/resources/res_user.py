from odoo.http import request


class UserUtility:
    @classmethod
    def get_or_create_user(cls, user_env, user_data):
        """Retrieve or create a user"""
        try:
            res_users_model = user_env['res.users']
            existing_user = res_users_model.with_context(active_test=False).search([('login', '=', user_data.login)], limit=1)

            user_type = user_data.user_type.value
            partner_data = user_data.partner_data

            if existing_user:
                cls._update_partner_details(user_env, existing_user, partner_data)
                return existing_user

            if user_type == "public":
                group_xml_id = "base.group_public"
            elif user_type == "portal":
                group_xml_id = "base.group_portal"
            else:
                group_xml_id = "base.group_user"

            user_vals = {
                "name": user_data.name,
                "login": user_data.login,
                "email": user_data.email,
                "groups_id": [(6, 0, [request.env.ref(group_xml_id).id])],
            }
            if user_data.password:
                user_vals["password"] = user_data.password

            res_user = res_users_model.create(user_vals)
            if not res_user:
                raise ValueError(f"User creation failed")

            status = partner_data.status.value if partner_data.status else None
            res_partner = res_user.partner_id
            if status:
                if status == 'retired' and res_partner.active:
                    res_user.active = False
                elif status in ['draft', 'active'] and not res_partner.active:
                    res_user.active = True

            return res_user

        except Exception as e:
            return {'error': f"Error while creating/updating user: {str(e)}"}


    @classmethod
    def _update_partner_details(cls,user_env, res_user, partner_data):
        try:
            country_model = user_env['res.country']
            state_model = user_env['res.country.state']

            res_partner = res_user.partner_id
            is_agent = True if partner_data.agent == True else False
            status = partner_data.status.value if partner_data.status else None
            country = country_model.search([('code', '=', 'IN')], limit=1)
            state = state_model.search([
                ('name', 'ilike', partner_data.state),
                ('country_id', '=', country.id)
            ], limit=1)

            partner_vals = {
                'x_care_id': partner_data.x_care_id,
                'name': partner_data.name,
                'company_type': partner_data.partner_type.value,
                'email': partner_data.email,
                'phone': partner_data.phone,
                'l10n_in_pan': partner_data.pan,
                'country_id': country.id if country else False,
                'state_id': state.id if state else False,
                'agent': is_agent
            }

            res_partner.write(partner_vals)
            if status:
                if status == 'retired' and res_partner.active:
                    res_partner.active = False
                elif status in ['draft', 'active'] and not res_partner.active:
                    res_partner.active = True
            return res_partner

        except Exception as e:
            raise {str(e)}
