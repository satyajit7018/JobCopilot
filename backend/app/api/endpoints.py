"""
JobCopilot - API router
Gathers the domain routers in `app.api.routers` under one address, /api, and
re-exports the request models and WebSocket manager that other modules import from here.
"""

from fastapi import APIRouter

# Import all domain routers
from app.api.routers import (
    account_router,
    admin_router,
    all_routers,
    auth_router,
    backup_router,
    billing_router,
    bot_router,
    compliance_router,
    discovery_router,
    email_router,
    interview_router,
    jobs_router,
    negotiation_router,
    profile_router,
    vault_router,
)

# Re-export request models for backwards compatibility
from app.api.routers.auth_router import GoogleSSORequest
from app.api.routers.bot_router import HITLResolveRequest, ResolveHeldApplicationRequest
from app.api.routers.email_router import InboundEmailPayload
from app.api.routers.interview_router import (
    InterviewerReconRequest,
    InterviewEvalRequest,
    InterviewInvitationTriggerRequest,
)
from app.api.routers.jobs_router import (
    AlumniReferralRequest,
    LogDirectCallRequest,
    RecruiterNudgeRequest,
    UpdateJobStatusRequest,
)
from app.api.routers.negotiation_router import (
    AdvancedCounterOfferRequest,
    CounterOfferRequest,
    EquityModelRequest,
    MultiOfferCompareRequest,
    OfferEvalRequest,
)
from app.api.routers.profile_router import QuestionnaireSubmitRequest
from app.api.routers.vault_router import VaultLearnRequest
from app.api.ws_gateway import MultiTenantWebSocketGateway, ws_manager
from app.core.models import (
    AdminAuditLog,
    ApplyLedgerEntry,
    ApplyLedgerStatus,
    ConsentGrantRequest,
    ConsentStatusResponse,
    ConsentType,
    UserConsent,
)

# Every domain router is served once, under /api.
router = APIRouter(prefix="/api")
for sub_router in all_routers:
    router.include_router(sub_router)

__all__ = [
    "router",
    "ws_manager",
    "MultiTenantWebSocketGateway",
    "GoogleSSORequest",
    "QuestionnaireSubmitRequest",
    "VaultLearnRequest",
    "AlumniReferralRequest",
    "RecruiterNudgeRequest",
    "LogDirectCallRequest",
    "HITLResolveRequest",
    "ResolveHeldApplicationRequest",
    "InboundEmailPayload",
    "InterviewEvalRequest",
    "InterviewInvitationTriggerRequest",
    "InterviewerReconRequest",
    "OfferEvalRequest",
    "EquityModelRequest",
    "MultiOfferCompareRequest",
    "AdvancedCounterOfferRequest",
    "CounterOfferRequest",
    "ApplyLedgerEntry",
    "ApplyLedgerStatus",
    "AdminAuditLog",
    "auth_router",
    "profile_router",
    "vault_router",
    "discovery_router",
    "jobs_router",
    "bot_router",
    "email_router",
    "interview_router",
    "negotiation_router",
    "billing_router",
    "backup_router",
    "admin_router",
    "account_router",
    "compliance_router",
    "ConsentType",
    "UserConsent",
    "ConsentGrantRequest",
    "ConsentStatusResponse",
    "UpdateJobStatusRequest",
]

