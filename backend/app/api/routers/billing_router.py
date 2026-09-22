"""
JobCopilot - SaaS Billing & Subscription Router
Handles Stripe subscription checkout sessions, customer portal redirection,
plan limits, and webhook-driven subscription provisioning.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.auth import enum_value, get_current_user
from app.core.circuit_breaker import CircuitOpenError, stripe_api_breaker
from app.core.config import settings
from app.core.database import db
from app.core.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])


class CheckoutRequest(BaseModel):
    tier: str = "PRO"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CustomerPortalRequest(BaseModel):
    return_url: Optional[str] = None


def _safe_redirect(url: Optional[str], default: str) -> str:
    """Only allow redirects back to our own origins (audit P1-8: open redirect after checkout)."""
    from urllib.parse import urlparse
    if not url:
        return default
    allowed = settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else [settings.ALLOWED_ORIGINS]
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.scheme in ("http", "https") and origin in [o.rstrip("/") for o in allowed]:
        return url
    raise HTTPException(status_code=400, detail="Redirect URL must point back to this application.")


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


def _tier_from_subscription(sub: dict) -> str:
    """Derives the tier from the authoritative price id and status, never from metadata."""
    if sub.get("status") not in ("active", "trialing"):
        return "FREE"
    items = (sub.get("items") or {}).get("data") or []
    price_id = ((items[0] if items else {}).get("price") or {}).get("id")
    if price_id and price_id == settings.STRIPE_ELITE_PRICE_ID:
        return "ELITE"
    if price_id and price_id == settings.STRIPE_PRO_PRICE_ID:
        return "PRO"
    return "FREE"


async def _call_stripe_via_breaker(func, unavailable_detail: str, error_detail_prefix: str):
    """
    Invokes a Stripe API callable through the shared circuit breaker, translating
    a tripped breaker or any Stripe API failure into the equivalent HTTPException.
    """
    try:
        return await stripe_api_breaker.call(func)
    except CircuitOpenError as ce:
        raise HTTPException(status_code=503, detail=f"{unavailable_detail} (circuit open): {str(ce)}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{error_detail_prefix}: {str(e)}")


@router.post("/billing/webhook")
async def stripe_webhook_handler(request: Request):
    """Receives Stripe events and adjusts the tenant tier (fail-closed on signature).

    Audit fixes:
      P0-6  construct_event returns a stripe.Event; convert with to_dict() before .get().
      P1-6  subscription events carry no checkout-session metadata, so users are resolved
            through the stored Stripe customer id first.
      P1-5  ADMIN roles are never overwritten by billing (see _apply_billing_tier).
      P1-9  subscription tier comes from price id + status, not metadata.
    """
    import stripe

    webhook_secret = settings.STRIPE_WEBHOOK_SECRET or os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Billing webhook not configured")

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid signature")

    event = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    metadata = obj.get("metadata") or {}
    customer_id = obj.get("customer")

    if event_type == "checkout.session.completed":
        user_id = metadata.get("user_id") or obj.get("client_reference_id")
        if not user_id:
            return {"status": "ignored", "reason": "No user reference on checkout session"}
        if customer_id:
            db.set_stripe_customer_id(user_id, customer_id)
        tier = "ELITE" if str(metadata.get("tier", "")).upper() == "ELITE" else "PRO"
        return {"status": "success", "user_id": user_id, "active_tier": _apply_billing_tier(user_id, tier)}

    user_id = (db.get_user_id_by_stripe_customer(customer_id) if customer_id else None) or metadata.get("user_id")
    if not user_id:
        return {"status": "ignored", "reason": "Unknown Stripe customer"}

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        return {"status": "success", "user_id": user_id,
                "active_tier": _apply_billing_tier(user_id, _tier_from_subscription(obj))}
    if event_type == "customer.subscription.deleted":
        return {"status": "success", "user_id": user_id, "active_tier": _apply_billing_tier(user_id, "FREE")}
    if event_type == "invoice.payment_failed":
        logger.warning("billing: payment failed for user %s (grace period; Stripe dunning will follow up)", user_id)
        return {"status": "warning", "event": "payment_failed", "user_id": user_id}

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
        success_url = _safe_redirect(payload.success_url, f"http://localhost:{settings.FRONTEND_PORT}/#billing-success?session_id={{CHECKOUT_SESSION_ID}}")
        cancel_url = _safe_redirect(payload.cancel_url, f"http://localhost:{settings.FRONTEND_PORT}/#billing")
        existing_customer = db.get_stripe_customer_id(current_user.user_id)

        def _create_session():
            return stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=current_user.user_id,
                **({"customer": existing_customer} if existing_customer else {"customer_email": current_user.email}),
                metadata={"user_id": current_user.user_id, "tier": requested_tier},
                # Stripe only copies subscription_data.metadata onto the Subscription (audit P1-6).
                subscription_data={"metadata": {"user_id": current_user.user_id, "tier": requested_tier}},
            )

        session = await _call_stripe_via_breaker(_create_session, "Billing service unavailable", "Stripe API error")
        checkout_url = session.url or f"https://checkout.stripe.com/pay/{session.id}"
        session_id = session.id
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
    return_url = _safe_redirect(payload.return_url, f"http://localhost:{settings.FRONTEND_PORT}/#billing")
    if settings.STRIPE_SECRET_KEY:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        customer_id = db.get_stripe_customer_id(current_user.user_id)
        if not customer_id:
            raise HTTPException(status_code=400, detail="No billing account yet. Subscribe first.")
        def _create_portal():
            return stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )

        portal_session = await _call_stripe_via_breaker(_create_portal, "Customer portal unavailable", "Stripe Customer Portal error")
        portal_url = portal_session.url
    else:
        portal_url = f"https://billing.stripe.com/p/session/sim_{current_user.user_id}"

    return {
        "status": "success",
        "portal_url": portal_url
    }


@router.post("/billing/sync")
async def sync_subscription_tier(current_user: User = Depends(get_current_user)):
    """
    Synchronizes user tier with Stripe as the single source of truth.
    Pulls latest subscription status and updates local database and rate limiter.
    """
    user_id = current_user.user_id
    active_tier = enum_value(current_user.role)

    if settings.STRIPE_SECRET_KEY:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            customer_id = db.get_stripe_customer_id(user_id)
            if not customer_id:
                return {"status": "success", "user_id": user_id, "synchronized_tier": active_tier}

            def _get_subs():
                return stripe.Subscription.list(customer=customer_id, status="active", limit=1)

            subs = await stripe_api_breaker.call(_get_subs)
            if subs and subs.data:
                sub = subs.data[0]
                price_id = sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
                if price_id == settings.STRIPE_ELITE_PRICE_ID:
                    active_tier = "ELITE"
                elif price_id == settings.STRIPE_PRO_PRICE_ID:
                    active_tier = "PRO"
                else:
                    active_tier = "PRO"
            else:
                active_tier = "FREE"

            active_tier = _apply_billing_tier(user_id, active_tier)
        except Exception:
            logger.warning("billing_router: stripe sync failed, falling back to current database role", exc_info=True)
            pass  # Fallback to current database role if Stripe customer lookup fails or circuit is open

    return {
        "status": "success",
        "user_id": user_id,
        "synchronized_tier": active_tier
    }


@router.get("/billing/proration-preview")
async def preview_proration(
    target_tier: str,
    current_user: User = Depends(get_current_user)
):
    """Calculates estimated proration credit/charge when switching tiers."""
    target_tier = target_tier.upper().strip()
    if target_tier not in ["PRO", "ELITE", "FREE"]:
        raise HTTPException(status_code=400, detail="Invalid target tier.")

    prices = {"FREE": 0, "PRO": 29, "ELITE": 79}
    current_tier = enum_value(current_user.role)
    current_price = prices.get(current_tier, 0)
    target_price = prices.get(target_tier, 0)

    # Calculate difference based on a 30-day standard billing cycle (assuming 15 days remaining)
    estimated_days_remaining = 15
    prorated_charge = max(0.0, round((target_price - current_price) * (estimated_days_remaining / 30.0), 2))
    prorated_credit = max(0.0, round((current_price - target_price) * (estimated_days_remaining / 30.0), 2))

    return {
        "current_tier": current_tier,
        "target_tier": target_tier,
        "current_base_price": current_price,
        "target_base_price": target_price,
        "estimated_prorated_charge_usd": prorated_charge,
        "estimated_prorated_credit_usd": prorated_credit,
        "days_remaining_in_cycle": estimated_days_remaining
    }

