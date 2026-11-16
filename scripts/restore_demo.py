"""Demonstration script showcasing state execution, deterministic rollback, and trust penalty."""

import os
import sys

# Ensure repo root is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from app.config import settings

BASE_URL = os.environ.get("HARNESS_API_URL", f"http://127.0.0.1:{settings.API_PORT}")


def run_restore_demo():
    print(f"[*] Running Restore & Trust Penalty Demo on: {BASE_URL}")

    # Use live client or FastAPI TestClient fallback
    client = None
    try:
        if httpx.get(f"{BASE_URL}/health", timeout=3.0).status_code == 200:
            client = httpx.Client(base_url=BASE_URL, timeout=10.0)
    except Exception:
        pass

    if client is None:
        print("[*] Using embedded FastAPI test client...")
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

    # 1. Inspect initial trust
    trust_res = client.get("/api/system/trust")
    initial_trust = {item["action_type"]: item["success_count"] for item in trust_res.json()}
    print(f"[+] Initial trust counters: {initial_trust}")

    # 2. Trigger an action (or approve a pending one)
    print("[*] Requesting purge of row 1...")
    res = client.post("/api/agent/execute", json={"prompt": "purge row 1"})
    print(f"[+] Response ({res.status_code}): {res.json().get('status')} - {res.json().get('message')}")

    action_id = None
    if res.status_code == 202:
        intent_id = res.json()["intent_id"]
        print(f"[*] Action paused for HITL. Approving intent: {intent_id}...")
        appr_res = client.post(f"/api/hitl/approve/{intent_id}")
        assert appr_res.status_code == 200, f"Approval failed: {appr_res.text}"
        action_id = appr_res.json()["action_id"]
        print(f"[+] Intent approved. Action ID: {action_id}. Trust incremented: {appr_res.json()['new_trust_count']}")
    elif res.status_code == 200:
        action_id = res.json()["action_id"]
        print(f"[+] Autonomous execution completed. Action ID: {action_id}")
    else:
        # Check action history
        actions = client.get("/api/system/actions").json()
        if actions:
            action_id = actions[0]["action_id"]

    assert action_id, "Could not obtain an action_id to restore"

    # 3. Check queue row status before restore
    queue = client.get("/api/system/queue").json()
    target_row = next((r for r in queue if r["id"] == 1), None)
    if target_row:
        print(f"[+] State before restoration: Row 1 status = {target_row['status']}")

    # 4. Perform restoration
    print(f"[*] Calling /api/system/restore for action {action_id}...")
    restore_res = client.post("/api/system/restore", json={"action_id": action_id})
    assert restore_res.status_code == 200, f"Restore failed: {restore_res.text}"
    restore_data = restore_res.json()
    print(f"[+] Restore outcome: {restore_data['message']}")
    print(f"[+] Previous state restored: {restore_data['previous_state']}")
    print(f"[+] Current trust score after penalty: {restore_data['current_trust_count']}")

    # 5. Verify row state in queue
    queue_after = client.get("/api/system/queue").json()
    target_after = next((r for r in queue_after if r["id"] == 1), None)
    if target_after:
        print(f"[+] State after restoration: Row 1 status = {target_after['status']}")

    # 6. Verify idempotency: second restore must not penalize trust again
    print("[*] Testing restore idempotency with second call...")
    restore_res2 = client.post("/api/system/restore", json={"action_id": action_id})
    assert restore_res2.status_code == 200
    assert restore_res2.json()["current_trust_count"] == restore_data["current_trust_count"]
    count2 = restore_res2.json()["current_trust_count"]
    print(f"[+] Idempotent restore verified. Trust remains at {count2}")

    print("[PASS] State restoration and trust penalty demonstration complete.")
    return True


if __name__ == "__main__":
    success = run_restore_demo()
    sys.exit(0 if success else 1)
