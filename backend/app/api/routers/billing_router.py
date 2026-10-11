"""
JobCopilot - Billing
The Premium plan through Razorpay: subscribe, verify, cancel, and the webhook
that keeps the plan in step with the subscription.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.auth import enum_value, get_current_user
from app.core.config import settings
from app.core.database import db
from app.core.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])


def _apply_billing_tier(user_id: str, tier_value: str) -> str:
    """Persists a billing tier without ever touching an ADMIN's role (audit P1-5).

    Role and billing tier currently share users.role. Until they are split into
    separate columns, admins keep ADMIN and billing events only affect non-admins.
    """
    from app.core.rate_limiter import SubscriptionTier, rate_limiter
    user = db.get_user_by_id(user_id)
    if not user:
        return "UNKNOWN_USER"
    if enum_value(user.role) == "ADMIN":
        logger.info("billing: tier change %s ignored for ADMIN user %s", tier_value, user_id)
        return "ADMIN"
    tier = {"ELITE": SubscriptionTier.ELITE, "PRO": SubscriptionTier.PRO}.get(tier_value, SubscriptionTier.FREE)
    rate_limiter.set_user_tier(user_id, tier)
    db.update_user_role(user_id, tier.value)
    return tier.value


@router.get("/billing/plan")
async def get_billing_plan(current_user: User = Depends(get_current_user)):
    """The user's plan (Free or Premium), subscription state, and Premium prices."""
    from app.core import razorpay_client
    from app.core.plans import is_premium
    from app.core.rate_limiter import rate_limiter

    subscription = db.get_subscription(current_user.user_id)
    return {
        "status": "success",
        "plan": rate_limiter.get_usage_summary(current_user.user_id),
        "premium": is_premium(current_user),
        "subscription": subscription,
        "payments_enabled": razorpay_client.payments_configured(),
        "prices": {
            "IN": {"currency": "INR", "amount": settings.PREMIUM_PRICE_INR},
            "INTL": {"currency": "USD", "amount": settings.PREMIUM_PRICE_USD},
        },
    }


# --- Razorpay (Premium) -------------------------------------------------------


class SubscribeRequest(BaseModel):
    # "IN" for India (INR plan), anything else gets the USD plan.
    region: str = "INTL"


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_subscription_id: str
    razorpay_signature: str


async def _sync_subscription(user_id: str, subscription: dict) -> str:
    """Stores a Razorpay subscription's state and sets the plan to match. Returns the tier."""
    from app.core import razorpay_client

    current = db.get_subscription(user_id) or {}
    status = subscription.get("status") or "created"
    # Cancelled at period end stays "cancelling" until Razorpay reports the end.
    if current.get("status") == "cancelling" and status == "active":
        status = "cancelling"
    db.set_subscription(user_id, subscription["id"], status, razorpay_client.period_end_iso(subscription))
    premium = status in razorpay_client.PREMIUM_STATUSES
    return _apply_billing_tier(user_id, "PRO" if premium else "FREE")


@router.post("/billing/razorpay/subscribe")
async def razorpay_subscribe(payload: SubscribeRequest, current_user: User = Depends(get_current_user)):
    """Creates a Premium subscription; the page then opens Razorpay Checkout with its id."""
    from app.core import razorpay_client
    from app.core.plans import is_premium

    if not razorpay_client.payments_configured():
        raise HTTPException(status_code=503, detail="Payments aren't set up on this server yet.")
    if is_premium(current_user):
        raise HTTPException(status_code=409, detail="You're already on Premium.")

    plan = razorpay_client.plan_for_region("IN" if payload.region.upper() == "IN" else "INTL")
    try:
        subscription = await razorpay_client.create_subscription(plan["plan_id"], current_user.user_id)
    except razorpay_client.RazorpayError as exc:
        logger.warning("billing: razorpay subscription create failed for %s: %s", current_user.user_id, exc)
        raise HTTPException(status_code=502, detail="Couldn't start the payment. Please try again.")

    # Replaces any earlier subscription that was started but never paid.
    db.set_subscription(current_user.user_id, subscription["id"], subscription.get("status", "created"))
    return {
        "subscription_id": subscription["id"],
        "key_id": settings.RAZORPAY_KEY_ID,
        "currency": plan["currency"],
        "amount": plan["amount"],
        "email": current_user.email,
        "name": current_user.full_name,
    }


