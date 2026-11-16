"""Tests for Deterministic Rollback, Restoration API, and Trust Penalties."""

from app.models.content_queue import ContentQueue
from app.models.trust_store import TrustStore
from app.models.action_log import ActionLog, RestorationLog


def test_restoration_recovers_state_and_decreases_trust(client, db_session):
    """Test 5: Restoring an action recovers previous state and decreases trust score by 1."""
    row = ContentQueue(id=30, content_text="Important payload to test restore", status="PENDING")
    db_session.add(row)

    # Set trust to 3 so action can execute autonomously
    trust_rec = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first()
    trust_rec.success_count = 3
    db_session.commit()

    # Step 1: Execute purge autonomously
    exec_res = client.post("/api/agent/execute", json={"prompt": "purge row 30"})
    assert exec_res.status_code == 200
    action_id = exec_res.json()["action_id"]

    # Verify content mutated
    db_session.refresh(row)
    assert row.status == "PURGED"

    # Step 2: Restore the action
    restore_res = client.post("/api/system/restore", json={"action_id": action_id})
    assert restore_res.status_code == 200
    data = restore_res.json()

    assert data["restored"] is True
    assert data["current_trust_count"] == 2  # Trust decreased from 3 to 2

    # Step 3: Verify content_queue row is restored to previous PENDING state
    db_session.refresh(row)
    assert row.status == "PENDING"
    assert row.content_text == "Important payload to test restore"

    # Step 4: Verify action_log is marked restored and restoration_log created
    action_log = db_session.query(ActionLog).filter(ActionLog.action_id == action_id).first()
    assert action_log.is_restored is True

    restorations = db_session.query(RestorationLog).filter(RestorationLog.action_id == action_id).all()
    assert len(restorations) == 1


def test_trust_penalty_cannot_become_negative(client, db_session):
    """Verify that restoring when trust is 0 does not reduce trust below 0."""
    row = ContentQueue(id=31, content_text="Zero trust restore test", status="PENDING")
    db_session.add(row)

    # Trust is 0
    trust_rec = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first()
    trust_rec.success_count = 0
    db_session.commit()

    # Trigger via HITL approval
    res = client.post("/api/agent/execute", json={"prompt": "purge row 31"})
    intent_id = res.json()["intent_id"]
    appr = client.post(f"/api/hitl/approve/{intent_id}")
    action_id = appr.json()["action_id"]
    # Trust became 1 after approval

    # Manually reset trust to 0 to test floor
    trust_rec = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first()
    trust_rec.success_count = 0
    db_session.commit()

    # Call restore
    restore_res = client.post("/api/system/restore", json={"action_id": action_id})
    assert restore_res.status_code == 200
    assert restore_res.json()["current_trust_count"] == 0

    # Verify trust in DB is still 0 (non-negative)
    db_session.refresh(trust_rec)
    assert trust_rec.success_count == 0


def test_restore_idempotency(client, db_session):
    """Test 7 (Part B): Calling restore multiple times does not apply duplicate trust penalties."""
    row = ContentQueue(id=32, content_text="Idempotency restore test", status="PENDING")
    db_session.add(row)

    trust_rec = db_session.query(TrustStore).filter(TrustStore.action_type == "purge").first()
    trust_rec.success_count = 3
    db_session.commit()

    # Execute
    res = client.post("/api/agent/execute", json={"prompt": "purge row 32"})
    action_id = res.json()["action_id"]

    # First restore: trust drops from 3 to 2
    r1 = client.post("/api/system/restore", json={"action_id": action_id})
    assert r1.status_code == 200
    assert r1.json()["current_trust_count"] == 2

    # Second restore: trust MUST NOT decrease again!
    r2 = client.post("/api/system/restore", json={"action_id": action_id})
    assert r2.status_code == 200
    assert r2.json()["current_trust_count"] == 2
    assert "already been restored" in r2.json()["message"]
