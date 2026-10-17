from typing import List

from pydantic import BaseModel, ConfigDict, Field


class InvoiceResyncInvoice(BaseModel):
    number: str  # Odoo invoice number
    care_total: float = Field(allow_inf_nan=False)  # NaN would pass the total check
    # The invoice as the live sync sends it (an AccountMoveApiRequest). It's checked per invoice, so
    # one invoice with bad data doesn't fail the others in the call.
    data: dict


class InvoiceResyncApiRequest(BaseModel):
    # Unknown fields are rejected, so a request still sending dry_run fails instead of applying
    model_config = ConfigDict(extra="forbid")
    invoices: List[InvoiceResyncInvoice] = Field(max_length=25)
