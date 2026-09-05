"""
JobCopilot - Router Decomposition & Domain Modularity Tests
Verifies that all 12 domain routers are cleanly modularized, properly mounted under /api,
preserve 100% backwards compatibility, enforce authentication boundaries, and respond correctly.
"""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.api.endpoints import (
    router as master_router,
    ws_manager,
    MultiTenantWebSocketGateway,
    GoogleSSORequest,
    QuestionnaireSubmitRequest,
    VaultLearnRequest,
    VaultTestMatchRequest,
    AlumniReferralRequest,
    RecruiterNudgeRequest,
    MultiRoleTailorRequest,
    LogDirectCallRequest,
    HITLResolveRequest,
    ResolveHeldApplicationRequest,
    InboundEmailPayload,
    InterviewEvalRequest,
    InterviewInvitationTriggerRequest,
    InterviewerReconRequest,
    OfferEvalRequest,
    EquityModelRequest,
    MultiOfferCompareRequest,
    AdvancedCounterOfferRequest,
    CounterOfferRequest,
    CheckoutRequest,
    CustomerPortalRequest,
    RestoreBackupPayload,
    Organization,
    Membership,
    AdminAuditLog,
    OrgRole,
)
from app.api.routers import (
    auth_router,
    profile_router,
    vault_router,
    discovery_router,
    jobs_router,
    bot_router,
    email_router,
    analytics_router,
    interview_router,
    negotiation_router,
    billing_router,
    backup_router,
    admin_router,
    org_router,
    account_router,
    compliance_router,
    all_routers,
)


def test_all_domain_routers_exported_and_valid():
    """Validates that all domain routers are distinct APIRouter instances."""
    assert len(all_routers) == 16
    for r in all_routers:
        assert isinstance(r, APIRouter)


def test_backwards_compatible_model_exports():
    """Ensures legacy imports of payload models from endpoints.py continue to function."""
    assert GoogleSSORequest is not None
    assert QuestionnaireSubmitRequest is not None
    assert VaultLearnRequest is not None
    assert VaultTestMatchRequest is not None
    assert AlumniReferralRequest is not None
    assert RecruiterNudgeRequest is not None
    assert MultiRoleTailorRequest is not None
    assert LogDirectCallRequest is not None
    assert HITLResolveRequest is not None
    assert ResolveHeldApplicationRequest is not None
    assert InboundEmailPayload is not None
    assert InterviewEvalRequest is not None
    assert InterviewInvitationTriggerRequest is not None
    assert InterviewerReconRequest is not None
    assert OfferEvalRequest is not None
    assert EquityModelRequest is not None
    assert MultiOfferCompareRequest is not None
    assert AdvancedCounterOfferRequest is not None
    assert CounterOfferRequest is not None
    assert CheckoutRequest is not None
    assert CustomerPortalRequest is not None
    assert RestoreBackupPayload is not None
    assert Organization is not None
    assert Membership is not None
    assert AdminAuditLog is not None
    assert OrgRole is not None
    assert isinstance(ws_manager, MultiTenantWebSocketGateway)


def test_route_topology_coverage(client: TestClient):
    """Verifies that all required domain route paths exist in the application routing table."""
    routes = [r.path for r in client.app.routes]
    
    expected_paths = [
        # Health & System
        "/health",
        "/api/health",
        # Auth Router
        "/api/auth/google-sso",
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/logout",
        "/api/auth/me",
        # Profile Router
        "/api/upload-resume",
        "/api/profile",
        "/api/questionnaire",
        # Vault Router
        "/api/vault",
        "/api/vault/learn",
        "/api/vault/test-match",
        # Discovery Router
        "/api/discovery/run",
        "/api/discovery/status",
        # Jobs Router
        "/api/jobs",
        "/api/jobs/{job_id}/tailor",
        "/api/resumes/tailor-multi",
        "/api/jobs/log-call",
        "/api/jobs/held",
        "/api/outreach/alumni-referral",
        "/api/outreach/recruiter-nudge",
        # Bot Router
        "/api/bot/apply/{job_id}",
        "/api/jobs/apply-async/{job_id}",
        "/api/bot/apply-async/{job_id}",
        "/api/tasks/{task_id}",
        "/api/hitl/pending",
        "/api/hitl/resolve",
        "/api/hitl/resolve-held",
        # Email Router
        "/api/email/inbound-webhook",
        "/api/email/inbound",
        "/api/email/messages",
        "/api/email/followup/{job_id}",
        # Analytics Router
        "/api/analytics/funnel",
        # Interview Studio Router
        "/api/interview/dossier",
        "/api/interview/questions",
        "/api/interview/evaluate",
        "/api/interview/notify-invitation",
        "/api/interview/reverse-questions",
        "/api/interview/interviewer-recon",
        "/api/interview/engineering-intel",
        "/api/calendar/availability",
        # Negotiation Router
        "/api/negotiation/evaluate",
        "/api/negotiation/equity",
        "/api/salary/compare-offers",
        "/api/negotiation/compare-offers",
        "/api/salary/counter-script",
        "/api/negotiation/advanced-counter",
        "/api/negotiation/counter-offer",
        # Billing Router
        "/api/billing/webhook",
        "/api/billing/plan",
        "/api/billing/checkout",
        "/api/billing/portal",
        "/api/billing/sync",
        "/api/billing/proration-preview",
        # Admin Router
        "/api/admin/users",
        "/api/admin/orgs",
        "/api/admin/metrics",
        "/api/admin/impersonate/{user_id}",
        "/api/admin/audit-logs",
        "/api/admin/users/{user_id}/role",
        # Org Router
        "/api/orgs",
        "/api/orgs/{org_id}",
        "/api/orgs/{org_id}/members",
        "/api/orgs/{org_id}/members/{user_id}",
        # Account Router
        "/api/account/export",
        "/api/account",
        # Backup Router
        "/api/backup/export",
        "/api/backup/restore",
        "/api/storage/download",
        # Compliance Router
        "/api/compliance/consent",
        "/api/compliance/consent/history",
        "/api/compliance/legal/tos",
        "/api/compliance/legal/dpa",
    ]

    for path in expected_paths:
        assert path in routes, f"Missing route in application: {path}"


