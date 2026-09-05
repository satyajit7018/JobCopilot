"""
JobCopilot - Compliance, Legal Governance & Trust Management Test Suite (Phase P3 Epic J)
Verifies:
1. Consent models & serialization across all 5 consent types.
2. Dual-engine database adapter operations (record, active query, update/revoke, audit history).
3. Strict multi-tenant isolation of consent records.
4. REST API routes under canonical /api/v1/compliance and legacy /api/compliance.
5. IP and User-Agent capture in compliance audit logs.
6. Public legal metadata endpoints for Terms of Service and Data Processing Agreement.
7. Verification of all 5 formal compliance policy documents in docs/compliance/.
"""

import os
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.core.database import db
from app.core.models import (
    ConsentType,
    UserConsent,
    ConsentGrantRequest,
    ConsentStatusResponse
)


# =========================================================================
# 1. Model & Enum Tests
# =========================================================================

def test_consent_type_enum_members():
    """Verifies all mandatory GDPR/SOC 2 consent categories are present in the enum."""
    expected_categories = {
        "terms_of_service",
        "data_processing",
        "ai_data_usage",
        "telemetry_analytics",
        "marketing"
    }
    actual_categories = {ct.value for ct in ConsentType}
    assert expected_categories.issubset(actual_categories)


def test_user_consent_model_defaults_and_serialization():
    """Verifies default factories and dict/model_dump serialization for UserConsent."""
    consent = UserConsent(
        user_id="usr_comp_model_test",
        consent_type=ConsentType.TERMS_OF_SERVICE,
        version="1.0",
        consented=True,
        ip_address="192.168.1.50",
        user_agent="Mozilla/5.0 TestBrowser/1.0"
    )
    assert consent.consent_id is not None
    assert consent.created_at is not None
    data = consent.dict()
    assert data["user_id"] == "usr_comp_model_test"
    assert data["consent_type"] == "terms_of_service"
    assert data["consented"] is True
    assert data["ip_address"] == "192.168.1.50"


def test_consent_grant_request_and_status_response_models():
    """Verifies request and response envelope model instantiations."""
    req = ConsentGrantRequest(
        consent_type=ConsentType.AI_DATA_USAGE,
        version="1.2",
        consented=False
    )
    assert req.consent_type == ConsentType.AI_DATA_USAGE
    assert req.consented is False

    res = ConsentStatusResponse(
        user_id="usr_comp_envelope",
        consents={
            "ai_data_usage": UserConsent(
                user_id="usr_comp_envelope",
                consent_type=ConsentType.AI_DATA_USAGE,
                consented=False
            )
        }
    )
    res_dict = res.dict()
    assert res_dict["user_id"] == "usr_comp_envelope"
    assert "ai_data_usage" in res_dict["consents"]


# =========================================================================
# 2. Database Layer Lifecycle & State Tests
# =========================================================================

def test_database_consent_lifecycle_and_updates():
    """Tests insert, active state retrieval, state update (revoke), and audit history."""
    test_user_id = f"usr_consent_life_{uuid.uuid4().hex[:8]}"

    # 1. Initial grant for Terms of Service
    c1 = UserConsent(
        user_id=test_user_id,
        consent_type=ConsentType.TERMS_OF_SERVICE,
        version="1.0",
        consented=True,
        ip_address="10.0.0.1",
        user_agent="TestAgent-1"
    )
    ok = db.record_user_consent(c1)
    assert ok is True

    # 2. Grant for AI Data Usage
    c2 = UserConsent(
        user_id=test_user_id,
        consent_type=ConsentType.AI_DATA_USAGE,
        version="1.0",
        consented=True,
        ip_address="10.0.0.1",
        user_agent="TestAgent-1"
    )
    db.record_user_consent(c2)

    # 3. Retrieve active consents
    active = db.get_user_consents(test_user_id)
    assert len(active) == 2
    assert active["terms_of_service"].consented is True
    assert active["ai_data_usage"].consented is True

    # 4. User revokes AI Data Usage
    c3 = UserConsent(
        user_id=test_user_id,
        consent_type=ConsentType.AI_DATA_USAGE,
        version="1.1",
        consented=False,
        ip_address="10.0.0.2",
        user_agent="TestAgent-2"
    )
    db.record_user_consent(c3)

    # 5. Verify active state reflects the revocation
    active_after = db.get_user_consents(test_user_id)
    assert active_after["ai_data_usage"].consented is False
    assert active_after["ai_data_usage"].version == "1.1"
    assert active_after["ai_data_usage"].ip_address == "10.0.0.2"

    # 6. Retrieve complete history
    history = db.get_user_consent_history(test_user_id)
    assert len(history) == 3

    # 7. Retrieve filtered history for AI Data Usage
    ai_history = db.get_user_consent_history(test_user_id, consent_type=ConsentType.AI_DATA_USAGE.value)
    assert len(ai_history) == 2
    assert ai_history[0].consented is False  # newest first
    assert ai_history[1].consented is True


