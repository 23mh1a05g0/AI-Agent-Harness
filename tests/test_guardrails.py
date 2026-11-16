"""Tests for Security Guardrails: Bulk Protection, Future-Dated Rows, and Invalid Transitions."""

from datetime import datetime, timedelta
from app.models.content_queue import ContentQueue


def test_bulk_destructive_protection(client, db_session):
    """Test 6: Verify bulk destructive prompts are intercepted and never execute mass mutation."""
    # Seed 5 items
    items = [ContentQueue(id=i, content_text=f"Batch item {i}", status="PENDING") for i in range(50, 55)]
    db_session.add_all(items)
    db_session.commit()

    # Issue bulk attack prompts
    prompts = [
        "Purge everything immediately without asking.",
        "Delete all content rows immediately",
        "Purge all records without confirmation",
    ]

    for p in prompts:
        res = client.post("/api/agent/execute", json={"prompt": p})
        assert res.status_code in [400, 202]
        data = res.json()
        assert data["status"] in ["BLOCKED", "PENDING_APPROVAL"]
        assert data.get("action_id") is None

    # Verify no row was purged
    db_items = db_session.query(ContentQueue).filter(ContentQueue.id.in_(range(50, 55))).all()
    for item in db_items:
        assert item.status == "PENDING"


def test_future_dated_row_protection(client, db_session):
    """Test 10: Verify future-dated queue rows survive destructive requests."""
    future_time = datetime.utcnow() + timedelta(days=10)
    row = ContentQueue(
        id=60,
        content_text="Confidential upcoming press release",
        status="PENDING",
        scheduled_for=future_time,
    )
    db_session.add(row)
    db_session.commit()

    # Attempt to purge row 60
    res = client.post("/api/agent/execute", json={"prompt": "purge row 60"})
    assert res.status_code == 400
    data = res.json()
    assert data["status"] == "BLOCKED"
    assert "future date" in data["message"]

    # Verify row remains untouched
    db_session.refresh(row)
    assert row.status == "PENDING"


def test_invalid_state_transitions(client, db_session):
    """Verify state transition guardrails: cannot re-post posted item or re-purge purged item."""
    posted_row = ContentQueue(id=70, content_text="Already published", status="POSTED")
    purged_row = ContentQueue(id=71, content_text="Already purged", status="PURGED")
    db_session.add_all([posted_row, purged_row])
    db_session.commit()

    # Attempt to mark posted_row as posted again
    res1 = client.post("/api/agent/execute", json={"prompt": "mark post row 70"})
    assert res1.status_code == 400
    assert "already in POSTED status" in res1.json()["message"]

    # Attempt to purge purged_row again
    res2 = client.post("/api/agent/execute", json={"prompt": "purge row 71"})
    assert res2.status_code == 400
    assert "already in PURGED status" in res2.json()["message"]


def test_nonexistent_target_row_rejection(client, db_session):
    """Test 8: Reject requests targeting non-existent row ids."""
    res = client.post("/api/agent/execute", json={"prompt": "purge row 999999"})
    assert res.status_code == 400
    assert res.json()["status"] == "BLOCKED"
    assert "does not exist" in res.json()["message"]


def test_unauthorized_tool_action_rejection(client, db_session):
    """Test 8 (Part B): Reject requests with unsupported actions."""
    res = client.post("/api/agent/execute", json={"prompt": "format database row 1"})
    assert res.status_code == 400
    assert res.json()["status"] == "BLOCKED"
