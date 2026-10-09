"""
Free and Premium plans with Razorpay subscriptions.

Premium: automatic applying, AI writing, inbox tracking, interview prep.
Razorpay is faked here; signatures are computed with the test secrets.
"""

import hashlib
import hmac
import json
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token
from app.core import razorpay_client
from app.core.database import db
from app.core.models import User, UserRole
from app.core.settings import settings
from app.main import app

client = TestClient(app)


def _user(role=UserRole.FREE) -> User:
    user = User(
        user_id=f"usr_{uuid.uuid4().hex[:12]}",
        email=f"plans_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="test_hash",
        full_name="Plan Tester",
        role=role,
        is_active=True,
    )
    db.create_user(user)
    return user


def _headers(user: User) -> dict:
    token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": user.role.value, "type": "access"},
        timedelta(minutes=60),
    )
    return {"Authorization": f"Bearer {token}"}


def _role(user: User) -> str:
    return db.get_user_by_id(user.user_id).role.value


@pytest.fixture
def razorpay(monkeypatch):
    """Configures Razorpay with test secrets and fakes its API."""
    from app.core.rate_limiter import rate_limiter

    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "key_secret")
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "hook_secret")
    monkeypatch.setattr(settings, "RAZORPAY_PLAN_ID_INR", "plan_inr")
    monkeypatch.setattr(settings, "RAZORPAY_PLAN_ID_USD", "plan_usd")
    state = {"created": [], "remote": {}}

    async def create(plan_id, user_id):
        sub = {"id": f"sub_{uuid.uuid4().hex[:10]}", "status": "created", "plan_id": plan_id}
        state["created"].append(sub)
        state["remote"][sub["id"]] = dict(sub)
        return sub

    async def fetch(sub_id):
        if sub_id not in state["remote"]:
            raise razorpay_client.RazorpayError("not found")
        return state["remote"][sub_id]

    async def cancel(sub_id, at_cycle_end=True):
        return {**state["remote"][sub_id], "current_end": 1893456000}

    monkeypatch.setattr(razorpay_client, "create_subscription", create)
    monkeypatch.setattr(razorpay_client, "fetch_subscription", fetch)
    monkeypatch.setattr(razorpay_client, "cancel_subscription", cancel)
    yield state
    rate_limiter.invalidate_cache()


def _checkout_signature(payment_id: str, sub_id: str) -> str:
    return hmac.new(b"key_secret", f"{payment_id}|{sub_id}".encode(), hashlib.sha256).hexdigest()


def _webhook(event: str, sub: dict):
    body = json.dumps({"event": event, "payload": {"subscription": {"entity": sub}}}).encode()
    sig = hmac.new(b"hook_secret", body, hashlib.sha256).hexdigest()
    return client.post("/api/billing/razorpay/webhook", content=body,
                       headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})


# --- Feature gates ---------------------------------------------------------------

PREMIUM_CALLS = [
    ("POST", "/api/jobs/job_missing/tailor"),
    ("POST", "/api/jobs/apply-async/job_missing"),
    ("GET", "/api/interview/questions?role=Engineer"),
    ("GET", "/api/email/messages"),
    ("POST", "/api/email/followup/job_missing"),
]


@pytest.mark.parametrize("method,path", PREMIUM_CALLS)
def test_free_users_get_402_on_premium_features(method, path):
    free = _user()
    try:
        res = client.request(method, path, headers=_headers(free), json={})
        assert res.status_code == 402
        assert "Premium" in res.json()["detail"]
    finally:
        db.hard_delete_user_account(free.user_id)


@pytest.mark.parametrize("role", [UserRole.PRO, UserRole.ADMIN])
@pytest.mark.parametrize("method,path", PREMIUM_CALLS)
def test_premium_and_admin_pass_the_gate(method, path, role):
    user = _user(role)
    try:
        res = client.request(method, path, headers=_headers(user), json={})
        assert res.status_code != 402
    finally:
        db.hard_delete_user_account(user.user_id)


def test_free_features_stay_open():
    free = _user()
    try:
        assert client.get("/api/jobs", headers=_headers(free)).status_code == 200
        plan = client.get("/api/billing/plan", headers=_headers(free)).json()
        assert plan["premium"] is False
        assert plan["prices"] == {"IN": {"currency": "INR", "amount": 199}, "INTL": {"currency": "USD", "amount": 5}}
    finally:
        db.hard_delete_user_account(free.user_id)


def test_inbound_email_for_free_user_is_acknowledged_but_not_processed(monkeypatch):
    from app.email.inbound_provider import InboundEmailProvider

    free = _user()
    try:
        monkeypatch.setattr(InboundEmailProvider, "verify_webhook_signature", staticmethod(lambda body, sig: True))
        monkeypatch.setattr(InboundEmailProvider, "parse_webhook_payload", staticmethod(lambda p: {
            "user_id": free.user_id, "sender": "hr@acme.com", "recipient": free.email,
            "subject": "Interview", "body_html": "", "body_text": "Let's talk",
        }))
        res = client.post("/api/email/inbound-webhook", json={})
        assert res.status_code == 200
        assert res.json()["status"] == "ignored"
        assert db.get_emails(user_id=free.user_id) == []
    finally:
        db.hard_delete_user_account(free.user_id)


