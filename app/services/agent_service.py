"""Agent Orchestration Service connecting LLM, Guardrails, Trust, and Execution."""

import uuid
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.config import settings
from app.services.llm_service import llm_service
from app.services.guardrail_service import guardrail_service
from app.services.hitl_service import hitl_service
from app.services.action_service import action_service
from app.schemas.agent import AgentExecuteResponse, ToolCallPayload
from app.utils.trace_logger import trace_logger
from pydantic import ValidationError


class AgentService:
    """Orchestrator enforcing strict LLM isolation and progressive autonomy."""

    def handle_request(
        self,
        db: Session,
        prompt: str,
        explicit_target_row_id: Optional[int] = None,
    ) -> Tuple[int, AgentExecuteResponse]:
        """Process incoming prompt through the guardrail pipeline.

        Returns:
            (HTTP_STATUS_CODE, AgentExecuteResponse)
        """
        request_id = str(uuid.uuid4())

        # Step 1: LLM generates candidate tool call (No DB access)
        raw_llm_output = llm_service.generate_tool_call(prompt, explicit_target_row_id)
        action_type = raw_llm_output.get("action_type")
        target_row_id = raw_llm_output.get("target_row_id")

        # Step 2: Validate against Pydantic schema
        validated_payload = None
        validation_error = None
        try:
            payload_obj = ToolCallPayload(
                action_type=action_type,
                target_row_id=target_row_id,
            )
            validated_payload = payload_obj.model_dump()
        except (ValidationError, TypeError) as val_err:
            validation_error = str(val_err)

        # If schema validation failed, evaluate guardrail with raw values
        guardrail_result = guardrail_service.evaluate_action(
            db=db,
            prompt=prompt,
            action_type=action_type or "unknown",
            target_row_id=target_row_id,
        )

        current_trust = guardrail_result["current_trust"]
        trust_threshold = guardrail_result["trust_threshold"]

        # Case 1: Guardrail explicitly blocked the action
        if guardrail_result["status"] == "BLOCKED" or validation_error:
            reason = guardrail_result["reason"] if guardrail_result["status"] == "BLOCKED" else f"Schema validation error: {validation_error}"
            
            # Persist blocked intent for auditability
            blocked_intent = hitl_service.create_pending_intent(
                db=db,
                action_type=action_type or "unknown",
                target_row_id=target_row_id,
                prompt=prompt,
                validated_payload=validated_payload or {"raw": raw_llm_output},
                status="BLOCKED",
            )

            trace_logger.log_decision(
                request_id=request_id,
                prompt=prompt,
                source_row_id=target_row_id,
                raw_llm_output=raw_llm_output,
                validated_payload=validated_payload,
                guardrail_checks=guardrail_result["checks"],
                trust_count=current_trust,
                trust_threshold=trust_threshold,
                decision="GUARDRAIL_BLOCKED",
                intent_id=blocked_intent.intent_id,
                action_outcome="BLOCKED",
            )

            return 400, AgentExecuteResponse(
                status="BLOCKED",
                decision="BLOCKED",
                intent_id=blocked_intent.intent_id,
                action_type=action_type,
                target_row_id=target_row_id,
                trust_count=current_trust,
                trust_threshold=trust_threshold,
                message=reason,
            )

        # Case 2: Untrusted action requires HITL approval (HTTP 202)
        if guardrail_result["status"] == "REQUIRE_HITL":
            pending_intent = hitl_service.create_pending_intent(
                db=db,
                action_type=action_type,
                target_row_id=target_row_id,
                prompt=prompt,
                validated_payload=validated_payload or {},
                status="PENDING",
            )

            trace_logger.log_decision(
                request_id=request_id,
                prompt=prompt,
                source_row_id=target_row_id,
                raw_llm_output=raw_llm_output,
                validated_payload=validated_payload,
                guardrail_checks=guardrail_result["checks"],
                trust_count=current_trust,
                trust_threshold=trust_threshold,
                decision="REQUIRE_HITL",
                intent_id=pending_intent.intent_id,
                action_outcome="PENDING_APPROVAL",
            )

            return 202, AgentExecuteResponse(
                status="PENDING_APPROVAL",
                decision="REQUIRE_HITL",
                intent_id=pending_intent.intent_id,
                action_type=action_type,
                target_row_id=target_row_id,
                trust_count=current_trust,
                trust_threshold=trust_threshold,
                message="Trust score is below threshold. Human-in-the-Loop approval required.",
            )

        # Case 3: Trust threshold reached -> Autonomous execution (HTTP 200)
        action_log, _ = action_service.execute_action(
            db=db,
            action_type=action_type,
            target_row_id=target_row_id,
        )

        trace_logger.log_decision(
            request_id=request_id,
            prompt=prompt,
            source_row_id=target_row_id,
            raw_llm_output=raw_llm_output,
            validated_payload=validated_payload,
            guardrail_checks=guardrail_result["checks"],
            trust_count=current_trust,
            trust_threshold=trust_threshold,
            decision="EXECUTE_AUTONOMOUS",
            action_id=action_log.action_id,
            action_outcome="EXECUTED",
        )

        return 200, AgentExecuteResponse(
            status="EXECUTED",
            decision="EXECUTE_AUTONOMOUS",
            action_id=action_log.action_id,
            action_type=action_type,
            target_row_id=target_row_id,
            trust_count=current_trust,
            trust_threshold=trust_threshold,
            message="Action executed autonomously based on earned trust.",
        )


agent_service = AgentService()
