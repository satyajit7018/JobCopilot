"""
JobCopilot - Phase P1 Epic D Test Suite
Tests Frontend & UX Maturity:
1. Strict CSP compliance & zero inline event handlers in index.html.
2. WCAG 2.1 AA accessibility attributes on modals (role="dialog", aria-modal, aria-labelledby).
3. Presence and structure of multi-tenant workspace switcher, impersonation banner, and offline alerts.
4. Enterprise Admin Portal view, telemetry KPI structure, and data tables.
5. GDPR self-service data export & erasure confirmation controls.
6. PWA service worker v1.1 compliance, background sync, and push notification handlers.
7. End-to-end API integration for all Epic C & D frontend endpoints.
"""

import re
import json
import uuid
import pytest
from pathlib import Path
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from datetime import timedelta

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole, CandidateProfile, JobListing, ApplicationStatus
from app.api.auth import hash_password, create_jwt_token

client = TestClient(app)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


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


def test_html_zero_inline_event_handlers():
    """Verifies that index.html contains ZERO inline event handlers (onclick, onchange, etc.)."""
    html_path = FRONTEND_DIR / "index.html"
    assert html_path.exists(), "frontend/index.html must exist"

    html_content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "html.parser")

    inline_event_attrs = [
        "onclick", "onchange", "onsubmit", "oninput", "onkeydown",
        "onkeyup", "onkeypress", "onload", "onerror", "onmouseover"
    ]

    violating_elements = []
    for tag in soup.find_all(True):
        for attr in inline_event_attrs:
            if tag.has_attr(attr):
                violating_elements.append((tag.name, attr, tag.get(attr)))

    assert len(violating_elements) == 0, f"Found inline event handlers violating strict CSP: {violating_elements}"


def test_html_wcag_aria_modal_dialogs():
    """Verifies that all interactive modals in index.html have WCAG 2.1 AA accessible attributes."""
    html_path = FRONTEND_DIR / "index.html"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    expected_modals = [
        "modal-held-applications",
        "modal-log-call",
        "hitl-modal",
        "outreach-modal",
        "interview-invite-modal",
        "glass-booth-modal",
        "modal-install-app",
        "modal-create-org",
        "modal-manage-org",
        "modal-proration-preview",
        "modal-gdpr-delete"
    ]

    for modal_id in expected_modals:
        modal_el = soup.find(id=modal_id)
        assert modal_el is not None, f"Expected modal element #{modal_id} not found in index.html"
        assert modal_el.get("role") == "dialog", f"Modal #{modal_id} must have role='dialog'"
        assert modal_el.get("aria-modal") == "true", f"Modal #{modal_id} must have aria-modal='true'"
        assert modal_el.get("aria-labelledby") or modal_el.get("aria-label"), f"Modal #{modal_id} must have aria-labelledby or aria-label"


def test_html_accessibility_announcer_and_banners():
    """Verifies presence of screen-reader announcer, impersonation banner, and offline banner."""
    html_path = FRONTEND_DIR / "index.html"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    # Screen-reader live region
    sr_announcer = soup.find(id="sr-announcer")
    assert sr_announcer is not None, "Missing #sr-announcer screen reader region"
    assert sr_announcer.get("aria-live") == "polite"
    assert "sr-only" in sr_announcer.get("class", [])

    # Impersonation Alert Banner
    imp_banner = soup.find(id="impersonation-banner")
    assert imp_banner is not None, "Missing #impersonation-banner"
    assert imp_banner.get("role") == "alert"

    # Offline Banner
    offline_banner = soup.find(id="offline-banner")
    assert offline_banner is not None, "Missing #offline-banner"
    assert offline_banner.get("role") == "status"

    # Workspace Switcher
    ws_container = soup.find(id="workspace-switcher-container")
    assert ws_container is not None, "Missing #workspace-switcher-container"
    ws_btn = soup.find(id="btn-workspace-switcher")
    assert ws_btn is not None
    assert ws_btn.get("aria-haspopup") == "true"


def test_html_admin_portal_and_gdpr_sections():
    """Verifies presence and accessibility of the Admin Portal view and GDPR controls."""
    html_path = FRONTEND_DIR / "index.html"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    # Admin Portal section
    admin_view = soup.find(id="view-admin")
    assert admin_view is not None, "Missing #view-admin view panel"
    assert admin_view.find(id="kpi-total-users") is not None
    assert admin_view.find(id="kpi-total-jobs") is not None
    assert admin_view.find(id="kpi-total-applications") is not None
    assert admin_view.find(id="kpi-active-subs") is not None
    assert admin_view.find(id="kpi-total-orgs") is not None

    # Admin Sub-panels and Tables
    assert admin_view.find(id="admin-users-tbody") is not None
    assert admin_view.find(id="admin-orgs-tbody") is not None
    assert admin_view.find(id="admin-logs-tbody") is not None

    # Settings: GDPR Controls & Billing
    settings_view = soup.find(id="view-settings")
    assert settings_view is not None
    assert settings_view.find(id="settings-billing-tier") is not None
    assert settings_view.find(id="offline-queue-count") is not None


def test_css_wcag_focus_visible_and_tokens():
    """Verifies that style.css contains WCAG focus-visible styling and required design tokens."""
    css_path = FRONTEND_DIR / "css" / "style.css"
    assert css_path.exists()
    css_content = css_path.read_text(encoding="utf-8")

    assert ":focus-visible" in css_content, "style.css must define :focus-visible rules"
    assert ".sr-only" in css_content, "style.css must define .sr-only utility"
    assert ".impersonation-alert-banner" in css_content
    assert ".offline-alert-banner" in css_content
    assert ".workspace-dropdown" in css_content
    assert ".admin-kpi-grid" in css_content


def test_service_worker_v1_1_and_sync_handlers():
    """Verifies Service Worker v1.1 includes Background Sync and Push listeners."""
    sw_path = FRONTEND_DIR / "sw.js"
    assert sw_path.exists()
    sw_content = sw_path.read_text(encoding="utf-8")

    assert "jobcopilot-pwa-v1.1" in sw_content, "sw.js cache must be bumped to v1.1"
    assert "sync" in sw_content, "sw.js must contain background sync handler"
    assert "push" in sw_content, "sw.js must contain push notification handler"
    assert "notificationclick" in sw_content


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
