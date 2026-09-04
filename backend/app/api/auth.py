"""
JobCopilot - Multi-Tenant Authentication & Identity System
Provides JWT Access/Refresh Token rotation with token blacklist revocation,
Argon2id password hashing with legacy PBKDF2 upgrade,
FastAPI security dependencies, and tenant session resolution.
"""

import os
import time
import hmac
import hashlib
import base64
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from fastapi import APIRouter, HTTPException, Depends, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    _ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32)
    HAS_ARGON2 = True
except ImportError:
    _ph = None
    HAS_ARGON2 = False

from starlette.requests import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.settings import settings
from app.core.mailer import mailer
from app.core.models import (
    User, UserRole, UserRegisterRequest, UserLoginRequest,
    RefreshTokenRequest, TokenResponse, UserResponse,
    VerifyEmailRequest, RequestPasswordResetRequest, ResetPasswordRequest,
    Membership, OrgRole
)
from app.core.database import db

# =========================================================================
# Fail-Closed JWT Configuration (F-05)
# =========================================================================
RAW_JWT_SECRET = settings.JWT_SECRET
ENV = settings.ENV.lower()

if ENV == "production":
    if not RAW_JWT_SECRET or RAW_JWT_SECRET == "jobcopilot-super-secret-saas-jwt-signing-key-32b" or len(RAW_JWT_SECRET) < 32:
        raise RuntimeError(
            "FATAL: In production, JWT_SECRET must be set to a cryptographically secure string of at least 32 characters."
        )

JWT_SECRET: str = RAW_JWT_SECRET or "jobcopilot-super-secret-saas-jwt-signing-key-32b"
JWT_ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)


# =========================================================================
# Password Hashing Engine (Argon2id with PBKDF2 Legacy Migration)
# =========================================================================
def _hash_password_legacy(password: str) -> str:
    """Explicit PBKDF2 hash for backward-compatibility and migration testing."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000)
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    key_b64 = base64.b64encode(key).decode('utf-8')
    return f"pbkdf2_sha256$600000${salt_b64}${key_b64}"


def hash_password(password: str) -> str:
    """Hashes password using Argon2id (or PBKDF2 if Argon2 is unavailable)."""
    if HAS_ARGON2 and _ph is not None:
        return _ph.hash(password)
    return _hash_password_legacy(password)


def verify_password(password: str, hashed: str) -> Tuple[bool, bool]:
    """
    Verifies a plain password against stored hash.
    Returns tuple: (is_valid: bool, needs_rehash: bool)
    """
    if not hashed:
        return False, False
    
    # 1. Argon2id Hash
    if hashed.startswith("$argon2"):
        if HAS_ARGON2 and _ph is not None:
            try:
                _ph.verify(hashed, password)
                needs_rehash = _ph.check_needs_rehash(hashed)
                return True, needs_rehash
            except Exception:
                return False, False
        return False, False

    # 2. Legacy PBKDF2 Hash
    try:
        parts = hashed.split('$')
        if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
            iterations = int(parts[1])
            salt = base64.b64decode(parts[2].encode('utf-8'))
            expected_key = base64.b64decode(parts[3].encode('utf-8'))
            computed_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
            is_valid = hmac.compare_digest(computed_key, expected_key)
            return is_valid, True  # Needs rehash to Argon2id
    except Exception:
        pass

    return False, False


# =========================================================================
# Pure JWT Token Generation & Verification (Zero-Dependency HS256)
# =========================================================================
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')


def _b64url_decode(s: str) -> bytes:
    padding = '=' * (4 - (len(s) % 4))
    return base64.urlsafe_b64decode(s + padding)


def create_jwt_token(payload: Dict[str, Any], expires_delta: timedelta) -> str:
    """Generates a standard signed JWT HS256 token with full 32-hex unique jti."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload_copy = payload.copy()
    if "jti" not in payload_copy:
        payload_copy["jti"] = uuid.uuid4().hex  # Full 32-character hex (F-08)
    payload_copy["iat"] = now
    payload_copy["exp"] = now + int(expires_delta.total_seconds())

    header_bytes = _b64url_encode(json.dumps(header).encode('utf-8'))
    payload_bytes = _b64url_encode(json.dumps(payload_copy).encode('utf-8'))
    signing_input = f"{header_bytes}.{payload_bytes}".encode('utf-8')
    signature = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_bytes}.{payload_bytes}.{sig_b64}"


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decodes and validates signature and expiration of JWT HS256 token."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token format.")
        header_b64, payload_b64, sig_b64 = parts

        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            raise HTTPException(status_code=401, detail="Invalid token signature.")

        payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))
        if "exp" in payload and time.time() > payload["exp"]:
            raise HTTPException(status_code=401, detail="Token has expired.")

        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token decode error: {str(e)}")


