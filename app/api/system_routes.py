"""API routes for system operations (restoration, action logs, trust counters, content queue)."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.content_queue import ContentQueue
from app.models.action_log import ActionLog
from app.models.trust_store import TrustStore
from app.schemas.system import (
    RestoreRequest,
    RestoreResponse,
    ActionLogResponse,
    TrustStoreResponse,
    ContentQueueResponse,
)
from app.services.restore_service import restore_service

router = APIRouter(prefix="/api/system", tags=["System Operations"])


@router.post("/restore", response_model=RestoreResponse)
def restore_action_state(
    request: RestoreRequest,
    db: Session = Depends(get_db),
):
    """Restore the previous state of a target row and reduce the trust score by 1."""
    try:
        action_log, current_trust, info = restore_service.restore_action(db, request.action_id)
        is_restored = info.get("restored", False)
        msg = (
            "State successfully restored and trust score penalized."
            if is_restored
            else "Action had already been restored. Trust score preserved."
        )
        return RestoreResponse(
            action_id=action_log.action_id,
            target_row_id=action_log.target_row_id,
            restored=True,
            previous_state=info.get("previous_state"),
            current_trust_count=current_trust,
            message=msg,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/actions", response_model=List[ActionLogResponse])
def get_action_history(db: Session = Depends(get_db)):
    """View append-only action log history."""
    actions = db.query(ActionLog).order_by(ActionLog.created_at.desc()).all()
    return [
        ActionLogResponse(
            action_id=action.action_id,
            action_type=action.action_type,
            target_row_id=action.target_row_id,
            previous_state=action.previous_state,
            new_state=action.new_state,
            is_restored=action.is_restored,
            created_at=action.created_at.isoformat() if action.created_at else None,
        )
        for action in actions
    ]


@router.get("/trust", response_model=List[TrustStoreResponse])
def get_trust_counters(db: Session = Depends(get_db)):
    """View current trust counters for all registered action types."""
    records = db.query(TrustStore).all()
    return [
        TrustStoreResponse(
            action_type=record.action_type,
            success_count=record.success_count,
        )
        for record in records
    ]


@router.get("/queue", response_model=List[ContentQueueResponse])
def get_content_queue(db: Session = Depends(get_db)):
    """View current content queue items and their statuses."""
    items = db.query(ContentQueue).order_by(ContentQueue.id.asc()).all()
    return [
        ContentQueueResponse(
            id=item.id,
            content_text=item.content_text,
            status=item.status,
            scheduled_for=item.scheduled_for.isoformat() if item.scheduled_for else None,
            created_at=item.created_at.isoformat() if item.created_at else None,
            updated_at=item.updated_at.isoformat() if item.updated_at else None,
        )
        for item in items
    ]
