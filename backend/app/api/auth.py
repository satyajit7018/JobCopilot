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
    Membership, OrgRole,
    MFASetupResponse, MFAVerifyRequest, MFALoginChallengeRequest, MFADisableRequest,
    SessionResponse, SessionListResponse, SecurityLogListResponse
)
from app.core.database import db
from app.core.credential_vault import cred_vault
from app.core.mfa import mfa_engine
from app.core.session_manager import session_manager
from app.core.security_logger import security_logger

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


def get_user_or_ip(request: Request) -> str:
    """Per-user rate limiting key function for authenticated requests, falling back to IP."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            payload = decode_jwt_token(token)
            sub = payload.get("sub")
            if sub:
                return f"usr:{sub}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=get_user_or_ip)
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
    """Authenticates user credentials, enforces brute-force lockout, MFA gate, and issues JWT tokens."""
    clean_email = req.email.lower().strip()
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("User-Agent")

    # Check brute-force lockout
    if db.check_login_lockout(clean_email, client_ip):
        security_logger.log_event(
            "auth.lockout",
            user_id=clean_email,
            severity="WARNING",
            ip_address=client_ip,
            user_agent=user_agent
        )
        raise HTTPException(
            status_code=401,
            detail="Account temporarily locked due to multiple failed login attempts. Please try again in 15 minutes."
        )

    user = db.get_user_by_email(clean_email)
    if not user:
        db.record_login_attempt(clean_email, client_ip, success=False)
        security_logger.log_event(
            "auth.login.failed",
            user_id=clean_email,
            severity="WARNING",
            ip_address=client_ip,
            user_agent=user_agent
        )
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    is_valid, needs_rehash = verify_password(req.password, user.password_hash)
    if not is_valid:
        db.record_login_attempt(clean_email, client_ip, success=False)
        security_logger.log_event(
            "auth.login.failed",
            user_id=user.user_id,
            severity="WARNING",
            ip_address=client_ip,
            user_agent=user_agent
        )
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

    # --- Epic F: MFA Enforcement Gate ---
    mfa_cred = db.get_mfa_credentials(user.user_id)
    if mfa_cred and mfa_cred.get("is_enabled"):
        mfa_token = create_jwt_token(
            {"sub": user.user_id, "email": user.email, "role": role_str, "type": "mfa_challenge"},
            timedelta(minutes=5)
        )
        security_logger.log_event(
            "auth.mfa.challenge_issued",
            user_id=user.user_id,
            ip_address=client_ip,
            user_agent=user_agent
        )
        return TokenResponse(
            access_token="",
            refresh_token="",
            user_id=user.user_id,
            email=user.email,
            role=role_str,
            mfa_required=True,
            mfa_token=mfa_token
        )

    # Direct login when MFA is disabled
    access_token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": role_str, "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_jwt_token(
        {"sub": user.user_id, "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    # Register active session
    token_payload = decode_jwt_token(access_token)
    session_manager.create_session(
        user_id=user.user_id,
        token_jti=token_payload.get("jti", ""),
        ip_address=client_ip,
        user_agent=user_agent
    )

    security_logger.log_event(
        "auth.login.success",
        user_id=user.user_id,
        ip_address=client_ip,
        user_agent=user_agent
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
    request: Request,
    current_user: User = Depends(get_current_user),
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Revokes the current access token in the database blacklist and deactivates active session."""
    if auth and auth.credentials:
        try:
            payload = decode_jwt_token(auth.credentials)
            jti = payload.get("jti")
            if jti:
                exp_str = str(payload.get("exp", ""))
                db.revoke_token(jti, current_user.user_id, exp_str)
                # Find and revoke corresponding user session
                sessions = db.list_user_sessions(current_user.user_id, active_only=True)
                for s in sessions:
                    if s.get("token_jti") == jti:
                        db.revoke_session(s["session_id"], current_user.user_id)
        except Exception:
            pass

    security_logger.log_event(
        "auth.logout",
        user_id=current_user.user_id,
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("User-Agent")
    )
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


