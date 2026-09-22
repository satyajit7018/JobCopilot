"""
JobCopilot - SaaS Phase 3 Integration Tests
Tests Tiered Rate Limiting, Stripe Billing Webhooks, Quota Enforcement, and Schema Migrations.
"""

import sys
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import create_jwt_token
from app.core.migrations import migration_runner
from app.core.rate_limiter import SubscriptionTier, rate_limiter
from app.main import app


class TestSaaSPhase3:

    def test_rate_limiter_quotas(self):
        """Verifies daily quota tracking and tier transitions."""
        user_id = f"user_{uuid.uuid4().hex[:8]}"

        # 1. Default FREE tier: 5 applies
        assert rate_limiter.get_user_tier(user_id) == SubscriptionTier.FREE
        assert rate_limiter.get_remaining_applies(user_id) == 5

        # 2. Record 5 applies
        for _ in range(5):
            assert rate_limiter.record_apply(user_id) is True

        # 3. 6th apply blocked
        assert rate_limiter.can_apply(user_id) is False
        assert rate_limiter.record_apply(user_id) is False

        # 4. Upgrade to PRO tier: 30 applies
        rate_limiter.set_user_tier(user_id, SubscriptionTier.PRO)
        assert rate_limiter.can_apply(user_id) is True
        assert rate_limiter.get_remaining_applies(user_id) == 25  # 30 - 5

        # 5. Upgrade to ELITE tier: unlimited
        rate_limiter.set_user_tier(user_id, SubscriptionTier.ELITE)
        summary = rate_limiter.get_usage_summary(user_id)
        assert summary["daily_limit"] == "Unlimited"
        assert summary["can_use_residential_proxies"] is True

    @pytest.mark.asyncio
    async def test_billing_checkout_and_webhook_lifecycle(self, monkeypatch):
        """Verifies Stripe checkout generation and webhook tier adjustment."""
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_saas")
        token = create_jwt_token(
            {"sub": "usr_test_tenant_a", "email": "test_a@jobcopilot.test", "role": "FREE", "type": "access"},
            timedelta(minutes=60)
        )
        headers = {"Authorization": f"Bearer {token}"}
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            user_id = f"cust_{uuid.uuid4().hex[:8]}"

            # 1. Fetch initial billing plan
            plan_res = await ac.get("/api/billing/plan", headers=headers)
            assert plan_res.status_code == 200
            assert plan_res.json()["status"] == "success"

            # 2. Generate Checkout session for PRO
            checkout_res = await ac.post("/api/billing/checkout", json={"tier": "PRO"}, headers=headers)
            assert checkout_res.status_code == 200
            data = checkout_res.json()
            assert "checkout.stripe.com" in data["checkout_url"]
            assert data["tier"] == "PRO"
            assert data["amount_usd"] == 29

            # 3. Webhooks, shaped like real Stripe payloads and delivered as real stripe.Event
            #    objects (not dicts) so the construct_event -> to_dict path is exercised (audit P0-6).
            import stripe

            from app.core.database import db
            from app.core.models import User, UserRole
            from app.core.settings import settings as app_settings
            db.create_user(User(user_id=user_id, email=f"{user_id}@billing.test", password_hash="x", role=UserRole.FREE))
            customer_id = f"cus_{uuid.uuid4().hex[:10]}"

            def as_event(d):
                return stripe.Event.construct_from(d, "sk_test")

            async def deliver(ev):
                with patch("stripe.Webhook.construct_event", return_value=as_event(ev)):
                    return await ac.post("/api/billing/webhook", json=ev, headers={"Stripe-Signature": "t=123,v1=test_sig"})

            completed = {"id": "evt_c", "object": "event", "type": "checkout.session.completed", "data": {"object": {
                "id": "cs_1", "object": "checkout.session", "customer": customer_id, "client_reference_id": user_id,
                "metadata": {"user_id": user_id, "tier": "PRO"}}}}
            res = await deliver(completed)
            assert res.status_code == 200 and res.json()["active_tier"] == "PRO"
            assert db.get_user_id_by_stripe_customer(customer_id) == user_id
            assert rate_limiter.get_user_tier(user_id) == SubscriptionTier.PRO

            # Upgrade via subscription.updated: tier comes from the price id, and no metadata is needed.
            updated = {"id": "evt_u", "object": "event", "type": "customer.subscription.updated", "data": {"object": {
                "id": "sub_1", "object": "subscription", "customer": customer_id, "status": "active", "metadata": {},
                "items": {"data": [{"price": {"id": app_settings.STRIPE_ELITE_PRICE_ID}}]}}}}
            res = await deliver(updated)
            assert res.status_code == 200 and res.json()["active_tier"] == "ELITE"

            # 4. Cancellation: real Subscription objects carry no checkout metadata (audit P1-6).
            deleted = {"id": "evt_d", "object": "event", "type": "customer.subscription.deleted", "data": {"object": {
                "id": "sub_1", "object": "subscription", "customer": customer_id, "status": "canceled", "metadata": {}}}}
            res = await deliver(deleted)
            assert res.status_code == 200 and res.json()["active_tier"] == "FREE"
            assert rate_limiter.get_user_tier(user_id) == SubscriptionTier.FREE

    def test_schema_migrations_runner(self):
        """Verifies atomic schema migration execution."""
        count = migration_runner.apply_all()
        # Should apply migrations without error
        assert count >= 0
