from pydantic import BaseModel, ConfigDict, Field

from .account_move import AccountMoveApiRequest


class InvoiceResyncApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: str  # Odoo invoice number
    care_total: float = Field(allow_inf_nan=False)  # NaN would pass the total check
    data: AccountMoveApiRequest  # the invoice as the live sync sends it
