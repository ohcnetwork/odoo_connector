from pydantic import BaseModel
from enum import Enum


class PartnerType(Enum):
    person = 'person'
    company = 'company'

class PartnerStatus(Enum):
    active = 'active'
    retired = 'retired'
    draft = 'draft'

class PartnerData(BaseModel):
    name: str
    x_care_id: str
    email: str
    phone: str
    state: str
    partner_type: PartnerType
    agent: bool | None = None
    pan: str | None = None
    status: PartnerStatus | None = None