# =========================================================================
# MFA / TOTP API Endpoints (Epic F)
# =========================================================================
@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(request: Request, current_user: User = Depends(get_current_user)):
    """Initiates TOTP enrollment, generates secret, QR provisioning URI, and backup recovery codes."""
    secret = mfa_engine.generate_secret()
    provisioning_uri = mfa_engine.generate_provisioning_uri(secret, current_user.email)
    plain_backup_codes, hashed_storage = mfa_engine.generate_backup_codes(8)

    # Store encrypted secret and recovery codes in pending state (is_enabled=False)
    enc_secret = cred_vault.encrypt_field(secret)
    db.save_mfa_credentials(
        user_id=current_user.user_id,
        secret=enc_secret,
        backup_codes=hashed_storage,
        is_enabled=False
    )

    security_logger.log_event(
        "auth.mfa.setup",
        user_id=current_user.user_id,
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("User-Agent")
    )

    return MFASetupResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        backup_codes=plain_backup_codes,
        message="MFA setup initiated. Enter current 6-digit TOTP code to finalize activation."
    )


@router.post("/mfa/verify")
async def verify_and_enable_mfa(request: Request, req: MFAVerifyRequest, current_user: User = Depends(get_current_user)):
    """Verifies TOTP code against pending secret and finalizes MFA activation."""
    mfa_cred = db.get_mfa_credentials(current_user.user_id)
    if not mfa_cred or not mfa_cred.get("secret"):
        raise HTTPException(status_code=400, detail="MFA setup has not been initiated. Call /auth/mfa/setup first.")

    plain_secret = cred_vault.decrypt_field(mfa_cred["secret"])
    if not mfa_engine.verify_totp(plain_secret, req.code):
        raise HTTPException(status_code=400, detail="Invalid verification code. Please check your authenticator app.")

    # Enable MFA
    db.save_mfa_credentials(
        user_id=current_user.user_id,
        secret=mfa_cred["secret"],
        backup_codes=mfa_cred.get("backup_codes", []),
        is_enabled=True
    )

    security_logger.log_event(
        "auth.mfa.enabled",
        user_id=current_user.user_id,
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("User-Agent")
    )

    return {"status": "success", "message": "Two-factor authentication successfully enabled."}


