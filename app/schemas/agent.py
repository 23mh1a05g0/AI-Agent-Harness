"""Pydantic schemas for agent tool calling and execution."""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class AgentExecuteRequest(BaseModel):
    """Incoming user prompt to the agent."""
    prompt: str = Field(..., min_length=1, description="Natural language prompt for the agent")
    target_row_id: Optional[int] = Field(None, description="Optional explicit target row id")


class ToolCallPayload(BaseModel):
    """Strictly validated structured tool call representation."""
    action_type: Literal["purge", "mark_posted"] = Field(..., description="Allowed deterministic action types")
    target_row_id: int = Field(..., description="Target content row id in content_queue")


class AgentExecuteResponse(BaseModel):
    """Response returned by the agent execution endpoint."""
    status: Literal["EXECUTED", "PENDING_APPROVAL", "BLOCKED"]
    decision: str
    intent_id: Optional[str] = None
    action_id: Optional[str] = None
    action_type: Optional[str] = None
    target_row_id: Optional[int] = None
    trust_count: Optional[int] = None
    trust_threshold: Optional[int] = None
    message: str
