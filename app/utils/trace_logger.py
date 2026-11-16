"""JSONL Trace Logger for auditing and replaying agent decisions."""

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional
from app.config import settings

_trace_lock = threading.Lock()


class TraceLogger:
    """Thread-safe append-only logger writing to traces.jsonl."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or settings.TRACES_FILE_PATH
        self._ensure_file_path()

    def _ensure_file_path(self):
        directory = os.path.dirname(self.file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def log_decision(
        self,
        request_id: str,
        prompt: str,
        source_row_id: Optional[int],
        raw_llm_output: Any,
        validated_payload: Optional[Dict[str, Any]],
        guardrail_checks: Dict[str, Any],
        trust_count: int,
        trust_threshold: int,
        decision: str,
        intent_id: Optional[str] = None,
        action_id: Optional[str] = None,
        action_outcome: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an agent decision and write as a single line JSON."""
        trace_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": request_id,
            "prompt": prompt,
            "source_row_id": source_row_id,
            "raw_llm_output": raw_llm_output,
            "validated_payload": validated_payload,
            "guardrail_checks": guardrail_checks,
            "trust_count": trust_count,
            "trust_threshold": trust_threshold,
            "decision": decision,
            "intent_id": intent_id,
            "action_id": action_id,
            "action_outcome": action_outcome,
        }

        # Write to JSONL
        with _trace_lock:
            self._ensure_file_path()
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace_record) + "\n")

        return trace_record


trace_logger = TraceLogger()
