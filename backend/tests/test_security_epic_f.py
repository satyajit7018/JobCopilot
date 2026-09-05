"""
JobCopilot - Phase P2 Epic F: Security Maturity Comprehensive Test Suite
Verifies:
1. RFC 6238 TOTP engine, secret generation, provisioning URI, recovery codes.
2. MFA enrollment, verification, login challenge enforcement gate, recovery consumption.
3. Active session tracking, device fingerprint parsing, remote revocation, token blacklisting.
4. Envelope encryption (DEK/KEK), legacy compatibility, and master key rotation.
5. Append-only security audit logging, brute-force anomaly triggers, and admin audit queries.
6. Per-user composite rate limiting resolution.
"""

import uuid
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole
from app.core.credential_vault import cred_vault, LocalKMSProvider, CredentialVault
from app.core.mfa import mfa_engine, MFAEngine
from app.core.session_manager import session_manager, parse_device_name
from app.core.security_logger import security_logger
from app.api.auth import (
    hash_password, create_jwt_token, decode_jwt_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, get_user_or_ip
)
from starlette.requests import Request


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_user():
    user_id = f"usr_test_{uuid.uuid4().hex[:8]}"
    email = f"sec_user_{uuid.uuid4().hex[:6]}@jobcopilot.test"
    pw_hash = hash_password("SecurePassword123!")
    user = User(
        user_id=user_id,
        email=email,
        password_hash=pw_hash,
        full_name="Security Test User",
        role=UserRole.FREE,
        is_active=True,
        email_verified=True
    )
    db.create_user(user)
    return user


@pytest.fixture
def test_admin():
    admin_id = f"usr_admin_{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@jobcopilot.test"
    pw_hash = hash_password("AdminSecurePassword123!")
    admin = User(
        user_id=admin_id,
        email=email,
        password_hash=pw_hash,
        full_name="Security Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        email_verified=True
    )
    db.create_user(admin)
    return admin


# =============================================================================
# 1. MFA / TOTP Core Engine Unit Tests
# =============================================================================
def test_mfa_engine_secret_and_uri():
    secret = mfa_engine.generate_secret()
    assert len(secret) >= 16
    uri = mfa_engine.generate_provisioning_uri(secret, "user@example.com")
    assert "otpauth://totp/" in uri
    assert "user%40example.com" in uri or "user@example.com" in uri
    assert secret in uri


def test_mfa_engine_totp_verification():
    secret = mfa_engine.generate_secret()
    code = mfa_engine.generate_current_totp(secret)
    assert len(code) == 6
    assert code.isdigit()
    assert mfa_engine.verify_totp(secret, code)
    assert not mfa_engine.verify_totp(secret, "999999")
    assert not mfa_engine.verify_totp(secret, "invalid")


def test_mfa_engine_backup_codes():
    plain_codes, hashed_storage = mfa_engine.generate_backup_codes(count=8)
    assert len(plain_codes) == 8
    assert len(hashed_storage) == 8

    # Consume first backup code
    first_code = plain_codes[0]
    consumed, updated = mfa_engine.verify_and_consume_backup_code(hashed_storage, first_code)
    assert consumed is True
    assert updated[0]["used"] is True
    assert updated[0]["used_at"] is not None

    # Replay attempt fails
    consumed_again, _ = mfa_engine.verify_and_consume_backup_code(updated, first_code)
    assert consumed_again is False

    # Invalid code fails
    consumed_invalid, _ = mfa_engine.verify_and_consume_backup_code(updated, "BAD-CODE-99")
    assert consumed_invalid is False


