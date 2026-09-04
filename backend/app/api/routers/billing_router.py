"""
JobCopilot - SaaS Billing & Subscription Router
Handles Stripe subscription checkout sessions, customer portal redirection,
plan limits, and webhook-driven subscription provisioning.
"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import db
from app.core.models import User
from app.api.auth import get_current_user

router = APIRouter(tags=["billing"])


class CheckoutRequest(BaseModel):
    tier: str = "PRO"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CustomerPortalRequest(BaseModel):
    return_url: Optional[str] = None


@router.post("/billing/webhook")
async def stripe_webhook_handler(request: Request):
    """Receives Stripe subscription updates and adjusts tenant tier accordingly (Fail-Closed)."""
    import stripe
    from app.core.rate_limiter import rate_limiter, SubscriptionTier

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Billing webhook not configured")

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)}")

    event_type = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})
    user_id = data_object.get("metadata", {}).get("user_id")
    tier_str = data_object.get("metadata", {}).get("tier", "PRO").upper()

    if not user_id:
        return {"status": "ignored", "reason": "No user_id in metadata"}

    if event_type in ["checkout.session.completed", "customer.subscription.created", "customer.subscription.updated"]:
        tier = SubscriptionTier.ELITE if tier_str == "ELITE" else SubscriptionTier.PRO
        rate_limiter.set_user_tier(user_id, tier)
        db.update_user_role(user_id, tier.value)
        return {"status": "success", "user_id": user_id, "active_tier": tier.value}
    elif event_type in ["customer.subscription.deleted"]:
        rate_limiter.set_user_tier(user_id, SubscriptionTier.FREE)
        db.update_user_role(user_id, "FREE")
        return {"status": "success", "user_id": user_id, "active_tier": SubscriptionTier.FREE.value}

    return {"status": "ignored", "event_type": event_type}


@router.get("/billing/plan")
async def get_billing_plan(current_user: User = Depends(get_current_user)):
    """Returns the current user's subscription tier, limits, and daily apply balance."""
    from app.core.rate_limiter import rate_limiter
    return {
        "status": "success",
        "plan": rate_limiter.get_usage_summary(current_user.user_id)
    }


@router.post("/billing/checkout")
async def create_checkout_session(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user)
):
    """Generates a real Stripe Checkout Session for subscription tier upgrade."""
    requested_tier = payload.tier.upper()
    if requested_tier not in ["PRO", "ELITE"]:
        raise HTTPException(status_code=400, detail="Invalid subscription tier. Choose PRO or ELITE.")

    if settings.STRIPE_SECRET_KEY:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        price_id = settings.STRIPE_PRO_PRICE_ID if requested_tier == "PRO" else settings.STRIPE_ELITE_PRICE_ID
        success_url = payload.success_url or f"http://localhost:{settings.FRONTEND_PORT}/#billing-success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = payload.cancel_url or f"http://localhost:{settings.FRONTEND_PORT}/#billing"

        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=current_user.user_id,
                customer_email=current_user.email,
                metadata={"user_id": current_user.user_id, "tier": requested_tier}
            )
            checkout_url = session.url or f"https://checkout.stripe.com/pay/{session.id}"
            session_id = session.id
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Stripe API error: {str(e)}")
    else:
        session_id = f"cs_sim_{current_user.user_id}_{requested_tier}"
        checkout_url = f"https://checkout.stripe.com/pay/{session_id}"

    return {
        "status": "success",
        "session_id": session_id,
        "checkout_url": checkout_url,
        "tier": requested_tier,
        "amount_usd": 29 if requested_tier == "PRO" else 79
    }


@router.post("/billing/portal")
async def create_customer_portal_session(
    payload: CustomerPortalRequest = CustomerPortalRequest(),
    current_user: User = Depends(get_current_user)
):
    """Creates a Stripe Billing Customer Portal session for user subscription management."""
    return_url = payload.return_url or f"http://localhost:{settings.FRONTEND_PORT}/#billing"
    if settings.STRIPE_SECRET_KEY:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=current_user.user_id,
                return_url=return_url
            )
            portal_url = portal_session.url
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Stripe Customer Portal error: {str(e)}")
    else:
        portal_url = f"https://billing.stripe.com/p/session/sim_{current_user.user_id}"

    return {
        "status": "success",
        "portal_url": portal_url
    }
