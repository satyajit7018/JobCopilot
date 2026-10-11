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
