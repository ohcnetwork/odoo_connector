from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


# === SESSION MODELS ===

class OpenSessionRequest(BaseModel):
    """Request to open a new cash session."""
    external_user_id: str = Field(..., description="Care user ID")
    external_user_name: str = Field(..., description="Care user display name")
    counter_x_care_id: str = Field(..., description="Counter Care ID")
    opening_balance: float = Field(default=0.0, ge=0, description="Opening cash balance")


class CloseSessionRequest(BaseModel):
    """Request to close an existing cash session."""
    external_user_id: str = Field(..., description="Care user ID")
    counter_x_care_id: str = Field(..., description="Counter Care ID")
    closed_by_ext_id: str = Field(..., description="Who is closing the session")
    closed_by_name: str = Field(..., description="Name of person closing")


class SessionResponse(BaseModel):
    """Response containing session details."""
    id: int
    external_user_id: str
    external_user_name: str
    counter_id: int
    counter_name: str
    status: str
    opening_balance: float
    expected_amount: float
    opened_at: str
    closed_at: Optional[str] = None
    closing_expected: Optional[float] = None
    closing_declared: Optional[float] = None
    closing_difference: Optional[float] = None
    difference_status: str
    payment_count: int
    pending_outgoing_count: int
    pending_incoming_count: int


class SessionListRequest(BaseModel):
    """Request to list sessions with optional filters."""
    external_user_id: Optional[str] = None
    counter_x_care_id: Optional[str] = None
    status: Optional[str] = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)


# === TRANSFER MODELS ===

class CreateTransferRequest(BaseModel):
    """Request to create a cash transfer."""
    from_user_id: str = Field(..., description="From session user ID")
    from_counter_x_care_id: str = Field(..., description="From counter Care ID")
    to_session_id: int = Field(..., description="Target session ID")
    amount: float = Field(..., gt=0, description="Transfer amount")
    created_by_ext_id: str = Field(..., description="Creator user ID")
    created_by_name: str = Field(..., description="Creator name")
    denominations: Optional[Dict[str, int]] = Field(
        default=None,
        description="Denomination breakdown (required for main cash)"
    )


class AcceptTransferRequest(BaseModel):
    """Request to accept a pending transfer."""
    session_id: int = Field(..., description="Session ID of the acceptor (must match transfer destination)")
    resolved_by_ext_id: str = Field(..., description="Who is accepting")
    resolved_by_name: str = Field(..., description="Name of acceptor")


class RejectTransferRequest(BaseModel):
    """Request to reject a pending transfer."""
    session_id: int = Field(..., description="Session ID of the rejector (must match transfer destination)")
    resolved_by_ext_id: str = Field(..., description="Who is rejecting")
    resolved_by_name: str = Field(..., description="Name of rejector")
    reason: Optional[str] = Field(default=None, description="Rejection reason")


class CancelTransferRequest(BaseModel):
    """Request to cancel a pending transfer (by the sender)."""
    cancelled_by_ext_id: str = Field(..., description="Who is cancelling")
    cancelled_by_name: str = Field(..., description="Name of canceller")
    reason: Optional[str] = Field(default=None, description="Cancellation reason")


class TransferResponse(BaseModel):
    """Response containing transfer details."""
    id: int
    from_session_id: int
    from_user_name: str
    from_counter_name: str
    to_session_id: int
    to_user_name: str
    to_counter_name: str
    amount: float
    denominations: Optional[Dict[str, int]] = None
    status: str
    created_by_name: str
    created_at: str
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[str] = None
    reject_reason: Optional[str] = None
    journal_entry_id: Optional[int] = None


class TransferListRequest(BaseModel):
    """Request to list transfers with optional filters."""
    from_session_id: Optional[int] = None
    to_session_id: Optional[int] = None
    status: Optional[str] = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)


class PendingTransfersRequest(BaseModel):
    """Request to get pending transfers for a session."""
    external_user_id: str = Field(..., description="User ID")
    counter_x_care_id: str = Field(..., description="Counter Care ID")


# === COUNTER MODELS ===

class OpenSessionInfo(BaseModel):
    """Info about an open session at a counter."""
    session_id: int
    external_user_id: str
    external_user_name: str


class CounterResponse(BaseModel):
    """Response containing counter details."""
    id: int
    name: str
    x_care_id: str
    is_main_cash: bool = False
    open_sessions: List[OpenSessionInfo] = Field(default_factory=list)
    open_session_count: int = 0
