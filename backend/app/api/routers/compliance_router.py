"""
JobCopilot - Compliance, Legal Governance & Trust Management Router (Epic J)
Provides versioned candidate consent tracking (GDPR/CCPA/SOC 2), audit log export,
and legal agreements (Terms of Service, Data Processing Agreement).
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query

from app.core.database import db
from app.core.models import (
    User,
    ConsentType,
    UserConsent,
    ConsentGrantRequest,
    ConsentStatusResponse
)
from app.api.auth import get_current_user

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _extract_client_ip(request: Request) -> str:
    """Extracts client IP address respecting X-Forwarded-For if behind a reverse proxy."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


@router.post("/consent", response_model=UserConsent, status_code=status.HTTP_201_CREATED)
async def record_candidate_consent(
    payload: ConsentGrantRequest,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Records an append-only, audited consent grant or revocation decision.
    Tracks client IP address and user-agent string for regulatory compliance.
    """
    client_ip = _extract_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")

    consent = UserConsent(
        user_id=current_user.user_id,
        consent_type=payload.consent_type,
        version=payload.version,
        consented=payload.consented,
        ip_address=client_ip,
        user_agent=user_agent
    )

    success = db.record_user_consent(consent)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record consent record."
        )

    return consent


@router.get("/consent", response_model=ConsentStatusResponse)
async def get_candidate_consent_status(
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the candidate's active consent states across all tracked consent categories.
    """
    consents = db.get_user_consents(current_user.user_id)
    return ConsentStatusResponse(
        user_id=current_user.user_id,
        consents=consents
    )


@router.get("/consent/history", response_model=List[UserConsent])
async def get_candidate_consent_audit_history(
    consent_type: Optional[ConsentType] = Query(None, description="Filter by consent category"),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the complete immutable chronological audit trail of consent grants and revocations.
    """
    type_str = consent_type.value if consent_type else None
    history = db.get_user_consent_history(current_user.user_id, consent_type=type_str)
    return history


@router.get("/legal/tos")
async def get_terms_of_service_metadata():
    """
    Returns public metadata and section outline for JobCopilot Terms of Service.
    """
    return {
        "version": "1.0",
        "effective_date": "2026-09-01",
        "last_updated": "2026-09-01",
        "title": "JobCopilot Terms of Service",
        "summary": "Governs access to JobCopilot AI candidate co-pilot services, autonomous application bot, and subscription billing.",
        "sections": [
            "1. Acceptance of Terms",
            "2. User Accounts & Multi-Tenancy",
            "3. Candidate AI Co-Pilot & Automation Services",
            "4. Subscription, Billing & Refund Policy",
            "5. Acceptable Use & Ethical AI Policy",
            "6. Intellectual Property & Candidate Data Ownership",
            "7. Disclaimer of Warranties & Limitation of Liability",
            "8. Governing Law & Dispute Resolution"
        ],
        "document_path": "docs/compliance/TERMS_OF_SERVICE.md"
    }


@router.get("/legal/dpa")
async def get_data_processing_agreement_metadata():
    """
    Returns public metadata and commitment summary for JobCopilot Data Processing Agreement (DPA).
    """
    return {
        "version": "1.0",
        "effective_date": "2026-09-01",
        "last_updated": "2026-09-01",
        "title": "JobCopilot Data Processing Agreement (DPA)",
        "gdpr_article_28_aligned": True,
        "ccpa_cpra_aligned": True,
        "roles": {
            "controller": "Customer / Candidate or Enterprise Organization",
            "processor": "JobCopilot Platform Services"
        },
        "subprocessors": [
            {"name": "OpenAI / Anthropic / Google Vertex", "purpose": "LLM Inference & Vector Generation", "region": "US/EU"},
            {"name": "Stripe, Inc.", "purpose": "Payment Processing & Billing", "region": "Global"},
            {"name": "AWS / GCP", "purpose": "Cloud Hosting & Encrypted Storage", "region": "US/EU"}
        ],
        "data_retention_days": 365,
        "document_path": "docs/compliance/DATA_PROCESSING_AGREEMENT.md"
    }
