"""API routes for agent prompt submission and tool execution."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.agent import AgentExecuteRequest, AgentExecuteResponse
from app.services.agent_service import agent_service

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/execute", response_model=AgentExecuteResponse)
def execute_agent_prompt(
    request: AgentExecuteRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Receive a user prompt and determine whether to execute or pause for HITL approval."""
    status_code, result = agent_service.handle_request(
        db=db,
        prompt=request.prompt,
        explicit_target_row_id=request.target_row_id,
    )
    response.status_code = status_code
    return result
