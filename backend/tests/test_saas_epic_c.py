"""
JobCopilot - Phase P1 Epic C Test Suite
Tests SaaS Multi-Tenant Organization & Team Workspaces, RBAC Roles,
Admin Panel & Impersonation Audit, Billing Lifecycle Sync, and GDPR Self-Service.
"""

import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole, CandidateProfile, JobListing, ApplicationStatus, Organization, Membership, OrgRole
from app.api.auth import hash_password, create_jwt_token
from datetime import timedelta

client = TestClient(app)


def _create_test_user(email: str, role: UserRole = UserRole.FREE, full_name: str = "Test User") -> User:
    """Helper to create and persist a test user."""
    clean_email = email.lower().strip()
    existing = db.get_user_by_email(clean_email)
    if existing:
        db.hard_delete_user_account(existing.user_id)

    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    user = User(
        user_id=user_id,
        email=clean_email,
        password_hash=hash_password("Password123!"),
        full_name=full_name,
        role=role,
        is_active=True,
        email_verified=True
    )
    db.create_user(user)
    return user


def _auth_headers_for(user: User) -> dict:
    """Generates valid Bearer authorization header for a test user."""
    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": role_str, "type": "access"},
        expires_delta=timedelta(minutes=60)
    )
    return {"Authorization": f"Bearer {token}"}


def test_admin_panel_and_impersonation():
    """Verifies that admin endpoints reject non-admins, provide system metrics, and audit impersonation."""
    admin_user = _create_test_user("super_admin@jobcopilot.com", role=UserRole.ADMIN, full_name="Super Admin")
    regular_user = _create_test_user("regular_user@test.com", role=UserRole.FREE, full_name="Reggie Regular")

    admin_headers = _auth_headers_for(admin_user)
    regular_headers = _auth_headers_for(regular_user)

    # 1. Non-admin is rejected
    rej = client.get("/api/admin/users", headers=regular_headers)
    assert rej.status_code == 403

    # 2. Admin can list users
    user_list = client.get("/api/admin/users", headers=admin_headers)
    assert user_list.status_code == 200
    assert user_list.json()["total"] >= 2

    # 3. Admin can get system metrics
    metrics = client.get("/api/admin/metrics", headers=admin_headers)
    assert metrics.status_code == 200
    m_data = metrics.json()
    assert "total_users" in m_data
    assert "active_subscriptions" in m_data

    # 4. Admin updates user role
    role_patch = client.patch(
        f"/api/admin/users/{regular_user.user_id}/role?role=PRO",
        headers=admin_headers
    )
    assert role_patch.status_code == 200
    assert role_patch.json()["new_role"] == "PRO"

    # 5. Admin impersonates regular user
    imp_res = client.post(f"/api/admin/impersonate/{regular_user.user_id}", headers=admin_headers)
    assert imp_res.status_code == 200
    imp_token = imp_res.json()["access_token"]
    assert imp_res.json()["impersonated_user_id"] == regular_user.user_id

    # 6. Verify impersonation token grants access as regular user
    imp_headers = {"Authorization": f"Bearer {imp_token}"}
    status_res = client.get("/api/auth/me", headers=imp_headers)
    assert status_res.status_code == 200
    assert status_res.json()["user_id"] == regular_user.user_id

    # 7. Verify admin audit logs recorded both the role update and impersonation
    logs_res = client.get("/api/admin/audit-logs", headers=admin_headers)
    assert logs_res.status_code == 200
    actions = [l["action"] for l in logs_res.json()["logs"]]
    assert "USER_IMPERSONATION" in actions
    assert "UPDATE_USER_ROLE" in actions


def test_gdpr_data_export_and_hard_deletion():
    """Verifies full per-tenant data portability export and permanent hard erasure."""
    user = _create_test_user("gdpr_candidate@test.com", full_name="Grace Hopper")
    headers = _auth_headers_for(user)

    # Seed some user-specific data
    # 1. Profile
    profile = CandidateProfile(
        id=user.user_id,
        user_id=user.user_id,
        full_name="Grace Hopper",
        email=user.email,
        phone="+1-202-555-0143",
        location="Arlington, VA"
    )
    db.save_profile(profile, user_id=user.user_id)

    # 2. Job listing
    job = JobListing(
        job_id=f"job_gdpr_{uuid.uuid4().hex[:8]}",
        user_id=user.user_id,
        fingerprint=f"fp_gdpr_{uuid.uuid4().hex[:8]}",
        platform="Greenhouse",
        company="US Navy Research",
        title="Senior Compiler Engineer",
        location="Remote",
        url="https://boards.greenhouse.io/navy/jobs/1",
        status=ApplicationStatus.DISCOVERED
    )
    db.save_job(job, user_id=user.user_id)

    # 3. Test GDPR Export (Article 20)
    export_res = client.post("/api/account/export", headers=headers)
    assert export_res.status_code == 200
    exp_data = export_res.json()
    assert exp_data["user_id"] == user.user_id
    assert exp_data["email"] == user.email
    data_bundle = exp_data["data"]
    assert data_bundle["profile"]["full_name"] == "Grace Hopper"
    assert len(data_bundle["jobs"]) >= 1

    # 4. Test GDPR Hard Delete with wrong email rejection
    wrong_del = client.request(
        "DELETE",
        "/api/account",
        json={"confirm_email": "wrong_email@test.com"},
        headers=headers
    )
    assert wrong_del.status_code == 400

    # 5. Test GDPR Hard Delete with correct email
    del_res = client.request(
        "DELETE",
        "/api/account",
        json={"confirm_email": user.email, "password": "Password123!"},
        headers=headers
    )
    assert del_res.status_code == 200
    assert "permanently erased" in del_res.json()["message"]

    # 6. Verify user is eradicated from DB
    assert db.get_user_by_id(user.user_id) is None
    assert db.get_profile(user.user_id) is None
    assert len(db.get_jobs(user.user_id)) == 0

    # 7. Subsequent authenticated request with old token is rejected
    after_res = client.get("/api/auth/me", headers=headers)
    assert after_res.status_code == 401
