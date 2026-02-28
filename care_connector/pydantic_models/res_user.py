from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from .res_partner import PartnerData
from .hr_employee import EmployeeData


class UserType(str, Enum):
    portal = "portal"
    internal = "internal"


class UserData(BaseModel):
    name: str
    login: str
    password: Optional[str] = None
    email: EmailStr
    user_type: UserType
    partner_data: PartnerData
    employee_data: EmployeeData
