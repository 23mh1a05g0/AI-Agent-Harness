"""Deterministic Restoration and Rollback Service."""

import uuid
from datetime import datetime
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.content_queue import ContentQueue
from app.models.action_log import ActionLog, RestorationLog
from app.services.trust_service import trust_service


class RestoreService:
    """Handles deterministic rollback of actions with trust penalty."""

    def restore_action(self, db: Session, action_id: str) -> Tuple[ActionLog, int, Dict[str, Any]]:
        """Restore previous state for an action log entry.

        Idempotent: Subsequent calls for an already restored action do not penalize trust again.
        Returns:
            (ActionLog, current_trust_count, restoration_info)
        """
        # Find action log
        action = db.query(ActionLog).filter(ActionLog.action_id == action_id).first()
        if not action:
            raise KeyError(f"Action log with id {action_id} not found")

        # Idempotency: if already restored, return existing state without penalty
        if action.is_restored:
            current_trust = trust_service.get_trust(db, action.action_type)
            return action, current_trust, {
                "restored": False,
                "already_restored": True,
                "previous_state": action.previous_state,
            }

        prev_state = action.previous_state
        if not prev_state:
            raise ValueError(f"Action {action_id} does not contain valid previous_state")

        target_row_id = action.target_row_id or prev_state.get("id")

        # Re-fetch or re-create row in content_queue
        row = db.query(ContentQueue).filter(ContentQueue.id == target_row_id).first()
        if not row:
            # Recreate from snapshot if missing
            row = ContentQueue(
                id=target_row_id,
                content_text=prev_state.get("content_text", ""),
                status=prev_state.get("status", "PENDING"),
            )
            db.add(row)
        else:
            # Restore exact snapshot attributes
            row.content_text = prev_state.get("content_text", row.content_text)
            row.status = prev_state.get("status", "PENDING")

        # Mark action as restored
        action.is_restored = True

        # Append-only restoration log
        restoration = RestorationLog(
            restoration_id=str(uuid.uuid4()),
            action_id=action.action_id,
            target_row_id=target_row_id,
            restored_at=datetime.utcnow(),
            details={
                "restored_state": prev_state,
                "prior_state": action.new_state,
            },
        )
        db.add(restoration)

        # Apply trust penalty: decrease success_count by exactly 1 (floor at 0)
        new_trust = trust_service.decrement_trust(db, action.action_type)

        db.commit()
        db.refresh(action)

        return action, new_trust, {
            "restored": True,
            "already_restored": False,
            "previous_state": prev_state,
        }


restore_service = RestoreService()
