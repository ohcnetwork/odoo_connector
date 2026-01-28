from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
from .res_partner import PartnerData
from .bill_counter import BillCounterData


class JournalType(Enum):
    cash = "cash"
    bank = "bank"
    card = "card"
    debit = "debit"  # Debit Card
    credit = "credit"  # Care of Accounts (charity/sponsor payments)


class PaymentMode(Enum):
    send = "send"
    receive = "receive"


class CustomerType(Enum):
    customer = "customer"
    vendor = "vendor"


class AccountMovePaymentApiRequest(BaseModel):
    x_care_id: str
    journal_x_care_id: str | None = None
    amount: float = 0.0
    journal_input: JournalType
    payment_date: str
    payment_mode: PaymentMode
    partner_data: PartnerData
    customer_type: CustomerType
    counter_data: BillCounterData
    bank_reference: str | None = None
    # For credit (Care of Account) payments - specifies which charity/fund is paying
    payment_method_line_id: int | None = None

    @model_validator(mode="after")
    def validate_credit_payment(self):
        """Validate that credit payments include payment_method_line_id."""
        if self.journal_input == JournalType.credit and not self.payment_method_line_id:
            raise ValueError(
                "payment_method_line_id is required for credit (Care of Account) payments. "
                "Use GET /api/payment/method/lines to fetch available payment methods."
            )
        return self


class AccountPaymentCancelApiRequest(BaseModel):
    x_care_id: str
    reason: str | None = None
