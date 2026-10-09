"""
JobCopilot - Razorpay subscriptions client (REST API over httpx).

Two signatures are involved, keyed differently:
- Checkout returns razorpay_signature = HMAC-SHA256(f"{payment_id}|{subscription_id}", key secret).
- Webhooks carry X-Razorpay-Signature = HMAC-SHA256(raw request body, webhook secret).
"""

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.core.settings import settings

API_BASE = "https://api.razorpay.com/v1"
# Monthly cycles to authorise up front (Razorpay requires a count): ten years.
TOTAL_CYCLES = 120

# Subscription states that keep Premium on. "pending" is a failed renewal that Razorpay
# is still retrying; "cancelling" is our own marker for "cancelled at period end".
PREMIUM_STATUSES = {"authenticated", "active", "pending", "cancelling"}


class RazorpayError(Exception):
    pass


def payments_configured() -> bool:
    return bool(
        settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET
        and settings.RAZORPAY_PLAN_ID_INR and settings.RAZORPAY_PLAN_ID_USD
    )


def plan_for_region(region: str) -> Dict[str, Any]:
    """India pays the INR plan; everyone else the USD plan."""
    if region == "IN":
        return {"plan_id": settings.RAZORPAY_PLAN_ID_INR, "currency": "INR", "amount": settings.PREMIUM_PRICE_INR}
    return {"plan_id": settings.RAZORPAY_PLAN_ID_USD, "currency": "USD", "amount": settings.PREMIUM_PRICE_USD}


async def _request(method: str, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
        raise RazorpayError("Razorpay is not configured.")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.request(
                method, f"{API_BASE}{path}", json=json,
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            )
    except httpx.HTTPError as exc:
        raise RazorpayError(f"Could not reach Razorpay: {exc}") from exc
    if res.status_code >= 400:
        try:
            message = res.json().get("error", {}).get("description") or res.text
        except ValueError:
            message = res.text
        raise RazorpayError(f"Razorpay error {res.status_code}: {message}")
    return res.json()


async def create_subscription(plan_id: str, user_id: str) -> Dict[str, Any]:
    return await _request("POST", "/subscriptions", {
        "plan_id": plan_id,
        "total_count": TOTAL_CYCLES,
        "customer_notify": 1,
        "notes": {"user_id": user_id},
    })


async def fetch_subscription(subscription_id: str) -> Dict[str, Any]:
    return await _request("GET", f"/subscriptions/{subscription_id}")


async def cancel_subscription(subscription_id: str, at_cycle_end: bool = True) -> Dict[str, Any]:
    return await _request("POST", f"/subscriptions/{subscription_id}/cancel",
                          {"cancel_at_cycle_end": 1 if at_cycle_end else 0})


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_checkout_signature(payment_id: str, subscription_id: str, signature: str) -> bool:
    if not settings.RAZORPAY_KEY_SECRET or not signature:
        return False
    expected = _hmac_hex(settings.RAZORPAY_KEY_SECRET, f"{payment_id}|{subscription_id}".encode())
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: Optional[str]) -> bool:
    if not settings.RAZORPAY_WEBHOOK_SECRET or not signature:
        return False
    return hmac.compare_digest(_hmac_hex(settings.RAZORPAY_WEBHOOK_SECRET, raw_body), signature)


def period_end_iso(subscription: Dict[str, Any]) -> Optional[str]:
    """Razorpay's current_end (unix seconds) as an ISO timestamp."""
    end = subscription.get("current_end") or subscription.get("charge_at")
    if not end:
        return None
    return datetime.fromtimestamp(int(end), tz=timezone.utc).isoformat()
