class SponsorCompanyUtility:
    @classmethod
    def get_sponsor_by_id(cls, user_env, sponsor_id):
        """Get a sponsor company by ID."""
        sponsor_list = []
        sponsor_model = user_env["sponsor.company"]
        sponsor = sponsor_model.search([("id", "=", int(sponsor_id))], limit=1)

        if sponsor:
            sponsor_list.append(cls._format_sponsor(sponsor))

        return sponsor_list

    @classmethod
    def search_sponsors(cls, user_env, request_data):
        """Search sponsor companies by name or code."""
        sponsor_model = user_env["sponsor.company"]
        search_key = (request_data.search_key or "").strip()
        active_only = request_data.active_only

        domain = []
        if search_key:
            domain = [
                "|",
                ("name", "=ilike", f"%{search_key}%"),
                ("code", "=ilike", f"%{search_key}%"),
            ]
        if active_only:
            domain.append(("active", "=", True))

        sponsors = sponsor_model.search(domain, order="name asc")

        return [cls._format_sponsor(sponsor) for sponsor in sponsors]

    @classmethod
    def _format_sponsor(cls, sponsor):
        """Format sponsor record for API response."""
        return {
            "id": sponsor.id,
            "name": sponsor.name,
            "code": sponsor.code or "",
            "phone": sponsor.phone or "",
            "mobile": sponsor.mobile or "",
            "email": sponsor.email or "",
            "city": sponsor.city or "",
            "active": sponsor.active,
            "invoice_count": sponsor.invoice_count,
        }
