from pydantic import BaseModel


class PaymentMethodLineResponse(BaseModel):
    """Response model for a single payment method line (Care of Account / Credit)."""
    id: int
    name: str
    code: str | None = None
    journal_id: int
    journal_name: str


class PaymentMethodLineListResponse(BaseModel):
    """Response model for list of payment method lines."""
    success: bool
    payment_methods: list[PaymentMethodLineResponse]
