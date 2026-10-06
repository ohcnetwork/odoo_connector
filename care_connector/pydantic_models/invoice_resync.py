from typing import List

from pydantic import BaseModel, Field


class InvoiceResyncInvoice(BaseModel):
    invoice: str  # Odoo invoice number
    care_total: float = Field(allow_inf_nan=False)  # NaN would pass the total check
    # The invoice as the live sync sends it (an AccountMoveApiRequest). It's checked per invoice, so
    # one invoice with bad data doesn't fail the others in the call.
    data: dict


class InvoiceResyncApiRequest(BaseModel):
    dry_run: bool = True
    all_or_nothing: bool = False
    invoices: List[InvoiceResyncInvoice] = Field(max_length=25)
