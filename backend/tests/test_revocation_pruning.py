"""Signing out must stay signed out: tidying the revocation list only removes tokens that have expired."""

import time
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token, decode_jwt_token
from app.core.database import db
from app.core.models import User, UserRole


def _jti():
    return f"jti_{uuid.uuid4().hex}"


def test_pruning_keeps_live_revocations_and_drops_expired_ones():
    live, expired, undated, odd = _jti(), _jti(), _jti(), _jti()
    db.revoke_token(live, "u1", str(int(time.time()) + 900))
    db.revoke_token(expired, "u1", str(int(time.time()) - 60))
    db.revoke_token(undated, "u1")
    db.revoke_token(odd, "u1", "2020-01-01T00:00:00")  # not Unix seconds: never guessed at

    db.prune_revoked_tokens()

    assert db.is_token_revoked(live)
    assert not db.is_token_revoked(expired)
    assert db.is_token_revoked(undated)
    assert db.is_token_revoked(odd)


def test_a_signed_out_token_stays_rejected_after_someone_refreshes(client: TestClient):
    """Refreshing a session tidies the revocation list. That must not revive anyone's signed-out token."""
    uid = f"usr_{uuid.uuid4().hex[:10]}"
    email = f"{uid}@jobcopilot.test"
    db.create_user(User(user_id=uid, email=email, password_hash="x", full_name="Sign Out", role=UserRole.FREE, is_active=True))
    access = create_jwt_token({"sub": uid, "email": email, "role": "FREE", "type": "access"}, timedelta(minutes=15))
    headers = {"Authorization": f"Bearer {access}"}

    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert db.is_token_revoked(decode_jwt_token(access)["jti"])

    db.prune_revoked_tokens()  # what every token refresh does

    res = client.get("/api/profile", headers=headers)
    assert res.status_code == 401 and "revoked" in res.json()["detail"].lower()
