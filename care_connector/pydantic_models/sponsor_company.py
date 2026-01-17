from pydantic import BaseModel


class SponsorCompanySearchRequest(BaseModel):
    search_key: str | None = None
    active_only: bool = True
