"""
JobCopilot - Phase P1 Epic D Test Suite
End-to-end API integration for the endpoints behind the admin, organization,
billing and GDPR screens. (Checks on the legacy UI's HTML and service worker were
removed with that UI; the React app is covered by frontend/e2e.)
"""

import uuid
from fastapi.testclient import TestClient
from datetime import timedelta

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole
from app.api.auth import hash_password, create_jwt_token

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


def test_frontend_endpoints_integration():
    """Validates that all backend endpoints driving Epic D frontend controls return valid responses."""
    admin_user = _create_test_user("fe_admin@test.com", role=UserRole.ADMIN, full_name="Admin UX")
    member_user = _create_test_user("fe_member@test.com", role=UserRole.FREE, full_name="Member UX")

    admin_headers = _auth_headers_for(admin_user)
    member_headers = _auth_headers_for(member_user)

    # 1. Organization list & create for user
    org_res = client.post("/api/orgs", json={"name": "Frontend Test Org", "plan_tier": "PRO"}, headers=member_headers)
    assert org_res.status_code == 201
    org_id = org_res.json()["org_id"]

    list_orgs = client.get("/api/orgs", headers=member_headers)
    assert list_orgs.status_code == 200
    assert any(o["org_id"] == org_id for o in list_orgs.json())

    # 2. Organization members
    members_res = client.get(f"/api/orgs/{org_id}/members", headers=member_headers)
    assert members_res.status_code == 200
    assert len(members_res.json()) >= 1

    # 3. Admin Metrics & Directories
    metrics = client.get("/api/admin/metrics", headers=admin_headers)
    assert metrics.status_code == 200
    m_data = metrics.json()
    assert "total_users" in m_data
    assert "total_organizations" in m_data

    users_list = client.get("/api/admin/users", headers=admin_headers)
    assert users_list.status_code == 200
    assert "users" in users_list.json()

    orgs_list = client.get("/api/admin/orgs", headers=admin_headers)
    assert orgs_list.status_code == 200
    assert "orgs" in orgs_list.json() or "organizations" in orgs_list.json()

    logs_list = client.get("/api/admin/audit-logs", headers=admin_headers)
    assert logs_list.status_code == 200
    assert "logs" in logs_list.json() or "audit_logs" in logs_list.json()

    # 4. Impersonation Token
    imp_res = client.post(f"/api/admin/impersonate/{member_user.user_id}", headers=admin_headers)
    assert imp_res.status_code == 200
    imp_data = imp_res.json()
    assert "access_token" in imp_data or "impersonation_token" in imp_data
    assert imp_data.get("impersonated_user_id") == member_user.user_id or imp_data.get("target_user_id") == member_user.user_id

    # 5. Billing Sync & Proration Preview
    sync_res = client.post("/api/billing/sync", headers=member_headers)
    assert sync_res.status_code == 200

    proration_res = client.get("/api/billing/proration-preview?target_tier=PRO", headers=member_headers)
    assert proration_res.status_code == 200
    assert "prorated_amount_cents" in proration_res.json() or "estimated_prorated_charge_usd" in proration_res.json()

    # 6. GDPR Export
    export_res = client.post("/api/account/export", headers=member_headers)
    assert export_res.status_code == 200
    assert export_res.json()["user_id"] == member_user.user_id
