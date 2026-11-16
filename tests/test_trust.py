"""Tests for Trust Store and Progressive Autonomy escalation."""

from app.models.content_queue import ContentQueue
from app.models.trust_store import TrustStore
from app.models.action_log import ActionLog
from app.models.pending_intent import PendingIntent
from app.config import settings


def test_progressive_autonomy_when_threshold_reached(client, db_session):
    """Test 4: When trust equals or exceeds threshold, action executes autonomously without HITL."""
    row = ContentQueue(id=20, content_text="Autonomous execution candidate", status="PENDING")
    db_session.add(row)

    # Set trust directly to TRUST_THRESHOLD (e.g. 3)
    trust_rec = db_session.query(TrustStore).filter(TrustStore.action_type == "mark_posted").first()
    trust_rec.success_count = settings.TRUST_THRESHOLD
    db_session.commit()

    # Request mark_posted on row 20
    res = client.post("/api/agent/execute", json={"prompt": "mark post row 20"})
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "EXECUTED"
    assert data["decision"] == "EXECUTE_AUTONOMOUS"
    assert data["action_id"] is not None
    assert data["intent_id"] is None

    # Verify content mutated immediately
    db_session.refresh(row)
    assert row.status == "POSTED"

    # Verify action log exists
    log = db_session.query(ActionLog).filter(ActionLog.action_id == data["action_id"]).first()
    assert log is not None
    assert log.previous_state["status"] == "PENDING"
    assert log.new_state["status"] == "POSTED"

    # Verify NO pending intent was created
    pending = db_session.query(PendingIntent).filter(PendingIntent.target_row_id == 20).all()
    assert len(pending) == 0


def test_trust_progression_lifecycle(client, db_session):
    """Verify progressive escalation from HITL approval to autonomous execution."""
    # Seed 4 rows
    rows = [ContentQueue(id=i, content_text=f"Queue item {i}", status="PENDING") for i in range(101, 105)]
    db_session.add_all(rows)
    db_session.commit()

    # Step 1: Trust = 0 -> Requires approval
    r1 = client.post("/api/agent/execute", json={"prompt": "purge row 101"})
    assert r1.status_code == 202
    intent_1 = r1.json()["intent_id"]
    client.post(f"/api/hitl/approve/{intent_1}")

    # Trust is now 1
    t1 = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first().success_count
    assert t1 == 1

    # Step 2: Trust = 1 -> Still requires approval
    r2 = client.post("/api/agent/execute", json={"prompt": "purge row 102"})
    assert r2.status_code == 202
    intent_2 = r2.json()["intent_id"]
    client.post(f"/api/hitl/approve/{intent_2}")

    # Trust is now 2
    t2 = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first().success_count
    assert t2 == 2

    # Step 3: Trust = 2 -> Still requires approval
    r3 = client.post("/api/agent/execute", json={"prompt": "purge row 103"})
    assert r3.status_code == 202
    intent_3 = r3.json()["intent_id"]
    client.post(f"/api/hitl/approve/{intent_3}")

    # Trust is now 3 (Equal to TRUST_THRESHOLD)
    t3 = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first().success_count
    assert t3 == settings.TRUST_THRESHOLD

    # Step 4: Now autonomous! Next purge executes with HTTP 200 without approval
    r4 = client.post("/api/agent/execute", json={"prompt": "purge row 104"})
    assert r4.status_code == 200
    assert r4.json()["status"] == "EXECUTED"
    assert r4.json()["decision"] == "EXECUTE_AUTONOMOUS"
