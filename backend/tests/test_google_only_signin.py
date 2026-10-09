"""
Google-only sign-in at launch.

Production has no email sender, so email + password accounts (which need
confirmation and reset emails) are off there unless PASSWORD_AUTH_ENABLED=true.
Google-only users can still delete their account by confirming with Google.
"""

import importlib
import time
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token, hash_password
from app.core.database import db
from app.core.models import User, UserRole
from app.core.settings import settings
from app.main import app

client = TestClient(app)
# The routers package re-exports router objects under the module names.
account_router = importlib.import_module("app.api.routers.account_router")


def _user() -> User:
    user = User(
        user_id=f"usr_{uuid.uuid4().hex[:12]}",
        email=f"google_only_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password(uuid.uuid4().hex),  # what Google sign-up stores
        full_name="Google Only",
        role=UserRole.FREE,
        is_active=True,
        email_verified=True,
    )
    db.create_user(user)
    return user


def _headers(user: User) -> dict:
    token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": "FREE", "type": "access"},
        timedelta(minutes=60),
    )
    return {"Authorization": f"Bearer {token}"}


def test_password_auth_defaults_follow_environment(monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_AUTH_ENABLED", None)
    monkeypatch.setattr(settings, "ENV", "development")
    assert settings.password_auth_enabled is True
    monkeypatch.setattr(settings, "ENV", "production")
    assert settings.password_auth_enabled is False
    monkeypatch.setattr(settings, "PASSWORD_AUTH_ENABLED", True)
    assert settings.password_auth_enabled is True


def test_register_and_login_refused_when_password_auth_off(monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_AUTH_ENABLED", False)
    email = f"nope_{uuid.uuid4().hex[:8]}@test.com"
    res = client.post("/api/auth/register", json={"email": email, "password": "Password123!", "full_name": "No"})
    assert res.status_code == 403
    assert db.get_user_by_email(email) is None
    res = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert res.status_code == 403
    assert client.get("/api/auth/public-config").json()["password_auth_enabled"] is False


def _fake_google(email: str, issued_at: float):
    def verify(_token):
        return {"email": email, "email_verified": True, "iat": int(issued_at)}
    return verify


def test_google_only_user_can_delete_with_fresh_google_confirmation(monkeypatch):
    user = _user()
    try:
        monkeypatch.setattr(account_router, "verify_google_id_token", _fake_google(user.email, time.time()))
        res = client.request("DELETE", "/api/account", headers=_headers(user),
                             json={"confirm_email": user.email, "google_id_token": "tok"})
        assert res.status_code == 200
        assert db.get_user_by_id(user.user_id) is None
    finally:
        db.hard_delete_user_account(user.user_id)


def test_google_confirmation_must_be_same_account_and_recent(monkeypatch):
    user = _user()
    try:
        monkeypatch.setattr(account_router, "verify_google_id_token", _fake_google("someone@else.com", time.time()))
        res = client.request("DELETE", "/api/account", headers=_headers(user),
                             json={"confirm_email": user.email, "google_id_token": "tok"})
        assert res.status_code == 403

        monkeypatch.setattr(account_router, "verify_google_id_token", _fake_google(user.email, time.time() - 3600))
        res = client.request("DELETE", "/api/account", headers=_headers(user),
                             json={"confirm_email": user.email, "google_id_token": "tok"})
        assert res.status_code == 403
        assert db.get_user_by_id(user.user_id) is not None
    finally:
        db.hard_delete_user_account(user.user_id)
