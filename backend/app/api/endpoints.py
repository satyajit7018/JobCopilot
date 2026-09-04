"""
JobCopilot - Master API Gateway & Router Aggregator
Decomposed into modular domain routers under `app.api.routers` while maintaining
100% backwards compatibility for existing imports, route topologies, and WebSocket streaming.
"""

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.api.ws_gateway import ws_manager, MultiTenantWebSocketGateway

# Import all domain routers
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
    all_routers,
)

# Re-export request models for backwards compatibility
from app.api.routers.auth_router import GoogleSSORequest
from app.api.routers.profile_router import QuestionnaireSubmitRequest
from app.api.routers.vault_router import VaultLearnRequest, VaultTestMatchRequest, VaultSemanticSearchRequest
from app.api.routers.jobs_router import (
    AlumniReferralRequest, RecruiterNudgeRequest, MultiRoleTailorRequest, LogDirectCallRequest
)
from app.api.routers.bot_router import HITLResolveRequest, ResolveHeldApplicationRequest
from app.api.routers.email_router import InboundEmailPayload
from app.api.routers.interview_router import (
    InterviewEvalRequest, InterviewInvitationTriggerRequest, InterviewerReconRequest
)
from app.api.routers.negotiation_router import (
    OfferEvalRequest, EquityModelRequest, MultiOfferCompareRequest,
    AdvancedCounterOfferRequest, CounterOfferRequest
)
from app.api.routers.billing_router import CheckoutRequest, CustomerPortalRequest
from app.api.routers.backup_router import RestoreBackupPayload
from app.core.models import (
    ApplyLedgerEntry, ApplyLedgerStatus,
    Organization, Membership, AdminAuditLog, OrgRole
)

# Backwards compatibility routers
public_router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(get_current_user)])

# Master API Router mounted under prefix "/api"
router = APIRouter(prefix="/api")

# Mount all domain routers
for sub_router in all_routers:
    router.include_router(sub_router)

__all__ = [
    "router",
    "public_router",
    "protected_router",
    "ws_manager",
    "MultiTenantWebSocketGateway",
    "GoogleSSORequest",
    "QuestionnaireSubmitRequest",
    "VaultLearnRequest",
    "VaultTestMatchRequest",
    "VaultSemanticSearchRequest",
    "AlumniReferralRequest",
    "RecruiterNudgeRequest",
    "MultiRoleTailorRequest",
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
    "CheckoutRequest",
    "CustomerPortalRequest",
    "RestoreBackupPayload",
    "ApplyLedgerEntry",
    "ApplyLedgerStatus",
    "Organization",
    "Membership",
    "AdminAuditLog",
    "OrgRole",
    "auth_router",
    "profile_router",
    "vault_router",
    "discovery_router",
    "jobs_router",
    "bot_router",
    "email_router",
    "analytics_router",
    "interview_router",
    "negotiation_router",
    "billing_router",
    "backup_router",
    "admin_router",
    "org_router",
    "account_router",
]

