"""Action Execution Service performing deterministic state capture and mutation."""

import uuid
from typing import Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.models.content_queue import ContentQueue
from app.models.action_log import ActionLog


class ActionService:
    """Executes validated database mutations and records append-only action logs."""

    def execute_action(
        self,
        db: Session,
        action_type: str,
        target_row_id: int,
    ) -> Tuple[ActionLog, ContentQueue]:
        """Atomically mutate content row and record before/after states.

        Returns:
            (ActionLog, updated ContentQueue)
        """
        row = db.query(ContentQueue).filter(ContentQueue.id == target_row_id).first()
        if not row:
            raise ValueError(f"Target row {target_row_id} does not exist in content_queue")

        # Capture exact previous state snapshot
        previous_state = row.to_dict()

        # Execute deterministic mutation
        if action_type == "purge":
            row.status = "PURGED"
        elif action_type == "mark_posted":
            row.status = "POSTED"
        else:
            raise ValueError(f"Unsupported action type: {action_type}")

        # Flush to register updated state
        db.flush()
        db.refresh(row)
        new_state = row.to_dict()

        # Create append-only action log
        action_log = ActionLog(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            target_row_id=target_row_id,
            previous_state=previous_state,
            new_state=new_state,
            is_restored=False,
        )
        db.add(action_log)
        db.commit()
        db.refresh(action_log)

        return action_log, row


action_service = ActionService()
