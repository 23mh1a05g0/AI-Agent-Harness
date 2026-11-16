"""API routes for Human-in-the-Loop (HITL) actions."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.hitl import (
    PendingIntentResponse,
    HITLApprovalResponse,
    HITLRejectResponse,
)
from app.services.hitl_service import hitl_service

router = APIRouter(prefix="/api/hitl", tags=["Human-in-the-Loop"])


@router.get("/pending", response_model=List[PendingIntentResponse])
def get_pending_actions(db: Session = Depends(get_db)):
    """Retrieve all pending actions awaiting human review."""
    intents = hitl_service.get_pending_intents(db)
    return [
        PendingIntentResponse(
            intent_id=intent.intent_id,
            action_type=intent.action_type,
            target_row_id=intent.target_row_id,
            status=intent.status,
            prompt=intent.prompt,
            validated_payload=intent.validated_payload,
            created_at=intent.created_at.isoformat() if intent.created_at else None,
            approved_at=intent.approved_at.isoformat() if intent.approved_at else None,
        )
        for intent in intents
    ]


@router.post("/approve/{intent_id}", response_model=HITLApprovalResponse)
def approve_action(intent_id: str, db: Session = Depends(get_db)):
    """Approve a pending action, atomically executing mutation and updating trust."""
    try:
        intent, action_log, new_trust = hitl_service.approve_intent(db, intent_id)
        action_id = action_log.action_id if action_log else "already-executed"
        return HITLApprovalResponse(
            intent_id=intent.intent_id,
            action_id=action_id,
            action_type=intent.action_type,
            target_row_id=intent.target_row_id,
            status=intent.status,
            new_trust_count=new_trust,
            message="Intent successfully approved and executed. Trust score incremented.",
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reject/{intent_id}", response_model=HITLRejectResponse)
def reject_action(intent_id: str, db: Session = Depends(get_db)):
    """Reject a pending action without execution."""
    try:
        intent = hitl_service.reject_intent(db, intent_id)
        return HITLRejectResponse(
            intent_id=intent.intent_id,
            status=intent.status,
            message="Action rejected. Database mutation prevented.",
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