# --- Razorpay subscriptions ------------------------------------------------------------


def test_subscribe_needs_payments_configured(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", None)
    free = _user()
    try:
        res = client.post("/api/billing/razorpay/subscribe", headers=_headers(free), json={"region": "IN"})
        assert res.status_code == 503
    finally:
        db.hard_delete_user_account(free.user_id)


def test_region_picks_the_plan(razorpay):
    a, b = _user(), _user()
    try:
        india = client.post("/api/billing/razorpay/subscribe", headers=_headers(a), json={"region": "IN"}).json()
        abroad = client.post("/api/billing/razorpay/subscribe", headers=_headers(b), json={"region": "US"}).json()
        assert (india["currency"], india["amount"]) == ("INR", 199)
        assert (abroad["currency"], abroad["amount"]) == ("USD", 5)
        assert [s["plan_id"] for s in razorpay["created"]] == ["plan_inr", "plan_usd"]
        assert india["key_id"] == "rzp_test_key"
    finally:
        db.hard_delete_user_account(a.user_id)
        db.hard_delete_user_account(b.user_id)


def test_full_lifecycle_subscribe_pay_cancel_expire(razorpay):
    user = _user()
    try:
        sub_id = client.post("/api/billing/razorpay/subscribe", headers=_headers(user), json={"region": "IN"}).json()["subscription_id"]

        # A forged signature doesn't unlock Premium.
        bad = client.post("/api/billing/razorpay/verify", headers=_headers(user), json={
            "razorpay_payment_id": "pay_1", "razorpay_subscription_id": sub_id, "razorpay_signature": "forged"})
        assert bad.status_code == 400
        assert _role(user) == "FREE"

        razorpay["remote"][sub_id]["status"] = "active"
        razorpay["remote"][sub_id]["current_end"] = 1893456000
        ok = client.post("/api/billing/razorpay/verify", headers=_headers(user), json={
            "razorpay_payment_id": "pay_1", "razorpay_subscription_id": sub_id,
            "razorpay_signature": _checkout_signature("pay_1", sub_id)})
        assert ok.status_code == 200 and ok.json()["premium"] is True
        assert _role(user) == "PRO"
        assert client.post("/api/jobs/job_missing/tailor", headers=_headers(user)).status_code != 402

        # Cancel: stays Premium until the period ends, even if a renewal-time event arrives.
        cancelled = client.post("/api/billing/razorpay/cancel", headers=_headers(user))
        assert cancelled.status_code == 200 and cancelled.json()["premium_until"]
        assert db.get_subscription(user.user_id)["status"] == "cancelling"
        assert _webhook("subscription.charged", razorpay["remote"][sub_id]).status_code == 200
        assert db.get_subscription(user.user_id)["status"] == "cancelling"
        assert _role(user) == "PRO"

        razorpay["remote"][sub_id]["status"] = "cancelled"
        assert _webhook("subscription.cancelled", razorpay["remote"][sub_id]).json()["active_tier"] == "FREE"
        assert _role(user) == "FREE"
    finally:
        db.hard_delete_user_account(user.user_id)


def test_verify_rejects_someone_elses_subscription(razorpay):
    owner, other = _user(), _user()
    try:
        sub_id = client.post("/api/billing/razorpay/subscribe", headers=_headers(owner), json={}).json()["subscription_id"]
        res = client.post("/api/billing/razorpay/verify", headers=_headers(other), json={
            "razorpay_payment_id": "pay_1", "razorpay_subscription_id": sub_id,
            "razorpay_signature": _checkout_signature("pay_1", sub_id)})
        assert res.status_code == 400
        assert _role(other) == "FREE"
    finally:
        db.hard_delete_user_account(owner.user_id)
        db.hard_delete_user_account(other.user_id)


def test_webhook_signature_and_unknown_subscriptions(razorpay):
    body = json.dumps({"event": "subscription.activated", "payload": {"subscription": {"entity": {"id": "sub_x"}}}}).encode()
    res = client.post("/api/billing/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": "nope"})
    assert res.status_code == 400
    assert _webhook("subscription.activated", {"id": "sub_unknown", "status": "active"}).json()["status"] == "ignored"


def test_payment_failure_keeps_premium_until_halted(razorpay):
    user = _user()
    try:
        sub_id = client.post("/api/billing/razorpay/subscribe", headers=_headers(user), json={}).json()["subscription_id"]
        for status, role in (("active", "PRO"), ("pending", "PRO"), ("halted", "FREE")):
            razorpay["remote"][sub_id]["status"] = status
            _webhook(f"subscription.{status}", razorpay["remote"][sub_id])
            assert _role(user) == role, status
    finally:
        db.hard_delete_user_account(user.user_id)


def test_billing_never_demotes_an_admin(razorpay):
    admin = _user(UserRole.ADMIN)
    try:
        db.set_subscription(admin.user_id, "sub_admin", "active")
        razorpay["remote"]["sub_admin"] = {"id": "sub_admin", "status": "cancelled"}
        _webhook("subscription.cancelled", razorpay["remote"]["sub_admin"])
        assert _role(admin) == "ADMIN"
    finally:
        db.hard_delete_user_account(admin.user_id)
