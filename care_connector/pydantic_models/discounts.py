from pydantic import BaseModel
from enum import Enum

class DiscountGroup(BaseModel):
    x_care_id: str
    name: str

class DiscountType(Enum):
    amount = 'amount'
    factor = 'factor'

class InvoiceDiscounts(BaseModel):
    name: str
    discount_group: DiscountGroup
    discount_type: DiscountType
    rate: float = 0.0
    disc_amt: float = 0.0