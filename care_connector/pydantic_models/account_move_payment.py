from pydantic import BaseModel, Field, field_validator
from enum import Enum
from .res_partner import PartnerData
from . bill_counter import BillCounterData

class JournalType(Enum):
    cash = 'cash'
    bank = 'bank'
    card = 'card'

class PaymentMode(Enum):
    send = 'send'
    receive = 'receive'

class CustomerType(Enum):
    customer = 'customer'
    vendor = 'vendor'

class AccountMovePaymentApiRequest(BaseModel):
    x_care_id: str
    journal_x_care_id: str | None = None
    amount: float = 0.0
    journal_input : JournalType
    payment_date : str
    payment_mode : PaymentMode
    partner_data: PartnerData
    customer_type: CustomerType
    counter_data: BillCounterData
    bank_reference: str | None = None

class AccountPaymentCancelApiRequest(BaseModel):
    x_care_id: str
    reason: str | None = None