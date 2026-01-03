from pydantic import BaseModel
from typing import List
from enum import Enum
from .res_partner import PartnerData
from .product_product import ProductData
from .discounts import InvoiceDiscounts


class InvoiceItem(BaseModel):
    product_data:  ProductData
    quantity: float = 1.0
    sale_price: float = 0.0
    x_care_id: str
    agent_id: str | None = None
    discounts: list[InvoiceDiscounts] | None = None
    free_qty: float = 0.0


class BillType(Enum):
    vendor = 'vendor'
    customer = 'customer'


class AccountMoveApiRequest(BaseModel):
    x_care_id: str
    invoice_number: str | None = None
    bill_type: BillType
    invoice_date: str
    due_date : str
    partner_data: PartnerData
    invoice_items: List[InvoiceItem]
    reason: str | None = None
    insurance_tag: List[str] | None = None
    payment_method_id: int | None = None
    x_identifier: str | None = None
    x_created_by: str | None = None
    payment_reference: str | None = None


class AccountMoveReturnApiRequest(BaseModel):
    x_care_id: str
    bill_type: BillType | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    partner_data: PartnerData | None = None
    invoice_items: List[InvoiceItem] | None = None
    reason: str | None = None

class AccountPaymentMethodApiRequest(BaseModel):
    search_key: str | None = None
