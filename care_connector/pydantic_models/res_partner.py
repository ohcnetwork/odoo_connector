from pydantic import BaseModel
from enum import Enum


class PartnerType(Enum):
    person = 'person'
    company = 'company'

class PartnerStatus(Enum):
    active = 'active'
    retired = 'retired'
    draft = 'draft'

class GenderType(Enum):
    male = "male"
    female = "female"
    other = "other"


class PartnerData(BaseModel):
    name: str
    x_care_id: str
    email: str | None = None
    phone: str | None = None
    state: str | None = None
    partner_type: PartnerType
    agent: bool | None = None
    pan: str | None = None
    status: PartnerStatus | None = None
    birthdate: str | None = None  # Format: DD-MM-YYYY
    gender: GenderType | None = None
    ref: str | None = None  # Reference/identifier for customer
    # Address fields
    street: str | None = None
    street2: str | None = None
    city: str | None = None
    zip: str | None = None
    country_code: str | None = None  # ISO country code e.g. "IN"