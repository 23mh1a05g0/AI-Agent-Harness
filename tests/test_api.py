"""Tests for API Endpoints, Database Schema, Submission Metadata, and Persistence."""

import json
from pathlib import Path
from sqlalchemy import inspect
from app.models.content_queue import ContentQueue
from app.models.trust_store import TrustStore
from app.models.action_log import ActionLog
from app.models.pending_intent import PendingIntent


def test_database_schema_exists(db_session):
    """Test 1: Verify all 4 required database tables and columns exist."""
    inspector = inspect(db_session.bind)
    tables = inspector.get_table_names()

    required_tables = ["content_queue", "action_log", "trust_store", "pending_intents"]
    for t in required_tables:
        assert t in tables, f"Required table '{t}' is missing from database schema"

    # Verify content_queue columns
    cq_cols = {c["name"] for c in inspector.get_columns("content_queue")}
    assert {"id", "content_text", "status"}.issubset(cq_cols)

    # Verify action_log columns
    al_cols = {c["name"] for c in inspector.get_columns("action_log")}
    assert {"action_id", "action_type", "target_row_id", "previous_state", "new_state"}.issubset(al_cols)

    # Verify trust_store columns
    ts_cols = {c["name"] for c in inspector.get_columns("trust_store")}
    assert {"action_type", "success_count"}.issubset(ts_cols)

    # Verify pending_intents columns
    pi_cols = {c["name"] for c in inspector.get_columns("pending_intents")}
    assert {"intent_id", "action_type", "target_row_id", "prompt", "validated_payload", "status"}.issubset(pi_cols)


def test_submission_json_structure():
    """Verify submission.json is valid and contains matching configuration."""
    submission_file = Path(__file__).resolve().parent.parent / "submission.json"
    assert submission_file.exists(), "submission.json must exist in root repository"

    with open(submission_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "testData" in data
    assert "mockLlmEnabled" in data["testData"]
    assert data["testData"]["mockLlmEnabled"] is True
    assert "apiPort" in data["testData"]
    assert data["testData"]["apiPort"] == 8000


def test_pending_intent_persistence_across_sessions(client, db_session):
    """Test 9: Pending actions survive application restarts and persist in PostgreSQL."""
    row = ContentQueue(id=80, content_text="Pending restart persistence test", status="PENDING")
    db_session.add(row)
    db_session.commit()

    # Trigger action to create pending intent
    res = client.post("/api/agent/execute", json={"prompt": "purge row 80"})
    assert res.status_code == 202
    intent_id = res.json()["intent_id"]

    # Query through /api/hitl/pending
    pending_res = client.get("/api/hitl/pending")
    assert pending_res.status_code == 200
    pending_list = pending_res.json()
    assert any(item["intent_id"] == intent_id for item in pending_list)

    # Simulate restart by reading directly from a fresh database session
    from tests.conftest import TestingSessionLocal
    fresh_session = TestingSessionLocal()
    saved_intent = fresh_session.query(PendingIntent).filter(PendingIntent.intent_id == intent_id).first()
    assert saved_intent is not None
    assert saved_intent.status == "PENDING"
    fresh_session.close()


def test_approval_idempotency(client, db_session):
    """Test 7 (Part A): Repeated approvals cannot execute twice or increase trust twice."""
    row = ContentQueue(id=90, content_text="Idempotent approval test", status="PENDING")
    db_session.add(row)
    db_session.commit()

    # Create pending intent
    res = client.post("/api/agent/execute", json={"prompt": "purge row 90"})
    intent_id = res.json()["intent_id"]

    # First approval
    appr1 = client.post(f"/api/hitl/approve/{intent_id}")
    assert appr1.status_code == 200
    trust_after_first = appr1.json()["new_trust_count"]

    # Second approval
    appr2 = client.post(f"/api/hitl/approve/{intent_id}")
    assert appr2.status_code == 200
    trust_after_second = appr2.json()["new_trust_count"]

    # Trust MUST NOT increase again!
    assert trust_after_second == trust_after_first


def test_system_inspection_endpoints(client, db_session):
    """Verify system inspection routes: /, /health, /api/system/queue, /api/system/trust, /api/system/actions."""
    # 1. Welcome endpoint
    welcome = client.get("/")
    assert welcome.status_code == 200
    assert welcome.json()["mock_llm_enabled"] is True

    # 2. Health check
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    # 3. Content queue
    queue = client.get("/api/system/queue")
    assert queue.status_code == 200
    assert isinstance(queue.json(), list)

    # 4. Trust store
    trust = client.get("/api/system/trust")
    assert trust.status_code == 200
    assert isinstance(trust.json(), list)

    # 5. Actions log
    actions = client.get("/api/system/actions")
    assert actions.status_code == 200
    assert isinstance(actions.json(), list)
