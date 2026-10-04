"""
JobCopilot - DELETE /api/account re-authentication tests.
A valid access token alone must not be enough to erase an account: the caller has
to re-prove the password, or a current TOTP code when MFA is enabled.
"""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token, hash_password
from app.core.credential_vault import cred_vault
from app.core.database import db
from app.core.mfa import mfa_engine
from app.core.models import User, UserRole
from app.main import app

client = TestClient(app)
PASSWORD = "Password123!"


def _create_user() -> User:
    user = User(
        user_id=f"usr_{uuid.uuid4().hex[:12]}",
        email=f"del_reauth_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password(PASSWORD),
        full_name="Delete Reauth",
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


def _delete(user: User, body: dict):
    return client.request("DELETE", "/api/account", json=body, headers=_headers(user))


def test_missing_password_is_rejected():
    user = _create_user()
    try:
        res = _delete(user, {"confirm_email": user.email})
        assert res.status_code == 400
        assert db.get_user_by_id(user.user_id) is not None

        res = _delete(user, {"confirm_email": user.email, "password": ""})
        assert res.status_code == 400
        assert db.get_user_by_id(user.user_id) is not None
    finally:
        db.hard_delete_user_account(user.user_id)


def test_wrong_password_is_rejected():
    user = _create_user()
    try:
        res = _delete(user, {"confirm_email": user.email, "password": "not-the-password"})
        assert res.status_code == 403
        assert db.get_user_by_id(user.user_id) is not None
    finally:
        db.hard_delete_user_account(user.user_id)


def test_correct_password_deletes_account():
    user = _create_user()
    res = _delete(user, {"confirm_email": user.email, "password": PASSWORD})
    assert res.status_code == 200
    assert "permanently erased" in res.json()["message"]
    assert db.get_user_by_id(user.user_id) is None


def test_mfa_code_without_mfa_enabled_is_rejected():
    user = _create_user()
    try:
        res = _delete(user, {"confirm_email": user.email, "mfa_code": "123456"})
        assert res.status_code == 400
        assert db.get_user_by_id(user.user_id) is not None
    finally:
        db.hard_delete_user_account(user.user_id)


def test_totp_reauth_for_mfa_account():
    """SSO-style account: the password is unknown, but a current TOTP code is accepted."""
    user = _create_user()
    secret = mfa_engine.generate_secret()
    db.save_mfa_credentials(
        user_id=user.user_id,
        secret=cred_vault.encrypt_field(secret),
        backup_codes=[],
        is_enabled=True,
    )
    try:
        wrong = "000000" if mfa_engine.generate_current_totp(secret) != "000000" else "111111"
        res = _delete(user, {"confirm_email": user.email, "mfa_code": wrong})
        assert res.status_code == 403
        assert db.get_user_by_id(user.user_id) is not None

        code = mfa_engine.generate_current_totp(secret)
        res = _delete(user, {"confirm_email": user.email, "mfa_code": code})
        assert res.status_code == 200
        assert db.get_user_by_id(user.user_id) is None
    finally:
        db.hard_delete_user_account(user.user_id)
