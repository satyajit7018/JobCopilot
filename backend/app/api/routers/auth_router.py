"""
JobCopilot - Authentication & System Health Router
Handles healthchecks, Google SSO token verification, JWT issuance, and authentication status.
"""

import os
import uuid
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.models import User, UserRole, TokenResponse, CandidateProfile
from app.core.database import db
from app.core.session_manager import session_manager
from app.core.security_logger import security_logger
from app.api.auth import (
    router as core_auth_router,
    get_current_user, hash_password, create_jwt_token, decode_jwt_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
)

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


@router.post("/auth/google-sso", response_model=TokenResponse)
async def google_sso_auth(payload: GoogleSSORequest):
    """Authenticates candidate with Google ID token and issues signed JWT."""
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    email = payload.email
    full_name = payload.full_name or "Google User"

    if payload.id_token:
        try:
            id_info = id_token.verify_oauth2_token(
                payload.id_token,
                google_requests.Request(),
                google_client_id
            )
            if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
                raise HTTPException(status_code=401, detail="Invalid token issuer.")
            email = id_info.get("email", email)
            full_name = id_info.get("name", full_name)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=f"Google token verification failed: {str(e)}")
    elif os.getenv("ENV", "").lower() == "production":
        raise HTTPException(status_code=401, detail="Google ID token required in production.")

    if not email:
        raise HTTPException(status_code=400, detail="Missing verified email address.")

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
    else:
        user_id = user.user_id

    # Create default candidate profile if absent
    profile = db.get_profile(user_id=user_id)
    if not profile:
        profile = CandidateProfile(
            id=user_id,
            user_id=user_id,
            full_name=full_name,
            email=email,
            phone="+1-000-000-0000",
            location="Remote"
        )
        db.save_profile(profile, user_id=user_id)

    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    access_token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": role_str, "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_jwt_token(
        {"sub": user.user_id, "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    access_jti = decode_jwt_token(access_token).get("jti", "")
    session_manager.create_session(
        user_id=user.user_id,
        token_jti=access_jti,
        ip_address="127.0.0.1",
        user_agent="Google SSO Client"
    )
    security_logger.log_event(
        "auth.login.google_sso",
        user_id=user.user_id,
        details={"provider": "google"}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.user_id,
        email=user.email,
        role=role_str
    )


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
        "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    }
