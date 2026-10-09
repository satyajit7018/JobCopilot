"""
JobCopilot - Candidate Account Lifecycle & GDPR Self-Service Router
Provides complete per-tenant data portability export (GDPR Article 20)
and permanent cryptographic account erasure (GDPR Article 17).
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth import client_ip, get_current_user, limiter, verify_google_id_token, verify_password
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


# A Google ID token is valid for an hour; deletion wants a sign-in from just now.
GOOGLE_REAUTH_MAX_AGE_SECONDS = 300


def _reauthenticate_for_deletion(payload: DeleteAccountRequest, user: User) -> None:
    """Requires a fresh credential before erasure, so a stolen access token alone is not enough.

    Accepted proofs, in order:
      * ``password`` — verified against the stored hash.
      * ``mfa_code`` — a current TOTP code, only when MFA is enabled on the account.
      * ``google_id_token`` — a Google sign-in completed in the last few minutes, for
        the same verified email. Google SSO accounts have a random, never-disclosed
        password, and production has no password reset email, so this is how a
        Google-only user without MFA proves it's them.

    A "recent login" check on our own access token was rejected: /auth/refresh re-mints
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

    if payload.google_id_token:
        try:
            id_info = verify_google_id_token(payload.google_id_token)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_401_UNAUTHORIZED:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google confirmation failed.")
            raise
        if id_info["email"].lower().strip() != user.email.lower().strip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="That Google account isn't the one signed in here."
            )
        issued_at = int(id_info.get("iat") or 0)
        if time.time() - issued_at > GOOGLE_REAUTH_MAX_AGE_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Google confirmation expired. Confirm with Google again."
            )
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Confirm it's you with your password, a two-factor code, or Google to delete your account."
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
    Stripe and Razorpay subscriptions, purges file uploads, and revokes credentials.
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

    # 1b. Stop Razorpay billing now (not at period end): the account is going away.
    subscription = db.get_subscription(user_id)
    if subscription and subscription.get("status") not in ("cancelled", "completed", "expired", "halted"):
        try:
            from app.core import razorpay_client
            await razorpay_client.cancel_subscription(subscription["subscription_id"], at_cycle_end=False)
        except Exception:
            logger.error("account_router: failed to cancel razorpay subscription %s during account deletion",
                         subscription.get("subscription_id"), exc_info=True)

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