@router.post("/billing/razorpay/verify")
async def razorpay_verify(payload: VerifyPaymentRequest, current_user: User = Depends(get_current_user)):
    """Confirms the Checkout payment and turns Premium on (the webhook does the same)."""
    from app.core import razorpay_client

    stored = db.get_subscription(current_user.user_id)
    if not stored or stored["subscription_id"] != payload.razorpay_subscription_id:
        raise HTTPException(status_code=400, detail="That payment isn't for your subscription.")
    if not razorpay_client.verify_checkout_signature(
        payload.razorpay_payment_id, payload.razorpay_subscription_id, payload.razorpay_signature
    ):
        raise HTTPException(status_code=400, detail="Payment signature check failed.")

    try:
        subscription = await razorpay_client.fetch_subscription(payload.razorpay_subscription_id)
    except razorpay_client.RazorpayError:
        # Signature proves the payment; Razorpay reports it as authenticated until the first charge.
        subscription = {"id": payload.razorpay_subscription_id, "status": "authenticated"}
    tier = await _sync_subscription(current_user.user_id, subscription)
    return {"status": "success", "tier": tier, "premium": tier in ("PRO", "ADMIN")}


@router.post("/billing/razorpay/cancel")
async def razorpay_cancel(current_user: User = Depends(get_current_user)):
    """Stops renewal; Premium stays on until the end of the paid month."""
    from app.core import razorpay_client

    stored = db.get_subscription(current_user.user_id)
    if not stored or stored.get("status") not in razorpay_client.PREMIUM_STATUSES - {"cancelling"}:
        raise HTTPException(status_code=400, detail="There's no active subscription to cancel.")
    try:
        subscription = await razorpay_client.cancel_subscription(stored["subscription_id"], at_cycle_end=True)
    except razorpay_client.RazorpayError as exc:
        logger.warning("billing: razorpay cancel failed for %s: %s", current_user.user_id, exc)
        raise HTTPException(status_code=502, detail="Couldn't cancel right now. Please try again.")
    ends = razorpay_client.period_end_iso(subscription) or stored.get("current_end")
    db.set_subscription(current_user.user_id, stored["subscription_id"], "cancelling", ends)
    return {"status": "success", "premium_until": ends}


@router.post("/billing/razorpay/webhook")
async def razorpay_webhook(request: Request):
    """Razorpay subscription events (signed with the webhook secret)."""
    from app.core import razorpay_client

    raw = await request.body()
    if not razorpay_client.verify_webhook_signature(raw, request.headers.get("X-Razorpay-Signature")):
        raise HTTPException(status_code=400, detail="Invalid signature.")
    try:
        import json
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload.")

    if not str(event.get("event", "")).startswith("subscription."):
        return {"status": "ignored"}
    entity = (((event.get("payload") or {}).get("subscription") or {}).get("entity")) or {}
    subscription_id = entity.get("id")
    user_id = db.get_user_id_by_subscription(subscription_id) if subscription_id else None
    if not user_id:
        # Not the subscription we have on file for anyone (e.g. an abandoned checkout).
        return {"status": "ignored"}

    # Events can arrive late or twice, so apply the subscription's current state.
    try:
        latest = await razorpay_client.fetch_subscription(subscription_id)
    except razorpay_client.RazorpayError:
        latest = entity
    tier = await _sync_subscription(user_id, latest)
    return {"status": "success", "user_id": user_id, "active_tier": tier}

