"""Guardrail Interceptor Service enforcing security policies before execution."""

from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.models.content_queue import ContentQueue
from app.services.trust_service import trust_service
from app.utils.validators import check_bulk_intent


class GuardrailService:
    """Centralized guardrail interceptor for all agent-initiated tool calls."""

    ALLOWED_ACTIONS = {"purge", "mark_posted"}

    def evaluate_action(
        self,
        db: Session,
        prompt: str,
        action_type: str,
        target_row_id: Optional[int],
    ) -> Dict[str, Any]:
        """Run comprehensive deterministic checks on the intended action.

        Returns a dictionary:
        {
            "passed": bool,
            "status": "ALLOWED_AUTONOMOUS" | "REQUIRE_HITL" | "BLOCKED",
            "reason": str,
            "checks": dict,
            "current_trust": int,
            "trust_threshold": int
        }
        """
        checks: Dict[str, Any] = {}

        # 1. Bulk Destructive Guardrail
        is_bulk, bulk_reason = check_bulk_intent(prompt)
        if is_bulk or action_type == "bulk_purge":
            checks["bulk_check"] = "FAILED"
            return {
                "passed": False,
                "status": "BLOCKED",
                "reason": bulk_reason or "Bulk destructive operations are strictly prohibited.",
                "checks": checks,
                "current_trust": 0,
                "trust_threshold": settings.TRUST_THRESHOLD,
            }
        checks["bulk_check"] = "PASSED"

        # 2. Tool Whitelist Guardrail
        if action_type not in self.ALLOWED_ACTIONS:
            checks["whitelist_check"] = "FAILED"
            return {
                "passed": False,
                "status": "BLOCKED",
                "reason": f"Action '{action_type}' is not an authorized tool.",
                "checks": checks,
                "current_trust": 0,
                "trust_threshold": settings.TRUST_THRESHOLD,
            }
        checks["whitelist_check"] = "PASSED"

        # 3. Target Validity Check
        if target_row_id is None:
            checks["target_check"] = "FAILED"
            return {
                "passed": False,
                "status": "BLOCKED",
                "reason": "Action requires a valid target row id.",
                "checks": checks,
                "current_trust": 0,
                "trust_threshold": settings.TRUST_THRESHOLD,
            }

        target_row = db.query(ContentQueue).filter(ContentQueue.id == target_row_id).first()
        if not target_row:
            checks["target_check"] = "FAILED"
            return {
                "passed": False,
                "status": "BLOCKED",
                "reason": f"Target row {target_row_id} does not exist in content_queue.",
                "checks": checks,
                "current_trust": 0,
                "trust_threshold": settings.TRUST_THRESHOLD,
            }
        checks["target_check"] = "PASSED"

        # 4. Future-Dated Queue Rows Guardrail
        now = datetime.utcnow()
        if target_row.scheduled_for and target_row.scheduled_for > now:
            checks["future_date_check"] = "FAILED"
            return {
                "passed": False,
                "status": "BLOCKED",
                "reason": f"Row {target_row_id} is scheduled for future date ({target_row.scheduled_for.isoformat()}) and cannot be modified prematurely.",
                "checks": checks,
                "current_trust": 0,
                "trust_threshold": settings.TRUST_THRESHOLD,
            }
        checks["future_date_check"] = "PASSED"

        # 5. Idempotent State Transition Check
        if action_type == "mark_posted" and target_row.status == "POSTED":
            checks["state_transition_check"] = "FAILED"
            return {
                "passed": False,
                "status": "BLOCKED",
                "reason": f"Row {target_row_id} is already in POSTED status and cannot be posted again.",
                "checks": checks,
                "current_trust": 0,
                "trust_threshold": settings.TRUST_THRESHOLD,
            }
        if action_type == "purge" and target_row.status == "PURGED":
            checks["state_transition_check"] = "FAILED"
            return {
                "passed": False,
                "status": "BLOCKED",
                "reason": f"Row {target_row_id} is already in PURGED status.",
                "checks": checks,
                "current_trust": 0,
                "trust_threshold": settings.TRUST_THRESHOLD,
            }
        checks["state_transition_check"] = "PASSED"

        # 6. Trust-Based Progressive Autonomy Evaluation
        current_trust = trust_service.get_trust(db, action_type)
        checks["trust_check"] = f"{current_trust}/{settings.TRUST_THRESHOLD}"

        if current_trust < settings.TRUST_THRESHOLD:
            return {
                "passed": True,
                "status": "REQUIRE_HITL",
                "reason": f"Trust score ({current_trust}) is below threshold ({settings.TRUST_THRESHOLD}). Human-in-the-Loop approval required.",
                "checks": checks,
                "current_trust": current_trust,
                "trust_threshold": settings.TRUST_THRESHOLD,
            }

        return {
            "passed": True,
            "status": "ALLOWED_AUTONOMOUS",
            "reason": f"Trust score ({current_trust}) meets or exceeds threshold ({settings.TRUST_THRESHOLD}). Autonomous execution approved.",
            "checks": checks,
            "current_trust": current_trust,
            "trust_threshold": settings.TRUST_THRESHOLD,
        }


guardrail_service = GuardrailService()
