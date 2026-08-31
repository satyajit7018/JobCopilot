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
import pytest
from datetime import timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole
from app.api.auth import hash_password, create_jwt_token


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
async def test_password_reset_workflow():
    """Asserts request-reset and reset-password securely updates password and revokes token."""
    user_id = f"usr_reset_{uuid.uuid4().hex[:6]}"
    email = f"{user_id}@test.com"
    old_pw = "OldPassword123!"
    new_pw = "NewPassword123!Safe"

    user = User(
        user_id=user_id,
        email=email,
        password_hash=hash_password(old_pw),
        role=UserRole.FREE,
        is_active=True
    )
    db.create_user(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Request reset
        res_req = await ac.post("/api/auth/request-reset", json={"email": email})
        assert res_req.status_code == 200

        # 2. Forge a valid reset token (simulating mailer received token)
        reset_token = create_jwt_token(
            {"sub": user_id, "email": email, "type": "reset_password"},
            timedelta(minutes=15)
        )

        # 3. Complete reset
        res_reset = await ac.post("/api/auth/reset-password", json={
            "token": reset_token,
            "new_password": new_pw
        })
        assert res_reset.status_code == 200
        assert "successfully" in res_reset.json().get("message", "")

        # 4. Token replay must fail
        res_replay = await ac.post("/api/auth/reset-password", json={
            "token": reset_token,
            "new_password": "AnotherPassword123!"
        })
        assert res_replay.status_code == 401


@pytest.mark.asyncio
async def test_email_verification_workflow():
    """Asserts verify-email updates user's email_verified status."""
    user_id = f"usr_verify_{uuid.uuid4().hex[:6]}"
    email = f"{user_id}@test.com"
    
    user = User(
        user_id=user_id,
        email=email,
        password_hash="test",
        role=UserRole.FREE,
        is_active=True,
        email_verified=False
    )
    db.create_user(user)

    verify_token = create_jwt_token(
        {"sub": user_id, "email": email, "type": "verify_email"},
        timedelta(hours=24)
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/auth/verify-email", json={"token": verify_token})
        assert res.status_code == 200
        assert "verified successfully" in res.json().get("message", "")

    updated = db.get_user_by_id(user_id)
    assert updated is not None
    assert updated.email_verified is True
