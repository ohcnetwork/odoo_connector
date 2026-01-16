from pydantic import BaseModel


class InsuranceCompanySearchRequest(BaseModel):
    search_key: str | None = None
    active_only: bool = True

