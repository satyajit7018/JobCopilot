"""
JobCopilot - Authentication & System Health Router
Handles healthchecks, Google SSO token verification, JWT issuance, and authentication status.
"""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.auth import (
    client_ip,
    complete_login,
    enum_value,
    get_current_user,
    hash_password,
    limiter,
)
from app.api.auth import (
    router as core_auth_router,
)
from app.core.database import db
from app.core.models import CandidateProfile, TokenResponse, User, UserRole

router = APIRouter(tags=["auth"])
router.include_router(core_auth_router)


class GoogleSSORequest(BaseModel):
    id_token: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    google_id: Optional[str] = None
    avatar_url: Optional[str] = None
    auto_login_permissions: bool = True


@router.get("/health")
async def health_check():
    """Public healthcheck endpoint."""
    return {"status": "ok", "version": "1.0.0", "storage": "sqlite_wal"}


@router.get("/auth/public-config")
async def public_auth_config():
    """Unauthenticated config the login gate needs to render the correct sign-in UI.

    Exposes only the public OAuth client id (safe to ship to browsers) and whether
    the demo/email-only path should be offered — never any secret.
    """
    from app.core.settings import settings

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID") or ""
    return {
        "google_client_id": client_id,
        "is_production": settings.is_production,
        # The bare-email/demo login path is dev-only; production requires a real
        # Google id_token (enforced in google_sso_auth below).
        "demo_enabled": not settings.is_production,
    }


@router.post("/auth/google-sso", response_model=TokenResponse)
@limiter.limit("20/minute")
async def google_sso_auth(request: Request, payload: GoogleSSORequest):
    """Authenticates with a Google ID token, then applies the same MFA gate as password login.

    Audit P0-4 hardening:
      * the audience (client id) check can never be skipped,
      * Google must assert email_verified,
      * the email comes only from the verified token, never the request body,
      * the tokenless demo path is gated on settings (not os.environ) and is off in production,
      * deactivated accounts are refused, and MFA is enforced via complete_login().
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    from app.core.settings import settings

    full_name = payload.full_name or "Google User"

    if payload.id_token:
        google_client_id = settings.GOOGLE_OAUTH_CLIENT_ID or os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        if not google_client_id:
            raise HTTPException(status_code=503, detail="Google sign-in is not configured.")
        try:
            id_info = id_token.verify_oauth2_token(payload.id_token, google_requests.Request(), google_client_id)
        except ValueError:
            raise HTTPException(status_code=401, detail="Google token verification failed.")
        if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(status_code=401, detail="Invalid token issuer.")
        if id_info.get("email_verified") is not True:
            raise HTTPException(status_code=401, detail="Google account email is not verified.")
        email = id_info.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Google token did not include an email address.")
        full_name = id_info.get("name", full_name)
    else:
        if settings.is_production:
            raise HTTPException(status_code=401, detail="Google ID token required in production.")
        email = payload.email  # local development demo path only

    if not email:
        raise HTTPException(status_code=400, detail="Missing verified email address.")
    email = email.lower().strip()

    user = db.get_user_by_email(email)
    if not user:
        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        user = User(
            user_id=user_id,
            email=email,
            password_hash=hash_password(uuid.uuid4().hex),
            full_name=full_name,
            role=UserRole.FREE,
            is_active=True
        )
        db.create_user(user)
    elif not user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated.")
    user_id = user.user_id

    profile = db.get_profile(user_id=user_id)
    if not profile:
        profile = CandidateProfile(
            id=user_id,
            user_id=user_id,
            full_name=full_name,
            email=email,
            phone="",
            location="Remote"
        )
        db.save_profile(profile, user_id=user_id)

    return complete_login(user, client_ip(request), request.headers.get("User-Agent"), "auth.login.google_sso")


@router.get("/auth/status")
async def auth_status(current_user: User = Depends(get_current_user)):
    """Returns local vault encryption status and user authentication state."""
    return {
        "status": "success",
        "is_authenticated": True,
        "encryption": "Argon2id + AES-256-GCM",
        "keychain_storage": "OS_KEYCHAIN_SECURE",
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": enum_value(current_user.role)
    }
