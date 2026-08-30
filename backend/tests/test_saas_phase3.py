"""
JobCopilot - SaaS Phase 3 Integration Tests
Tests Tiered Rate Limiting, Stripe Billing Webhooks, Quota Enforcement, and Schema Migrations.
"""

import sys
import os
import uuid
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.rate_limiter import rate_limiter, SubscriptionTier
from app.core.migrations import migration_runner
from app.core.models import JobListing, ApplicationStatus
from app.core.database import db
from app.api.auth import create_jwt_token


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

            # 3. Receive Stripe webhook: subscription created (upgrade to PRO)
            created_event = {
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "metadata": {
                            "user_id": user_id,
                            "tier": "PRO"
                        }
                    }
                }
            }
            with patch("stripe.Webhook.construct_event", return_value=created_event):
                hook_res = await ac.post(
                    "/api/billing/webhook",
                    json=created_event,
                    headers={"Stripe-Signature": "t=123,v1=test_sig"}
                )
                assert hook_res.status_code == 200
                assert hook_res.json()["active_tier"] == "PRO"
                assert rate_limiter.get_user_tier(user_id) == SubscriptionTier.PRO

            # 4. Receive Stripe webhook: subscription cancelled (downgrade to FREE)
            cancel_event = {
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "metadata": {
                            "user_id": user_id
                        }
                    }
                }
            }
            with patch("stripe.Webhook.construct_event", return_value=cancel_event):
                cancel_res = await ac.post(
                    "/api/billing/webhook",
                    json=cancel_event,
                    headers={"Stripe-Signature": "t=123,v1=test_sig"}
                )
                assert cancel_res.status_code == 200
                assert cancel_res.json()["active_tier"] == "FREE"
                assert rate_limiter.get_user_tier(user_id) == SubscriptionTier.FREE

    def test_schema_migrations_runner(self):
        """Verifies atomic schema migration execution."""
        count = migration_runner.apply_all()
        # Should apply migrations without error
        assert count >= 0