def test_consent_multi_tenant_isolation():
    """Verifies that consent decisions of tenant A do not leak into tenant B."""
    tenant_1 = f"usr_tenant_iso_1_{uuid.uuid4().hex[:6]}"
    tenant_2 = f"usr_tenant_iso_2_{uuid.uuid4().hex[:6]}"

    # Tenant 1 grants marketing
    db.record_user_consent(UserConsent(
        user_id=tenant_1,
        consent_type=ConsentType.MARKETING,
        consented=True
    ))

    # Tenant 2 has no records initially
    assert len(db.get_user_consents(tenant_2)) == 0
    assert len(db.get_user_consent_history(tenant_2)) == 0

    # Tenant 2 grants telemetry only
    db.record_user_consent(UserConsent(
        user_id=tenant_2,
        consent_type=ConsentType.TELEMETRY_ANALYTICS,
        consented=True
    ))

    consents_1 = db.get_user_consents(tenant_1)
    consents_2 = db.get_user_consents(tenant_2)

    assert "marketing" in consents_1
    assert "telemetry_analytics" not in consents_1
    assert "telemetry_analytics" in consents_2
    assert "marketing" not in consents_2


# =========================================================================
# 3. REST API Endpoint Tests
# =========================================================================

def test_api_v1_post_consent_grant_and_retrieval(auth_client: TestClient):
    """Tests POST /api/v1/compliance/consent and GET /api/v1/compliance/consent."""
    # Grant Terms of Service
    payload = {
        "consent_type": "terms_of_service",
        "version": "1.0",
        "consented": True
    }
    response = auth_client.post(
        "/api/v1/compliance/consent",
        json=payload,
        headers={"User-Agent": "JobCopilot-Compliance-Test-Runner/1.0", "X-Forwarded-For": "203.0.113.195"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["consent_type"] == "terms_of_service"
    assert data["consented"] is True
    assert data["version"] == "1.0"
    assert data["ip_address"] == "203.0.113.195"
    assert "JobCopilot-Compliance-Test-Runner" in data["user_agent"]

    # Verify active consent status
    get_res = auth_client.get("/api/v1/compliance/consent")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert "terms_of_service" in get_data["consents"]
    assert get_data["consents"]["terms_of_service"]["consented"] is True


def test_api_v1_consent_history_and_filtering(auth_client: TestClient):
    """Tests GET /api/v1/compliance/consent/history with and without consent_type filter."""
    # Record telemetry consent
    auth_client.post(
        "/api/v1/compliance/consent",
        json={"consent_type": "telemetry_analytics", "version": "1.0", "consented": True}
    )
    # Revoke telemetry consent
    auth_client.post(
        "/api/v1/compliance/consent",
        json={"consent_type": "telemetry_analytics", "version": "1.1", "consented": False}
    )

    # Get all history
    history_res = auth_client.get("/api/v1/compliance/consent/history")
    assert history_res.status_code == 200
    all_history = history_res.json()
    assert len(all_history) >= 2

    # Get filtered history for telemetry_analytics
    filter_res = auth_client.get("/api/v1/compliance/consent/history?consent_type=telemetry_analytics")
    assert filter_res.status_code == 200
    filtered = filter_res.json()
    assert len(filtered) >= 2
    for item in filtered:
        assert item["consent_type"] == "telemetry_analytics"


def test_api_v1_legal_metadata_endpoints(client: TestClient):
    """Verifies public legal metadata endpoints for Terms of Service and DPA."""
    # Terms of Service
    tos_res = client.get("/api/v1/compliance/legal/tos")
    assert tos_res.status_code == 200
    tos_data = tos_res.json()
    assert tos_data["version"] == "1.0"
    assert "Terms of Service" in tos_data["title"]
    assert len(tos_data["sections"]) >= 8
    assert tos_data["document_path"] == "docs/compliance/TERMS_OF_SERVICE.md"

    # Data Processing Agreement
    dpa_res = client.get("/api/v1/compliance/legal/dpa")
    assert dpa_res.status_code == 200
    dpa_data = dpa_res.json()
    assert dpa_data["version"] == "1.0"
    assert dpa_data["gdpr_article_28_aligned"] is True
    assert len(dpa_data["subprocessors"]) >= 3
    assert dpa_data["document_path"] == "docs/compliance/DATA_PROCESSING_AGREEMENT.md"


def test_legacy_api_compliance_routing(client: TestClient, auth_client: TestClient):
    """Verifies backward compatibility on legacy /api/compliance routes."""
    # Legacy ToS endpoint
    legacy_tos = client.get("/api/compliance/legal/tos")
    assert legacy_tos.status_code == 200
    assert legacy_tos.json()["version"] == "1.0"

    # Legacy DPA endpoint
    legacy_dpa = client.get("/api/compliance/legal/dpa")
    assert legacy_dpa.status_code == 200
    assert legacy_dpa.json()["gdpr_article_28_aligned"] is True

    # Legacy consent retrieval
    legacy_consent = auth_client.get("/api/compliance/consent")
    assert legacy_consent.status_code == 200


def test_unauthenticated_consent_actions_blocked(client: TestClient):
    """Verifies that unauthenticated access to consent mutations or candidate history is rejected."""
    # POST /api/v1/compliance/consent without auth
    res_post = client.post(
        "/api/v1/compliance/consent",
        json={"consent_type": "marketing", "version": "1.0", "consented": True}
    )
    assert res_post.status_code in (401, 403)

    # GET /api/v1/compliance/consent without auth
    res_get = client.get("/api/v1/compliance/consent")
    assert res_get.status_code in (401, 403)

    # GET /api/v1/compliance/consent/history without auth
    res_hist = client.get("/api/v1/compliance/consent/history")
    assert res_hist.status_code in (401, 403)


# =========================================================================
# 4. Governance & Policy Documentation Verification
# =========================================================================

def test_compliance_documents_exist_and_contain_required_controls():
    """Verifies presence and mandatory content in all 5 legal and governance policy documents."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    compliance_dir = repo_root / "docs" / "compliance"
    assert compliance_dir.is_dir(), f"Missing compliance directory: {compliance_dir}"

    expected_docs = {
        "TERMS_OF_SERVICE.md": [
            "Acceptance of Terms",
            "Human-in-the-Loop",
            "Intellectual Property & Candidate Data Ownership",
            "GDPR / CCPA Self-Service Erasure"
        ],
        "DATA_PROCESSING_AGREEMENT.md": [
            "GDPR Article 28",
            "Technical and Organizational Security Measures",
            "Assistance with Data Subject Rights",
            "seventy-two (72) hours"
        ],
        "SOC2_CONTROL_MAPPING.md": [
            "CC6.1",
            "CC6.6",
            "CC8.1",
            "P1.1",
            "migration_safety_gate.py"
        ],
        "ACCESS_REVIEW_POLICY.md": [
            "Principle of Least Privilege",
            "Periodic Access Review Cadence",
            "Administrative Impersonation Governance",
            "admin_audit_logs"
        ],
        "AUDIT_LOG_RETENTION_POLICY.md": [
            "user_consents",
            "7 Years",
            "3 Years",
            "Append-Only Operations",
            "AES-256"
        ]
    }

    for doc_name, required_phrases in expected_docs.items():
        file_path = compliance_dir / doc_name
        assert file_path.is_file(), f"Expected document missing: {file_path}"
        content = file_path.read_text(encoding="utf-8")
        for phrase in required_phrases:
            assert phrase in content, f"Document '{doc_name}' is missing required phrase '{phrase}'"
