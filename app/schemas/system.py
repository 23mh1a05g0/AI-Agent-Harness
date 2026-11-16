"""Pydantic schemas for system operations (restore, audit, queue, trust)."""

from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class RestoreRequest(BaseModel):
    """Request payload to restore a historical action."""
    action_id: str = Field(..., min_length=1, description="UUID of the action to restore")


class RestoreResponse(BaseModel):
    """Outcome of restoration."""
    action_id: str
    target_row_id: Optional[int] = None
    restored: bool
    previous_state: Optional[Dict[str, Any]] = None
    current_trust_count: int
    message: str


class ActionLogResponse(BaseModel):
    """Action log entry representation."""
    action_id: str
    action_type: str
    target_row_id: Optional[int] = None
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    is_restored: bool
    created_at: Optional[str] = None


class TrustStoreResponse(BaseModel):
    """Trust counter representation."""
    action_type: str
    success_count: int


class ContentQueueResponse(BaseModel):
    """Content queue item representation."""
    id: int
    content_text: str
    status: str
    scheduled_for: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