# =========================================================================
# FastAPI Security Dependencies (F-01, F-02, F-08)
# =========================================================================
async def get_current_user_optional(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Resolves the authenticated user from JWT Bearer token if present.
    Returns None if no token or token is invalid.
    """
    if auth and auth.credentials:
        try:
            payload = decode_jwt_token(auth.credentials)
            if payload.get("type") == "access":
                jti = payload.get("jti")
                if jti and db.is_token_revoked(jti):
                    return None
                user_id = payload.get("sub")
                if user_id:
                    user = db.get_user_by_id(user_id)
                    if user and user.is_active:
                        return user
        except Exception:
            pass

    # Gated dev escape hatch (F-02)
    if os.getenv("JOBCOPILOT_DEV_AUTH") == "1" and os.getenv("ENV", "").lower() != "production":
        return User(
            user_id="dev_user",
            email="dev@jobcopilot.local",
            password_hash="",
            full_name="Dev User",
            role=UserRole.FREE
        )

    return None


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Strict authenticated user dependency requiring a valid, unrevoked JWT access token.
    Raises 401 Unauthorized if missing, expired, revoked, or of wrong type.
    """
    if not auth or not auth.credentials:
        # Check dev escape hatch if explicitly enabled in non-production
        if os.getenv("JOBCOPILOT_DEV_AUTH") == "1" and os.getenv("ENV", "").lower() != "production":
            return User(
                user_id="dev_user",
                email="dev@jobcopilot.local",
                password_hash="",
                full_name="Dev User",
                role=UserRole.FREE
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_jwt_token(auth.credentials)
    
    # Assert token type is strictly 'access' (F-08)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Access token required."
        )

    # Check token revocation blacklist (F-08)
    jti = payload.get("jti")
    if jti and db.is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked."
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    
    user = db.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found or disabled.")
    
    # Attach impersonation metadata if token was issued via admin impersonation
    if payload.get("impersonated_by"):
        setattr(user, "impersonated_by", payload.get("impersonated_by"))

    return user


async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Requires the authenticated user to hold the ADMIN role."""
    role_str = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if role_str != "ADMIN" and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for this resource."
        )
    return current_user


async def get_current_org_membership(
    org_id: str,
    current_user: User = Depends(get_current_user)
) -> Membership:
    """Verifies that the authenticated user is an active member of the specified organization."""
    membership = db.get_membership(org_id, current_user.user_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization."
        )
    return membership


async def require_org_admin(
    org_id: str,
    current_user: User = Depends(get_current_user)
) -> Membership:
    """Requires the authenticated user to be an OWNER or ADMIN of the specified organization."""
    membership = await get_current_org_membership(org_id, current_user)
    role_val = membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
    if role_val not in ["OWNER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization administrator privileges required."
        )
    return membership


async def require_org_owner(
    org_id: str,
    current_user: User = Depends(get_current_user)
) -> Membership:
    """Requires the authenticated user to be the OWNER of the specified organization."""
    membership = await get_current_org_membership(org_id, current_user)
    role_val = membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
    if role_val != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization owner privileges required."
        )
    return membership


# =========================================================================
# Auth API Endpoints (Public Allowlist: /register, /login, /refresh)
# =========================================================================
@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register_user(request: Request, req: UserRegisterRequest):
    """Registers a new multi-tenant candidate account with Argon2id password hashing."""
    clean_email = req.email.lower().strip()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    
    if len(req.password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters."
        )

    existing = db.get_user_by_email(clean_email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    hashed_pw = hash_password(req.password)
    new_user_id = f"usr_{uuid.uuid4().hex[:12]}"
    now_str = datetime.now().isoformat()

    new_user = User(
        user_id=new_user_id,
        email=clean_email,
        password_hash=hashed_pw,
        full_name=req.full_name or clean_email.split('@')[0],
        role=UserRole.FREE,
        is_active=True,
        email_verified=False,
        created_at=now_str,
        updated_at=now_str
    )

    if not db.create_user(new_user):
        raise HTTPException(status_code=500, detail="Failed to create user record.")

    # Send verification email token
    verify_token = create_jwt_token(
        {"sub": new_user_id, "email": clean_email, "type": "verify_email"},
        timedelta(hours=24)
    )
    mailer.send_verification_email(clean_email, verify_token)

    access_token = create_jwt_token(
        {"sub": new_user_id, "email": clean_email, "role": "FREE", "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_jwt_token(
        {"sub": new_user_id, "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=new_user_id,
        email=clean_email,
        role="FREE"
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("15/minute")
async def login_user(request: Request, req: UserLoginRequest):
    """Authenticates user credentials, enforces brute-force lockout, and issues JWT tokens."""
    clean_email = req.email.lower().strip()
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Check brute-force lockout
    if db.check_login_lockout(clean_email, client_ip):
        raise HTTPException(
            status_code=401,
            detail="Account temporarily locked due to multiple failed login attempts. Please try again in 15 minutes."
        )

    user = db.get_user_by_email(clean_email)
    if not user:
        db.record_login_attempt(clean_email, client_ip, success=False)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    is_valid, needs_rehash = verify_password(req.password, user.password_hash)
    if not is_valid:
        db.record_login_attempt(clean_email, client_ip, success=False)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated.")

    # Record successful attempt to reset failed counter
    db.record_login_attempt(clean_email, client_ip, success=True)

    # Seamless automatic upgrade from PBKDF2 to Argon2id on successful login
    if needs_rehash:
        try:
            new_hash = hash_password(req.password)
            db.update_user_password(user.user_id, new_hash)
        except Exception:
            pass

    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    access_token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": role_str, "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_jwt_token(
        {"sub": user.user_id, "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.user_id,
        email=user.email,
        role=role_str
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(request: Request, payload: RefreshTokenRequest):
    """Rotates refresh token, revokes old token, and issues a new access token."""
    token_payload = decode_jwt_token(payload.refresh_token)
    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Invalid token type for refresh.")
    
    old_jti = token_payload.get("jti")
    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token subject.")

    # Prevent refresh token replay attacks (F-08)
    if old_jti and db.is_token_revoked(old_jti):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked or already used.")

    user = db.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    # Revoke old refresh token on rotation
    if old_jti:
        exp_str = str(token_payload.get("exp", ""))
        db.revoke_token(old_jti, user.user_id, exp_str)

    # Opportunistically prune expired revoked tokens
    db.prune_revoked_tokens()

    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    new_access_token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": role_str, "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    new_refresh_token = create_jwt_token(
        {"sub": user.user_id, "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user_id=user.user_id,
        email=user.email,
        role=role_str
    )


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest):
    """Verifies user email from a signed verification token."""
    payload = decode_jwt_token(req.token)
    if payload.get("type") != "verify_email":
        raise HTTPException(status_code=400, detail="Invalid verification token type.")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token subject.")
    
    db.set_email_verified(user_id, True)
    return {"status": "success", "message": "Email address verified successfully!"}


@router.post("/request-reset")
@limiter.limit("3/minute")
async def request_password_reset(request: Request, req: RequestPasswordResetRequest):
    """Initiates a secure password reset workflow without user enumeration."""
    clean_email = req.email.lower().strip()
    user = db.get_user_by_email(clean_email)
    if user:
        reset_token = create_jwt_token(
            {"sub": user.user_id, "email": clean_email, "type": "reset_password"},
            timedelta(minutes=15)
        )
        mailer.send_password_reset_email(clean_email, reset_token)

    return {
        "status": "success",
        "message": "If an account with this email exists, a password reset link has been sent."
    }


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, req: ResetPasswordRequest):
    """Completes password reset using a single-use signed token."""
    if len(req.new_password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"New password must be at least {settings.PASSWORD_MIN_LENGTH} characters."
        )

    payload = decode_jwt_token(req.token)
    if payload.get("type") != "reset_password":
        raise HTTPException(status_code=400, detail="Invalid reset token type.")
    
    jti = payload.get("jti")
    if jti and db.is_token_revoked(jti):
        raise HTTPException(status_code=401, detail="Reset token has already been used or revoked.")

    user_id = payload.get("sub")
    user = db.get_user_by_id(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    # Update password with Argon2id hash
    new_hash = hash_password(req.new_password)
    db.update_user_password(user.user_id, new_hash)

    # Revoke single-use reset token
    if jti:
        db.revoke_token(jti, user.user_id, str(payload.get("exp", "")))

    return {"status": "success", "message": "Password reset successfully. You can now log in."}


@router.post("/logout")
async def logout_user(
    current_user: User = Depends(get_current_user),
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Revokes the current access token in the database blacklist."""
    if auth and auth.credentials:
        try:
            payload = decode_jwt_token(auth.credentials)
            jti = payload.get("jti")
            if jti:
                exp_str = str(payload.get("exp", ""))
                db.revoke_token(jti, current_user.user_id, exp_str)
        except Exception:
            pass
    return {"status": "success", "message": "Successfully logged out and token revoked."}


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Returns the authenticated candidate's identity and subscription tier."""
    role_str = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=role_str,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at
    )