# =============================================================================
# 2. MFA API Endpoints & Login Challenge Workflow Tests
# =============================================================================
def test_mfa_setup_and_activation_workflow(client, test_user):
    token = create_jwt_token(
        {"sub": test_user.user_id, "email": test_user.email, "role": "FREE", "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Call setup endpoint
    res = client.post("/api/auth/mfa/setup", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "secret" in data
    assert "provisioning_uri" in data
    assert len(data["backup_codes"]) == 8
    secret = data["secret"]

    # Verify credentials stored in pending state
    cred = db.get_mfa_credentials(test_user.user_id)
    assert cred is not None
    assert cred["is_enabled"] is False

    # Step 2: Verification fails with wrong code
    res_fail = client.post("/api/auth/mfa/verify", json={"code": "000000"}, headers=headers)
    assert res_fail.status_code == 400

    # Step 3: Verification succeeds with valid code
    valid_code = mfa_engine.generate_current_totp(secret)
    res_verify = client.post("/api/auth/mfa/verify", json={"code": valid_code}, headers=headers)
    assert res_verify.status_code == 200
    assert res_verify.json()["status"] == "success"

    # Verify enabled in DB
    cred_active = db.get_mfa_credentials(test_user.user_id)
    assert cred_active["is_enabled"] is True


def test_mfa_login_enforcement_gate_and_challenge(client, test_user):
    # Setup and activate MFA for user
    secret = mfa_engine.generate_secret()
    plain_codes, hashed_storage = mfa_engine.generate_backup_codes(8)
    enc_secret = cred_vault.encrypt_field(secret)
    db.save_mfa_credentials(test_user.user_id, enc_secret, hashed_storage, is_enabled=True)

    # 1. Standard login returns MFA challenge instead of access token
    login_res = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "SecurePassword123!"
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["mfa_required"] is True
    assert "mfa_token" in login_data
    assert login_data["access_token"] == ""
    mfa_token = login_data["mfa_token"]

    # 2. Complete challenge with invalid code fails
    bad_res = client.post("/api/auth/mfa/login-challenge", json={
        "mfa_token": mfa_token,
        "code": "111111"
    })
    assert bad_res.status_code == 401

    # 3. Complete challenge with valid TOTP code succeeds
    valid_code = mfa_engine.generate_current_totp(secret)
    good_res = client.post("/api/auth/mfa/login-challenge", json={
        "mfa_token": mfa_token,
        "code": valid_code
    })
    assert good_res.status_code == 200
    good_data = good_res.json()
    assert good_data["access_token"] != ""
    assert good_data["user_id"] == test_user.user_id

    # 4. Complete challenge using single-use backup recovery code
    login_res2 = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "SecurePassword123!"
    })
    mfa_token2 = login_res2.json()["mfa_token"]
    backup_code = plain_codes[0]

    recovery_res = client.post("/api/auth/mfa/login-challenge", json={
        "mfa_token": mfa_token2,
        "code": backup_code
    })
    assert recovery_res.status_code == 200
    assert recovery_res.json()["access_token"] != ""

    # Replay of same backup code fails
    login_res3 = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "SecurePassword123!"
    })
    mfa_token3 = login_res3.json()["mfa_token"]
    recovery_replay = client.post("/api/auth/mfa/login-challenge", json={
        "mfa_token": mfa_token3,
        "code": backup_code
    })
    assert recovery_replay.status_code == 401


