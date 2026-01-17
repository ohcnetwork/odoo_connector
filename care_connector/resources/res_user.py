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
                "group_ids": [(6, 0, [user_env.ref(group_xml_id).id])],
            }
            if user_data.password:
                user_vals["password"] = user_data.password
            # Set x_care_id on user if available in partner_data
            if partner_data and partner_data.x_care_id:
                user_vals["x_care_id"] = partner_data.x_care_id

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
    def _update_partner_details(cls, user_env, res_user, partner_data):
        """Update partner details for an existing user."""
        country_model = user_env['res.country']
        state_model = user_env['res.country.state']

        res_partner = res_user.partner_id
        status = partner_data.status.value if partner_data.status else None
        country = country_model.search([('code', '=', 'IN')], limit=1)
        state = state_model.search([
            ('name', 'ilike', partner_data.state),
            ('country_id', '=', country.id)
        ], limit=1) if country else False

        partner_vals = {
            'x_care_id': partner_data.x_care_id,
            'name': partner_data.name,
            'company_type': partner_data.partner_type.value,
            'email': partner_data.email,
            'phone': partner_data.phone,
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
        }

        res_partner.write(partner_vals)
        
        # Also update x_care_id on the user for direct lookup
        if partner_data.x_care_id:
            res_user.write({'x_care_id': partner_data.x_care_id})
        if status:
            if status == 'retired' and res_partner.active:
                res_partner.active = False
            elif status in ['draft', 'active'] and not res_partner.active:
                res_partner.active = True
        return res_partner
