from datetime import datetime


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
            status = partner_data.status.value if partner_data.status else None

            # Parse birthdate if provided
            birthdate = None
            if partner_data.birthdate:
                birthdate = datetime.strptime(partner_data.birthdate, "%d-%m-%Y").date()

            # Get gender value if provided and normalize it
            gender = None
            if partner_data.gender:
                gender_value = partner_data.gender.value.lower()
                # Map to 'other' if not male or female
                if gender_value not in ["male", "female"]:
                    gender = "other"
                else:
                    gender = gender_value

            # Resolve country and state
            country_code = partner_data.country_code or "IN"
            country = country_model.search([("code", "=", country_code)], limit=1)
            state = False
            if partner_data.state and country:
                state = state_model.search(
                    [
                        ("name", "ilike", partner_data.state),
                        ("country_id", "=", country.id),
                    ],
                    limit=1,
                )

            # Map partner_type to x_care_id_type
            care_id_type = (
                "user" if partner_data.partner_type.value == "person" else "vendor"
            )

            if not res_partner:
                create_vals = {
                    "name": partner_data.name,
                    "x_care_id": partner_data.x_care_id,
                    "x_care_id_type": care_id_type,
                    "company_type": partner_data.partner_type.value,
                    "country_id": country.id if country else False,
                    "state_id": state.id if state else False,
                }
                # Optional fields
                if partner_data.email:
                    create_vals["email"] = partner_data.email
                if partner_data.phone:
                    create_vals["phone"] = partner_data.phone
                if partner_data.pan:
                    create_vals["vat"] = partner_data.pan
                if partner_data.ref:
                    create_vals["ref"] = partner_data.ref
                if birthdate:
                    create_vals["x_birthdate"] = birthdate
                if gender:
                    create_vals["x_gender"] = gender
                # Address fields
                if partner_data.street:
                    create_vals["street"] = partner_data.street
                if partner_data.street2:
                    create_vals["street2"] = partner_data.street2
                if partner_data.city:
                    create_vals["city"] = partner_data.city
                if partner_data.zip:
                    create_vals["zip"] = partner_data.zip

                res_partner = res_partner_model.create(create_vals)
            else:
                # Update existing partner
                update_vals = {
                    "name": partner_data.name,
                    "company_type": partner_data.partner_type.value,
                }
                if partner_data.email:
                    update_vals["email"] = partner_data.email
                if partner_data.phone:
                    update_vals["phone"] = partner_data.phone
                if partner_data.pan:
                    update_vals["vat"] = partner_data.pan
                if partner_data.ref:
                    update_vals["ref"] = partner_data.ref
                if birthdate:
                    update_vals["x_birthdate"] = birthdate
                if gender:
                    update_vals["x_gender"] = gender
                # Address fields
                if partner_data.street:
                    update_vals["street"] = partner_data.street
                if partner_data.street2:
                    update_vals["street2"] = partner_data.street2
                if partner_data.city:
                    update_vals["city"] = partner_data.city
                if partner_data.zip:
                    update_vals["zip"] = partner_data.zip
                if country:
                    update_vals["country_id"] = country.id
                if state:
                    update_vals["state_id"] = state.id

                res_partner.write(update_vals)

            if status:
                if status == "retired" and res_partner.active:
                    res_partner.active = False
                elif status in ["draft", "active"] and not res_partner.active:
                    res_partner.active = True

            return res_partner

        except Exception as e:
            return {"error": f"Error while creating/updating partner: {str(e)}"}
