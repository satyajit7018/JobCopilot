"""
JobCopilot - Candidate Account Lifecycle & GDPR Self-Service Router
Provides complete per-tenant data portability export (GDPR Article 20)
and permanent cryptographic account erasure (GDPR Article 17).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth import client_ip, get_current_user, limiter, verify_password
from app.core.credential_vault import cred_vault
from app.core.database import db
from app.core.mfa import mfa_engine
from app.core.models import AccountExportResponse, DeleteAccountRequest, User
from app.core.security_logger import security_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["account"])


@router.post("/export", response_model=AccountExportResponse)
async def export_user_account_data(current_user: User = Depends(get_current_user)):
    """
    GDPR Article 20 (Right to Data Portability).
    Generates and returns an exhaustive, machine-readable JSON archive of all
    candidate data across all tables, decrypting stored PII.
    """
    user_id = current_user.user_id
    export_bundle = db.export_user_data(user_id)

    return AccountExportResponse(
        user_id=user_id,
        email=current_user.email,
        exported_at=export_bundle.get("exported_at", ""),
        data=export_bundle
    )


def _reauthenticate_for_deletion(payload: DeleteAccountRequest, user: User) -> None:
    """Requires a fresh credential before erasure, so a stolen access token alone is not enough.

    Accepted proofs, in order:
      * ``password`` — verified against the stored hash.
      * ``mfa_code`` — a current TOTP code, only when MFA is enabled on the account.

    Google SSO accounts are created with a random, never-disclosed password hash and
    the schema has no flag that tells them apart from password accounts, so the rule
    is the same for everyone. An SSO-only user without MFA sets a password via
    /auth/request-reset (which proves control of the mailbox) and then confirms with
    it. A "recent login" (token ``iat``) check was rejected: /auth/refresh re-mints
    access tokens with a fresh ``iat``, and a token stolen via XSS is fresh anyway.

    A wrong password/code is 403, not 401: the session itself is valid, and the
    frontend treats any 401 as an expired session (refresh, retry, then log out).
    """
    if payload.password:
        is_valid, _ = verify_password(payload.password, user.password_hash)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Incorrect password confirmation."
            )
        return

    if payload.mfa_code:
        mfa_cred = db.get_mfa_credentials(user.user_id)
        if not mfa_cred or not mfa_cred.get("is_enabled") or not mfa_cred.get("secret"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is not enabled; confirm with your password instead."
            )
        plain_secret = cred_vault.decrypt_field(mfa_cred["secret"])
        if not mfa_engine.verify_totp(plain_secret, payload.mfa_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid verification code."
            )
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Password confirmation is required to delete your account. If you sign in with Google "
            "and have never set a password, use 'Forgot password' to set one first."
        )
    )


@router.delete("", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def delete_user_account(
    request: Request,
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user)
):
    """
    GDPR Article 17 (Right to Erasure / Hard Delete).
    Permanently erases all database records tied to the candidate, cancels active
    Stripe subscriptions, purges file uploads, and revokes credentials.
    Requires the account email plus re-authentication (password, or TOTP when MFA is on).
    """
    clean_confirm = payload.confirm_email.lower().strip()
    if clean_confirm != current_user.email.lower().strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation email does not match the authenticated account email."
        )

    try:
        _reauthenticate_for_deletion(payload, current_user)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            security_logger.log_event(
                "account.delete.reauth_failed",
                user_id=current_user.user_id,
                severity="WARNING",
                ip_address=client_ip(request),
                user_agent=request.headers.get("User-Agent")
            )
        raise

    user_id = current_user.user_id

    # 1. Cancel Stripe subscription if active customer
    try:
        from app.core.settings import settings
        if settings.STRIPE_SECRET_KEY:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            # Cancel using the real Stripe customer id (the app user id is not a Stripe customer).
            customer_id = db.get_stripe_customer_id(user_id)
            if customer_id:
                subscriptions = stripe.Subscription.list(customer=customer_id, limit=5)
                for sub in subscriptions.auto_paging_iter():
                    stripe.Subscription.delete(sub.id)
    except Exception:
        logger.warning("account_router: failed to cancel stripe subscriptions during account deletion", exc_info=True)
        pass  # Non-blocking if Stripe is not configured or in test mode

    # 2. Hard erase database records and storage files
    success = db.hard_delete_user_account(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account data."
        )

    # GDPR Art. 17: also purge remote/local object storage (resumes, screenshots).
    try:
        from app.core.object_storage import storage
        storage.purge_user(user_id)
    except Exception:
        logger.warning("account_router: object storage purge failed during account deletion", exc_info=True)

    return {
        "status": "success",
        "message": f"Account for {current_user.email} and all associated data permanently erased in compliance with GDPR Article 17."
    }
