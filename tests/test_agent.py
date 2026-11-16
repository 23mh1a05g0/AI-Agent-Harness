"""Tests for Agent Service, LLM tool calling, schema validation, and trace logging."""

import os
import json
import pytest
from app.services.llm_service import llm_service
from app.schemas.agent import ToolCallPayload
from app.config import settings
from pydantic import ValidationError


def test_mock_llm_tool_generation():
    """Verify deterministic mock LLM extracts tool and row id correctly."""
    # Test purge
    purge_call = llm_service.generate_tool_call("Please purge row 10 immediately")
    assert purge_call["action_type"] == "purge"
    assert purge_call["target_row_id"] == 10

    # Test mark_posted
    post_call = llm_service.generate_tool_call("Mark post #42 as posted")
    assert post_call["action_type"] == "mark_posted"
    assert post_call["target_row_id"] == 42

    # Test explicit target override
    override_call = llm_service.generate_tool_call("purge this item", target_row_id=7)
    assert override_call["action_type"] == "purge"
    assert override_call["target_row_id"] == 7


def test_pydantic_schema_validation():
    """Verify strict Pydantic validation rejects invalid actions."""
    # Valid payloads
    valid_purge = ToolCallPayload(action_type="purge", target_row_id=1)
    assert valid_purge.action_type == "purge"

    valid_post = ToolCallPayload(action_type="mark_posted", target_row_id=2)
    assert valid_post.action_type == "mark_posted"

    # Invalid action type
    with pytest.raises(ValidationError):
        ToolCallPayload(action_type="drop_database", target_row_id=1)

    with pytest.raises(ValidationError):
        ToolCallPayload(action_type="bulk_purge", target_row_id=1)


def test_trace_logging(client, db_session):
    """Verify every agent decision writes a JSONL trace entry."""
    from app.models.content_queue import ContentQueue

    row = ContentQueue(id=10, content_text="Test for trace logging", status="PENDING")
    db_session.add(row)
    db_session.commit()

    # Trigger agent execution
    res = client.post("/api/agent/execute", json={"prompt": "purge row 10"})
    assert res.status_code in [200, 202]

    # Verify trace file exists and contains valid JSON lines
    trace_path = settings.TRACES_FILE_PATH
    assert os.path.exists(trace_path), f"Trace file {trace_path} does not exist"

    with open(trace_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) > 0
        last_trace = json.loads(lines[-1])

        assert "timestamp" in last_trace
        assert "request_id" in last_trace
        assert "prompt" in last_trace
        assert "guardrail_checks" in last_trace
        assert "trust_count" in last_trace
        assert "decision" in last_trace
