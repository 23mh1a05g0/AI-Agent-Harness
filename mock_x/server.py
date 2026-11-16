"""Standalone Mock X (Twitter) Web Server with Login, Session, Composer, and Feed."""

import os
import uuid
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Response, Request, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Mock X Social Platform", description="Local mock social network for browser automation testing")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# In-memory session and posts store
VALID_SESSIONS: Dict[str, str] = {}  # session_id -> username
POSTS: List[Dict[str, Any]] = [
    {"id": 1, "username": "system_admin", "content": "Welcome to the Mock X local network!", "timestamp": "2026-11-16T12:00:00Z"},
    {"id": 2, "username": "ai_agent", "content": "Harness initialized with safety guardrails.", "timestamp": "2026-11-16T12:05:00Z"},
]


class LoginRequest(BaseModel):
    username: str
    password: str


class ComposeRequest(BaseModel):
    content: str


@app.get("/", response_class=HTMLResponse)
def get_index():
    """Serve the single-page application."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Mock X Server Running</h1>")


@app.post("/api/login")
def login(creds: LoginRequest, response: Response):
    """Authenticate user and issue session cookie."""
    if not creds.username or not creds.password:
        raise HTTPException(status_code=400, detail="Username and password required")

    session_id = str(uuid.uuid4())
    VALID_SESSIONS[session_id] = creds.username

    response.set_cookie(
        key="mock_x_session",
        value=session_id,
        httponly=False,
        max_age=86400,
        samesite="lax",
    )
    return {"status": "authenticated", "username": creds.username, "session_id": session_id}


@app.get("/api/session")
def check_session(request: Request):
    """Verify if the current session cookie is valid."""
    session_id = request.cookies.get("mock_x_session")
    if session_id and session_id in VALID_SESSIONS:
        return {"authenticated": True, "username": VALID_SESSIONS[session_id]}
    return {"authenticated": False}


@app.get("/api/posts")
def get_posts():
    """Retrieve social post feed."""
    return {"posts": list(reversed(POSTS))}


@app.post("/api/compose")
def compose_post(post: ComposeRequest, request: Request):
    """Publish a new post if session is authenticated."""
    session_id = request.cookies.get("mock_x_session")
    if not session_id or session_id not in VALID_SESSIONS:
        raise HTTPException(status_code=401, detail="Authentication required to publish posts")

    username = VALID_SESSIONS[session_id]
    new_post = {
        "id": len(POSTS) + 1,
        "username": username,
        "content": post.content,
        "timestamp": "2026-11-16T21:00:00Z",
    }
    POSTS.append(new_post)
    return {"status": "published", "post": new_post}


@app.post("/api/logout")
def logout(response: Response, request: Request):
    """Clear session cookie."""
    session_id = request.cookies.get("mock_x_session")
    if session_id in VALID_SESSIONS:
        del VALID_SESSIONS[session_id]
    response.delete_cookie("mock_x_session")
    return {"status": "logged_out"}


if __name__ == "__main__":
    uvicorn.run("mock_x.server:app", host="127.0.0.1", port=8001, reload=False)
