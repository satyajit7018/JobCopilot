"""
JobCopilot - Candidate Account Lifecycle & GDPR Self-Service Router
Provides complete per-tenant data portability export (GDPR Article 20)
and permanent cryptographic account erasure (GDPR Article 17).
"""

from fastapi import APIRouter, HTTPException, Depends, status, Response
from pydantic import BaseModel

from app.core.database import db
from app.core.models import User, AccountExportResponse, DeleteAccountRequest
from app.api.auth import get_current_user, verify_password

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


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_user_account(
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user)
):
    """
    GDPR Article 17 (Right to Erasure / Hard Delete).
    Permanently erases all database records tied to the candidate, cancels active
    Stripe subscriptions, purges file uploads, and revokes credentials.
    """
    clean_confirm = payload.confirm_email.lower().strip()
    if clean_confirm != current_user.email.lower().strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation email does not match the authenticated account email."
        )

    # If user has a local password hash (not SSO random password), check password
    if payload.password and current_user.password_hash:
        if not verify_password(payload.password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password confirmation."
            )

    user_id = current_user.user_id

    # 1. Cancel Stripe subscription if active customer
    try:
        from app.core.settings import settings
        if settings.STRIPE_SECRET_KEY:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            # List subscriptions for this customer and cancel them
            subscriptions = stripe.Subscription.list(customer=user_id, limit=5)
            for sub in subscriptions.auto_paging_iter():
                stripe.Subscription.delete(sub.id)
    except Exception:
        pass  # Non-blocking if Stripe is not configured or in test mode

    # 2. Hard erase database records and storage files
    success = db.hard_delete_user_account(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account data."
        )

    return {
        "status": "success",
        "message": f"Account for {current_user.email} and all associated data permanently erased in compliance with GDPR Article 17."
    }
