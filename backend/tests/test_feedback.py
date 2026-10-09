"""Feedback from the app: stored per user, readable by admins only, deleted with the account."""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token
from app.core.database import db
from app.core.models import User, UserRole
from app.main import app


def _client(role=UserRole.FREE):
    user = User(user_id=f"usr_{uuid.uuid4().hex[:12]}", email=f"fb_{uuid.uuid4().hex[:8]}@test.com",
                password_hash="x", full_name="FB", role=role, is_active=True)
    db.create_user(user)
    tc = TestClient(app)
    token = create_jwt_token({"sub": user.user_id, "email": user.email, "role": role.value, "type": "access"}, timedelta(minutes=30))
    tc.headers["Authorization"] = f"Bearer {token}"
    return user, tc


def test_feedback_round_trip_and_deletion():
    user, tc = _client()
    admin, admin_tc = _client(UserRole.ADMIN)
    try:
        res = tc.post("/api/feedback", json={"message": "The Jobs page is great", "page": "/jobs?x=1"})
        assert res.status_code == 201
        assert tc.get("/api/admin/feedback").status_code == 403
        items = admin_tc.get("/api/admin/feedback").json()["feedback"]
        mine = [f for f in items if f["user_id"] == user.user_id]
        assert mine and mine[0]["email"] == user.email and mine[0]["page"] == "/jobs"
        db.hard_delete_user_account(user.user_id)
        assert not [f for f in admin_tc.get("/api/admin/feedback").json()["feedback"] if f["user_id"] == user.user_id]
    finally:
        db.hard_delete_user_account(user.user_id)
        db.hard_delete_user_account(admin.user_id)


def test_feedback_validation():
    user, tc = _client()
    try:
        assert tc.post("/api/feedback", json={"message": "x"}).status_code == 422
        assert tc.post("/api/feedback", json={"message": "y" * 5000}).status_code == 422
        assert TestClient(app).post("/api/feedback", json={"message": "hello there"}).status_code == 401
    finally:
        db.hard_delete_user_account(user.user_id)
