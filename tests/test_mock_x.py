"""Tests for Mock X Social Platform server endpoints."""

from fastapi.testclient import TestClient
from mock_x.server import app as mock_x_app

client = TestClient(mock_x_app)


def test_mock_x_html_and_unauthenticated_session():
    """Verify Mock X serves UI and starts unauthenticated."""
    res = client.get("/")
    assert res.status_code == 200
    assert "Mock X" in res.text

    session_res = client.get("/api/session")
    assert session_res.status_code == 200
    assert session_res.json()["authenticated"] is False


def test_mock_x_authentication_and_posting_lifecycle():
    """Verify login, session check, posting, feed inspection, and logout."""
    # 1. Login
    login_res = client.post("/api/login", json={"username": "agent_alpha", "password": "securepassword"})
    assert login_res.status_code == 200
    assert login_res.json()["status"] == "authenticated"
    assert "mock_x_session" in login_res.cookies

    # 2. Check session with cookie
    sess_res = client.get("/api/session")
    assert sess_res.status_code == 200
    assert sess_res.json()["authenticated"] is True
    assert sess_res.json()["username"] == "agent_alpha"

    # 3. Submit post
    post_text = "Verified post from automated test harness."
    compose_res = client.post("/api/compose", json={"content": post_text})
    assert compose_res.status_code == 200
    assert compose_res.json()["status"] == "published"
    assert compose_res.json()["post"]["content"] == post_text

    # 4. View feed
    feed_res = client.get("/api/posts")
    assert feed_res.status_code == 200
    posts = feed_res.json()["posts"]
    assert any(p["content"] == post_text for p in posts)

    # 5. Logout
    logout_res = client.post("/api/logout")
    assert logout_res.status_code == 200
    assert client.get("/api/session").json()["authenticated"] is False