def test_unauthenticated_protected_routes_return_401(client: TestClient):
    """Verifies that protected routes across domain routers return 401 when accessed without Bearer token."""
    protected_endpoints = [
        ("GET", "/api/profile"),
        ("GET", "/api/vault"),
        ("GET", "/api/jobs"),
        ("GET", "/api/analytics/funnel"),
        ("GET", "/api/interview/dossier?company=Google"),
        ("POST", "/api/interview/evaluate"),
        ("POST", "/api/negotiation/evaluate"),
        ("GET", "/api/calendar/availability"),
        ("GET", "/api/billing/plan"),
        ("POST", "/api/backup/export"),
        ("GET", "/api/jobs/held"),
    ]

    for method, path in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"Endpoint {method} {path} should be protected but returned {res.status_code}"


def test_authenticated_domain_router_responses(auth_client: TestClient):
    """Exercises domain routers with authenticated credentials to verify proper dispatching."""
    # 1. Analytics Router
    res_analytics = auth_client.get("/api/analytics/funnel")
    assert res_analytics.status_code == 200
    assert res_analytics.json()["status"] == "success"

    # 2. Interview Router: Dossier
    res_dossier = auth_client.get("/api/interview/dossier?company=Stripe&role=Staff+Engineer")
    assert res_dossier.status_code == 200
    assert res_dossier.json()["status"] == "success"
    assert "dossier" in res_dossier.json()

    # 3. Interview Router: Questions
    res_questions = auth_client.get("/api/interview/questions?role=Staff+Engineer")
    assert res_questions.status_code == 200
    assert "questions" in res_questions.json()

    # 4. Interview Router: Evaluate
    res_eval = auth_client.post("/api/interview/evaluate", json={
        "question": "How do you handle distributed race conditions?",
        "candidate_answer": "I use Redis distributed locks with Redlock algorithm and fencing tokens."
    })
    assert res_eval.status_code == 200
    assert "evaluation" in res_eval.json()

    # 5. Negotiation Router: Evaluate Offer
    res_neg = auth_client.post("/api/negotiation/evaluate", json={
        "base_salary_lpa": 35.0,
        "bonus_lpa": 5.0,
        "equity_annual_lpa": 10.0,
        "role_title": "Lead Software Engineer"
    })
    assert res_neg.status_code == 200
    assert res_neg.json()["status"] == "success"

    # 6. Negotiation Router: Equity Modeler
    res_eq = auth_client.post("/api/negotiation/equity", json={
        "options_count": 5000,
        "total_company_shares": 1000000,
        "current_valuation_usd": 50000000.0,
        "strike_price": 2.5
    })
    assert res_eq.status_code == 200
    assert res_eq.json()["status"] == "success"

    # 7. Calendar Router: Availability
    res_cal = auth_client.get("/api/calendar/availability?timezone=IST&days=3")
    assert res_cal.status_code == 200
    assert "slots" in res_cal.json()

    # 8. Billing Router: Plan Info
    res_billing = auth_client.get("/api/billing/plan")
    assert res_billing.status_code == 200
    assert res_billing.json()["status"] == "success"

    # 9. Discovery Router: Status
    res_disc = auth_client.get("/api/discovery/status")
    assert res_disc.status_code == 200
    assert "total_discovered" in res_disc.json()
