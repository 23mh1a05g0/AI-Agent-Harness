"""Human-in-the-Loop (HITL) Service for managing approval workflows."""

import uuid
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.models.pending_intent import PendingIntent
from app.models.action_log import ActionLog
from app.services.action_service import action_service
from app.services.trust_service import trust_service


class HITLService:
    """Manages pending intents, approvals, rejections, and trust increments."""

    def create_pending_intent(
        self,
        db: Session,
        action_type: str,
        target_row_id: Optional[int],
        prompt: str,
        validated_payload: Dict[str, Any],
        status: str = "PENDING",
    ) -> PendingIntent:
        """Persist a new pending intent."""
        intent = PendingIntent(
            intent_id=str(uuid.uuid4()),
            action_type=action_type,
            target_row_id=target_row_id,
            prompt=prompt,
            validated_payload=validated_payload,
            status=status,
            created_at=datetime.utcnow(),
        )
        db.add(intent)
        db.commit()
        db.refresh(intent)
        return intent

    def get_pending_intents(self, db: Session) -> List[PendingIntent]:
        """List all intents currently awaiting approval."""
        return db.query(PendingIntent).filter(PendingIntent.status == "PENDING").order_by(PendingIntent.created_at.asc()).all()

    def get_intent_by_id(self, db: Session, intent_id: str) -> Optional[PendingIntent]:
        """Fetch an intent by its ID."""
        return db.query(PendingIntent).filter(PendingIntent.intent_id == intent_id).first()

    def approve_intent(
        self,
        db: Session,
        intent_id: str,
    ) -> Tuple[PendingIntent, Optional[ActionLog], int]:
        """Atomically approve a pending intent and execute the mutation.

        Idempotent: Repeated approvals do not execute twice or increase trust twice.
        Returns:
            (PendingIntent, ActionLog, current_trust_count)
        """
        # Lock intent row if non-sqlite
        query = db.query(PendingIntent).filter(PendingIntent.intent_id == intent_id)
        if db.bind and db.bind.dialect.name != "sqlite":
            query = query.with_for_update()

        intent = query.first()
        if not intent:
            raise KeyError(f"Pending intent {intent_id} not found")

        # Idempotency check: if already EXECUTED, return existing record
        if intent.status == "EXECUTED":
            current_trust = trust_service.get_trust(db, intent.action_type)
            # Find the corresponding action_log if available
            action_log = (
                db.query(ActionLog)
                .filter(ActionLog.target_row_id == intent.target_row_id, ActionLog.action_type == intent.action_type)
                .order_by(ActionLog.created_at.desc())
                .first()
            )
            return intent, action_log, current_trust

        if intent.status != "PENDING":
            raise ValueError(f"Cannot approve intent with status '{intent.status}'")

        if intent.target_row_id is None:
            raise ValueError("Intent has no target_row_id")

        # Execute mutation & log state
        action_log, _ = action_service.execute_action(
            db=db,
            action_type=intent.action_type,
            target_row_id=intent.target_row_id,
        )

        # Atomically increment trust score by exactly 1
        new_trust = trust_service.increment_trust(db, intent.action_type)

        # Mark intent as EXECUTED
        intent.status = "EXECUTED"
        intent.approved_at = datetime.utcnow()
        db.commit()
        db.refresh(intent)

        return intent, action_log, new_trust

    def reject_intent(self, db: Session, intent_id: str) -> PendingIntent:
        """Reject a pending intent."""
        intent = db.query(PendingIntent).filter(PendingIntent.intent_id == intent_id).first()
        if not intent:
            raise KeyError(f"Pending intent {intent_id} not found")

        if intent.status == "REJECTED":
            return intent  # Idempotent

        if intent.status == "EXECUTED":
            raise ValueError("Cannot reject an already executed intent")

        intent.status = "REJECTED"
        db.commit()
        db.refresh(intent)
        return intent


hitl_service = HITLService()
