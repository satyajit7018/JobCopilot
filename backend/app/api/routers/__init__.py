"""
JobCopilot - Domain Routers Package
Modular FastAPI APIRouters decomposing the monolithic endpoints.py into domain-driven sub-routers.
"""

from app.api.routers.auth_router import router as auth_router
from app.api.routers.profile_router import router as profile_router
from app.api.routers.vault_router import router as vault_router
from app.api.routers.discovery_router import router as discovery_router
from app.api.routers.jobs_router import router as jobs_router
from app.api.routers.bot_router import router as bot_router
from app.api.routers.email_router import router as email_router
from app.api.routers.analytics_router import router as analytics_router
from app.api.routers.interview_router import router as interview_router
from app.api.routers.negotiation_router import router as negotiation_router
from app.api.routers.billing_router import router as billing_router
from app.api.routers.backup_router import router as backup_router
from app.api.routers.admin_router import router as admin_router
from app.api.routers.org_router import router as org_router
from app.api.routers.account_router import router as account_router

all_routers = [
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
]

__all__ = [
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
    "all_routers",
]

