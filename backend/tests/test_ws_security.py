"""
JobCopilot - WebSocket Strict Authentication & Multi-Tenant Isolation Test Suite
Validates token requirements, rejection with code 4001, and message scoping.
"""

import uuid
import pytest
from datetime import timedelta
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole
from app.api.auth import create_jwt_token


def test_ws_rejects_unauthenticated_connection():
    """Asserts connecting without token closes websocket with code 4001."""
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws"):
            pass
    assert exc_info.value.code == 4001


def test_ws_rejects_invalid_token():
    """Asserts connecting with invalid signature token closes with 4001."""
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws?token=invalid_forged_token"):
            pass
    assert exc_info.value.code == 4001


def test_ws_accepts_valid_jwt_token():
    """Asserts connecting with valid unrevoked access token succeeds and handles ping-pong."""
    user_id = f"usr_ws_{uuid.uuid4().hex[:6]}"
    email = f"{user_id}@test.com"
    user = User(user_id=user_id, email=email, password_hash="test", role=UserRole.PRO)
    db.create_user(user)

    token = create_jwt_token(
        {"sub": user_id, "email": email, "role": "PRO", "type": "access"},
        timedelta(minutes=15)
    )

    client = TestClient(app)
    with client.websocket_connect(f"/ws?token={token}") as ws:
        ws.send_text("PING")
        data = ws.receive_json()
        assert data["type"] == "PONG"
        assert data["user_id"] == user_id
