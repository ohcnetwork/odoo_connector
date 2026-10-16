from typing import List

from pydantic import BaseModel, Field

from .discounts import InvoiceDiscounts


class DiscountResyncLine(BaseModel):
    x_care_id: str  # Care charge item, account.move.line.x_care_id
    discounts: List[InvoiceDiscounts] = []  # the discounts Care applied


class DiscountResyncInvoice(BaseModel):
    invoice: str  # Odoo invoice number
    x_care_id: str  # Care invoice, account.move.x_care_id
    care_total: float = Field(allow_inf_nan=False)  # NaN would pass the total check
    lines: List[DiscountResyncLine]


class DiscountResyncApiRequest(BaseModel):
    dry_run: bool = True
    all_or_nothing: bool = False
    invoices: List[DiscountResyncInvoice] = Field(max_length=25)
