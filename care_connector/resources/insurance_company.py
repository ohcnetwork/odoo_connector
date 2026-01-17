class InsuranceCompanyUtility:
    @classmethod
    def get_insurance_company_by_id(cls, user_env, company_id):
        try:
            insurance_company_list = []
            insurance_company_model = user_env["insurance.company"]
            insurance_company = insurance_company_model.search(
                [("id", "=", int(company_id))], limit=1
            )
            if insurance_company:
                insurance_company_list.append(
                    {
                        "id": insurance_company.id,
                        "name": insurance_company.name,
                        "code": insurance_company.code,
                        "description": insurance_company.description or "",
                        "account_id": insurance_company.account_id.id
                        if insurance_company.account_id
                        else None,
                        "account_name": insurance_company.account_id.name
                        if insurance_company.account_id
                        else None,
                        "active": insurance_company.active,
                        "claim_count": insurance_company.claim_count,
                    }
                )
            return insurance_company_list
        except Exception as e:
            raise Exception(f"{str(e)}")

    @classmethod
    def search_insurance_companies(cls, user_env, request_data):
        try:
            insurance_company_list = []
            search_key = (request_data.search_key or "").strip()
            active_only = request_data.active_only

            insurance_company_model = user_env["insurance.company"]

            domain = []
            if search_key:
                domain = [
                    "|",
                    ("name", "=ilike", f"%{search_key}%"),
                    ("code", "=ilike", f"%{search_key}%"),
                ]
            if active_only:
                domain.append(("active", "=", True))

            insurance_companies = insurance_company_model.search(
                domain, order="name asc"
            )

            for company in insurance_companies:
                insurance_company_list.append(
                    {
                        "id": company.id,
                        "name": company.name,
                        "code": company.code,
                        "description": company.description or "",
                        "account_id": company.account_id.id
                        if company.account_id
                        else None,
                        "account_name": company.account_id.name
                        if company.account_id
                        else None,
                        "active": company.active,
                        "claim_count": company.claim_count,
                    }
                )

            return insurance_company_list

        except Exception as e:
            raise Exception(str(e))