@router.post("/mfa/login-challenge", response_model=TokenResponse)
async def complete_mfa_login(request: Request, req: MFALoginChallengeRequest):
    """Verifies MFA challenge token with TOTP code or backup recovery code, issuing full JWT."""
    token_payload = decode_jwt_token(req.mfa_token)
    if token_payload.get("type") != "mfa_challenge":
        raise HTTPException(status_code=400, detail="Invalid MFA challenge token type.")

    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid challenge token subject.")

    user = db.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User account not found or disabled.")

    mfa_cred = db.get_mfa_credentials(user.user_id)
    if not mfa_cred or not mfa_cred.get("is_enabled"):
        raise HTTPException(status_code=400, detail="MFA is not enabled for this account.")

    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("User-Agent")

    # 1. Try TOTP code
    plain_secret = cred_vault.decrypt_field(mfa_cred["secret"])
    is_valid_totp = mfa_engine.verify_totp(plain_secret, req.code)

    # 2. If TOTP code fails, try recovery code
    used_recovery = False
    if not is_valid_totp:
        backup_codes = mfa_cred.get("backup_codes", [])
        consumed, updated_backup_codes = mfa_engine.verify_and_consume_backup_code(backup_codes, req.code)
        if consumed:
            used_recovery = True
            db.save_mfa_credentials(
                user_id=user.user_id,
                secret=mfa_cred["secret"],
                backup_codes=updated_backup_codes,
                is_enabled=True
            )
            security_logger.log_event(
                "auth.mfa.recovery_used",
                user_id=user.user_id,
                ip_address=client_ip,
                user_agent=user_agent
            )
        else:
            security_logger.log_event(
                "auth.mfa.challenge_failed",
                user_id=user.user_id,
                severity="WARNING",
                ip_address=client_ip,
                user_agent=user_agent
            )
            raise HTTPException(status_code=401, detail="Invalid TOTP code or backup recovery code.")

    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    access_token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": role_str, "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_jwt_token(
        {"sub": user.user_id, "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    # Register active session
    access_jti = decode_jwt_token(access_token).get("jti", "")
    session_manager.create_session(
        user_id=user.user_id,
        token_jti=access_jti,
        ip_address=client_ip,
        user_agent=user_agent
    )

    security_logger.log_event(
        "auth.login.success",
        user_id=user.user_id,
        ip_address=client_ip,
        user_agent=user_agent,
        details={"mfa_verified": True, "recovery_code": used_recovery}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.user_id,
        email=user.email,
        role=role_str
    )


@router.post("/mfa/disable")
async def disable_mfa(
    request: Request,
    req: MFADisableRequest,
    current_user: User = Depends(get_current_user)
):
    """Disables MFA after verifying the user's password or current TOTP code."""
    verified = False
    if req.password:
        is_valid, _ = verify_password(req.password, current_user.password_hash)
        if is_valid:
            verified = True
    elif req.code:
        mfa_cred = db.get_mfa_credentials(current_user.user_id)
        if mfa_cred and mfa_cred.get("secret"):
            plain_secret = cred_vault.decrypt_field(mfa_cred["secret"])
            if mfa_engine.verify_totp(plain_secret, req.code):
                verified = True

    if not verified:
        raise HTTPException(status_code=400, detail="Invalid password or verification code to disable MFA.")

    db.delete_mfa_credentials(current_user.user_id)
    security_logger.log_event(
        "auth.mfa.disabled",
        user_id=current_user.user_id,
        severity="WARNING",
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("User-Agent")
    )
    return {"status": "success", "message": "Two-factor authentication has been disabled."}


# =========================================================================
# Session & Device Management API Endpoints (Epic F)
# =========================================================================
@router.get("/sessions", response_model=SessionListResponse)
async def list_active_sessions(
    current_user: User = Depends(get_current_user),
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Lists all active device sessions for the authenticated candidate."""
    current_jti = None
    if auth and auth.credentials:
        try:
            payload = decode_jwt_token(auth.credentials)
            current_jti = payload.get("jti")
        except Exception:
            pass

    sessions = session_manager.list_active_sessions(current_user.user_id, current_jti=current_jti)
    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.delete("/sessions/{session_id}")
async def revoke_user_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Revokes a specific device session and blacklists its token."""
    success = session_manager.revoke_session(session_id, current_user.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or already revoked.")

    security_logger.log_event(
        "auth.session.revoked",
        user_id=current_user.user_id,
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("User-Agent"),
        details={"revoked_session_id": session_id}
    )
    return {"status": "success", "message": "Session revoked successfully."}


@router.delete("/sessions")
async def revoke_all_other_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Revokes all active sessions for the user except the current one."""
    current_jti = None
    if auth and auth.credentials:
        try:
            payload = decode_jwt_token(auth.credentials)
            current_jti = payload.get("jti")
        except Exception:
            pass

    revoked_count = session_manager.revoke_all_sessions(current_user.user_id, except_jti=current_jti)
    security_logger.log_event(
        "auth.session.revoked_all",
        user_id=current_user.user_id,
        ip_address=request.client.host if request.client else "127.0.0.1",
        user_agent=request.headers.get("User-Agent"),
        details={"revoked_count": revoked_count}
    )
    return {"status": "success", "message": f"Successfully revoked {revoked_count} other active session(s)."}


# =========================================================================
# Security Audit Logs API Endpoints (Epic F)
# =========================================================================
@router.get("/security-logs", response_model=SecurityLogListResponse)
async def get_user_security_logs(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Returns security audit log events pertaining to the authenticated user."""
    logs_data = security_logger.get_logs(user_id=current_user.user_id, limit=limit, offset=offset)
    return SecurityLogListResponse(**logs_data)
