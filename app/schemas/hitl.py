"""Pydantic schemas for Human-in-the-Loop (HITL) actions."""

from typing import Optional, Any, Dict
from pydantic import BaseModel


class PendingIntentResponse(BaseModel):
    """Schema for a pending HITL intent record."""
    intent_id: str
    action_type: str
    target_row_id: Optional[int] = None
    status: str
    prompt: str
    validated_payload: Dict[str, Any]
    created_at: Optional[str] = None
    approved_at: Optional[str] = None


class HITLApprovalResponse(BaseModel):
    """Schema for approval action outcome."""
    intent_id: str
    action_id: str
    action_type: str
    target_row_id: Optional[int] = None
    status: str
    new_trust_count: int
    message: str


class HITLRejectResponse(BaseModel):
    """Schema for rejection action outcome."""
    intent_id: str
    status: str
    message: str
