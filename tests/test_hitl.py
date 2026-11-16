"""Tests for Human-in-the-Loop (HITL) intents, approval, and rejection."""

from app.models.content_queue import ContentQueue
from app.models.pending_intent import PendingIntent
from app.models.action_log import ActionLog
from app.models.trust_store import TrustStore


def test_untrusted_action_requires_hitl(client, db_session):
    """Test 2: When trust is below threshold, request returns 202 and creates pending intent."""
    row = ContentQueue(id=10, content_text="Sample content to purge", status="PENDING")
    db_session.add(row)
    db_session.commit()

    # Verify initial trust is 0
    trust_rec = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first()
    assert trust_rec.success_count == 0

    # Execute prompt
    res = client.post("/api/agent/execute", json={"prompt": "purge row 10"})
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "PENDING_APPROVAL"
    assert data["decision"] == "REQUIRE_HITL"
    assert "intent_id" in data
    assert data["intent_id"] is not None

    # Verify content remains UNCHANGED
    db_session.refresh(row)
    assert row.status == "PENDING"

    # Verify pending intent exists in DB
    intent = db_session.query(PendingIntent).filter(PendingIntent.intent_id == data["intent_id"]).first()
    assert intent is not None
    assert intent.status == "PENDING"
    assert intent.target_row_id == 10
    assert intent.action_type == "purge"


def test_hitl_approval_mutates_content_and_increases_trust(client, db_session):
    """Test 3: Approving pending intent mutates content, creates action log, increments trust."""
    row = ContentQueue(id=10, content_text="Sample content to purge", status="PENDING")
    db_session.add(row)
    db_session.commit()

    # Step 1: Trigger untrusted action
    res = client.post("/api/agent/execute", json={"prompt": "purge row 10"})
    assert res.status_code == 202
    intent_id = res.json()["intent_id"]

    # Step 2: Approve intent
    appr_res = client.post(f"/api/hitl/approve/{intent_id}")
    assert appr_res.status_code == 200
    appr_data = appr_res.json()
    assert appr_data["status"] == "EXECUTED"
    assert appr_data["new_trust_count"] == 1

    # Step 3: Verify content mutated
    db_session.refresh(row)
    assert row.status == "PURGED"

    # Step 4: Verify action_log created with exact snapshots
    action_log = db_session.query(ActionLog).filter(ActionLog.action_id == appr_data["action_id"]).first()
    assert action_log is not None
    assert action_log.previous_state["status"] == "PENDING"
    assert action_log.new_state["status"] == "PURGED"

    # Step 5: Verify trust store incremented by exactly 1
    trust_rec = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first()
    assert trust_rec.success_count == 1


def test_hitl_rejection_prevents_mutation(client, db_session):
    """Test rejection: Intent is marked REJECTED and no mutation occurs."""
    row = ContentQueue(id=15, content_text="Sample content for rejection", status="PENDING")
    db_session.add(row)
    db_session.commit()

    # Trigger untrusted action
    res = client.post("/api/agent/execute", json={"prompt": "purge row 15"})
    intent_id = res.json()["intent_id"]

    # Reject intent
    rej_res = client.post(f"/api/hitl/reject/{intent_id}")
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED"

    # Verify content still PENDING
    db_session.refresh(row)
    assert row.status == "PENDING"

    # Verify no action log created
    action_logs = db_session.query(ActionLog).filter(ActionLog.target_row_id == 15).all()
    assert len(action_logs) == 0

    # Verify trust is not increased
    trust_rec = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first()
    assert trust_rec.success_count == 0
