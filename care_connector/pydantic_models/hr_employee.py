from pydantic import BaseModel
from enum import Enum

class EmployeeStatus(Enum):
    active = 'active'
    retired = 'retired'
    draft = 'draft'

class EmployeeData(BaseModel):
    name: str
    x_care_id: str
    partner_x_care_id: str | None = None
    email: str
    phone: str
    job_title: str | None = None
    status: EmployeeStatus | None = None