def test_mfa_disable_workflow(client, test_user):
    secret = mfa_engine.generate_secret()
    enc_secret = cred_vault.encrypt_field(secret)
    db.save_mfa_credentials(test_user.user_id, enc_secret, [], is_enabled=True)

    token = create_jwt_token(
        {"sub": test_user.user_id, "email": test_user.email, "role": "FREE", "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Disable with invalid password fails
    fail_res = client.post("/api/auth/mfa/disable", json={"password": "WrongPassword!"}, headers=headers)
    assert fail_res.status_code == 400

    # Disable with correct password succeeds
    success_res = client.post("/api/auth/mfa/disable", json={"password": "SecurePassword123!"}, headers=headers)
    assert success_res.status_code == 200

    assert db.get_mfa_credentials(test_user.user_id) is None


# =============================================================================
# 3. Session & Device Management Tests
# =============================================================================
def test_device_name_parser():
    mac_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    assert parse_device_name(mac_ua) == "macOS (Chrome)"

    iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
    assert parse_device_name(iphone_ua) == "iOS Device (Safari)"

    win_edge_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/119.0.0.0"
    assert parse_device_name(win_edge_ua) == "Windows PC (Edge)"

    assert parse_device_name("") == "Unknown Device"


def test_session_creation_listing_and_revocation(client, test_user):
    token = create_jwt_token(
        {"sub": test_user.user_id, "email": test_user.email, "role": "FREE", "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    jti = decode_jwt_token(token).get("jti")
    headers = {"Authorization": f"Bearer {token}"}

    # Create two sessions
    sess1 = session_manager.create_session(
        user_id=test_user.user_id,
        token_jti=jti,
        ip_address="192.168.1.10",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    )
    sess2 = session_manager.create_session(
        user_id=test_user.user_id,
        token_jti=f"jti_other_{uuid.uuid4().hex[:8]}",
        ip_address="192.168.1.20",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/118.0"
    )

    # List sessions via API
    res = client.get("/api/auth/sessions", headers=headers)
    assert res.status_code == 200
    sessions = res.json()["sessions"]
    assert len(sessions) >= 2

    # Check current session flag
    current_sess = [s for s in sessions if s["session_id"] == sess1["session_id"]][0]
    other_sess = [s for s in sessions if s["session_id"] == sess2["session_id"]][0]
    assert current_sess["is_current"] is True
    assert other_sess["is_current"] is False

    # Revoke other session
    del_res = client.delete(f"/api/auth/sessions/{sess2['session_id']}", headers=headers)
    assert del_res.status_code == 200

    # Bulk revoke all other sessions
    bulk_res = client.delete("/api/auth/sessions", headers=headers)
    assert bulk_res.status_code == 200


def test_session_revocation_invalidates_token(client, test_user):
    token = create_jwt_token(
        {"sub": test_user.user_id, "email": test_user.email, "role": "FREE", "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    jti = decode_jwt_token(token).get("jti")
    sess = session_manager.create_session(
        user_id=test_user.user_id,
        token_jti=jti,
        ip_address="10.0.0.1",
        user_agent="API Test Client"
    )

    headers = {"Authorization": f"Bearer {token}"}
    # Valid before revocation
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200

    # Revoke session
    session_manager.revoke_session(sess["session_id"], test_user.user_id)

    # Immediately unauthorized
    me_res_after = client.get("/api/auth/me", headers=headers)
    assert me_res_after.status_code == 401


# =============================================================================
# 4. Envelope Encryption & Key Rotation Tests
# =============================================================================
def test_envelope_encryption_roundtrip():
    data = "Candidate_Tax_ID_987654"
    enc = cred_vault.encrypt(data)
    assert enc.startswith("env:v")
    assert len(enc.split(":")) == 6

    dec = cred_vault.decrypt(enc)
    assert dec == data


def test_envelope_encryption_legacy_compatibility():
    legacy_enc = cred_vault.encrypt("Legacy_Candidate_Passport", master_password="temporary_master_pwd")
    assert legacy_enc.startswith("enc:")

    dec = cred_vault.decrypt(legacy_enc, master_password="temporary_master_pwd")
    assert dec == "Legacy_Candidate_Passport"


def test_master_key_rotation_procedure():
    # Encrypt data with current version
    initial_text = "Highly_Confidential_Executive_Compensation"
    enc_v1 = cred_vault.encrypt(initial_text)

    # Rotate master key to new version
    rotation_info = cred_vault.rotate_master_key()
    assert rotation_info["status"] == "success"
    assert rotation_info["active_version"] != rotation_info["previous_version"]

    # Historical envelope can still be decrypted
    dec_after = cred_vault.decrypt(enc_v1)
    assert dec_after == initial_text

    # New encryptions use the new active version
    enc_v2 = cred_vault.encrypt("New_Version_Secret")
    assert f"env:{rotation_info['active_version']}:" in enc_v2


# =============================================================================
# 5. Security Audit Logging & Anomaly Alerts Tests
# =============================================================================
def test_security_audit_logging_and_query(client, test_user, test_admin):
    event = security_logger.log_event(
        event_type="auth.login.success",
        user_id=test_user.user_id,
        ip_address="127.0.0.1",
        user_agent="Pytest Client",
        details={"method": "password"}
    )
    assert event["log_id"].startswith("sec_")

    token = create_jwt_token(
        {"sub": test_user.user_id, "email": test_user.email, "role": "FREE", "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    headers = {"Authorization": f"Bearer {token}"}

    # User retrieves own security logs
    res = client.get("/api/auth/security-logs", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(log["event_type"] == "auth.login.success" for log in data["logs"])

    # Admin queries system-wide security audit logs
    admin_token = create_jwt_token(
        {"sub": test_admin.user_id, "email": test_admin.email, "role": "ADMIN", "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_res = client.get("/api/admin/security-audit-logs?event_type=auth.login.success", headers=admin_headers)
    assert admin_res.status_code == 200
    assert admin_res.json()["total"] >= 1


def test_brute_force_anomaly_alert_trigger():
    attacker_ip = f"198.51.100.{uuid.uuid4().hex[:2]}"
    target_user = f"usr_victim_{uuid.uuid4().hex[:6]}"

    # Simulate 5 failed attempts
    for _ in range(5):
        security_logger.log_event(
            event_type="auth.login.failed",
            user_id=target_user,
            ip_address=attacker_ip
        )

    # Verify anomaly alert recorded in audit logs
    alerts = security_logger.get_logs(event_type="anomaly.brute_force")
    assert alerts["total"] >= 1
    latest_alert = alerts["logs"][0]
    assert latest_alert["severity"] == "CRITICAL"


# =============================================================================
# 6. Per-User Rate Limiting Key Function Test
# =============================================================================
def test_get_user_or_ip_resolution(test_user):
    token = create_jwt_token(
        {"sub": test_user.user_id, "email": test_user.email, "role": "FREE", "type": "access"},
        timedelta(minutes=15)
    )

    # 1. Authenticated request resolves to user ID
    req_auth = Request({
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode("utf-8"))],
        "client": ("192.168.1.50", 12345)
    })
    key_auth = get_user_or_ip(req_auth)
    assert key_auth == f"usr:{test_user.user_id}"

    # 2. Unauthenticated request resolves to IP
    req_unauth = Request({
        "type": "http",
        "headers": [],
        "client": ("192.168.1.50", 12345)
    })
    key_unauth = get_user_or_ip(req_unauth)
    assert key_unauth == "ip:192.168.1.50"
