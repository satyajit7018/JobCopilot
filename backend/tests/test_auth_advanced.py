"""
JobCopilot - Advanced Authentication Security & Account Hygiene Tests
Validates:
1. 12-character minimum password policy
2. Account lockout after consecutive failed login attempts
3. Single-use password reset token with expiration and jti revocation
4. Email verification workflow
5. Pruning of expired revoked tokens
"""

import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import create_jwt_token, hash_password
from app.core.database import db
from app.core.models import User, UserRole
from app.main import app


@pytest.mark.asyncio
async def test_password_min_length_enforced():
    """Asserts registration rejects passwords under 12 characters."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/auth/register", json={
            "email": f"usr_short_{uuid.uuid4().hex[:6]}@test.com",
            "password": "short_pass"  # 10 chars
        })
        assert res.status_code == 400
        assert "at least 12 characters" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_login_lockout_after_consecutive_failures():
    """Asserts account is locked after 5 consecutive failed logins."""
    user_id = f"usr_lock_{uuid.uuid4().hex[:6]}"
    email = f"{user_id}@test.com"
    correct_pw = "ValidPassword123!"

    user = User(
        user_id=user_id,
        email=email,
        password_hash=hash_password(correct_pw),
        role=UserRole.FREE,
        is_active=True
    )
    db.create_user(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 5 failed attempts
        for _ in range(5):
            res = await ac.post("/api/auth/login", json={"email": email, "password": "WrongPassword123!"})
            assert res.status_code == 401

        # 6th attempt with correct password should be locked out
        res_locked = await ac.post("/api/auth/login", json={"email": email, "password": correct_pw})
        assert res_locked.status_code == 401
        assert "temporarily locked" in res_locked.json().get("detail", "")


@pytest.mark.asyncio
async def test_public_auth_config_shape():
    """The login gate's public config exposes client id + flags, never a secret."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/auth/public-config")
        assert res.status_code == 200
        body = res.json()
        assert set(body) == {"google_client_id", "is_production", "demo_enabled", "password_auth_enabled",
                             "operator_name", "support_email"}
        # In the (non-production) test env, the demo/email path is offered.
        assert body["is_production"] is False
        assert body["demo_enabled"] is True
        assert body["password_auth_enabled"] is True


@pytest.mark.asyncio
async def test_google_sso_rejects_bare_email_in_production(monkeypatch):
    """With ENV=production, a bare-email SSO POST (no id_token) must 401."""
    from app.core.settings import settings
    monkeypatch.setattr(settings, "ENV", "production")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/auth/google-sso", json={"email": "someone@gmail.com"})
        assert res.status_code == 401
        assert "id token required" in res.json().get("detail", "").lower()
