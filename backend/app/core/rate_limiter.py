"""
JobCopilot - Tiered Subscription & Rate Limiting Engine
Enforces daily application caps, proxy routing access, and priority queue routing based on user subscription tier.

Tiers:
- FREE:  5 auto-applies/day,  standard discovery, local proxies
- PRO:   30 auto-applies/day, 0-day feeds, triple-threat outreach ($29/mo)
- ELITE: Unlimited applies,   residential proxy rotation, priority queue ($79/mo)
"""

import time
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel


class SubscriptionTier(str, Enum):
    FREE = "FREE"
    PRO = "PRO"
    ELITE = "ELITE"


class TierConfig:
    LIMITS = {
        SubscriptionTier.FREE: {
            "daily_applies": 5,
            "can_use_residential_proxies": False,
            "has_0day_priority_feeds": False,
            "has_triple_threat_outreach": False,
            "price_usd_monthly": 0
        },
        SubscriptionTier.PRO: {
            "daily_applies": 30,
            "can_use_residential_proxies": False,
            "has_0day_priority_feeds": True,
            "has_triple_threat_outreach": True,
            "price_usd_monthly": 29
        },
        SubscriptionTier.ELITE: {
            "daily_applies": 999999,
            "can_use_residential_proxies": True,
            "has_0day_priority_feeds": True,
            "has_triple_threat_outreach": True,
            "price_usd_monthly": 79
        }
    }


class RateLimiter:
    """Tracks and enforces daily usage quotas per user."""

    def __init__(self):
        # user_id -> {"date": "YYYY-MM-DD", "count": int}
        self.usage_ledger: Dict[str, Dict[str, Any]] = {}
        # user_id -> SubscriptionTier
        self.user_subscriptions: Dict[str, SubscriptionTier] = {}

    def _get_today_str(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def get_user_tier(self, user_id: str) -> SubscriptionTier:
        return self.user_subscriptions.get(user_id, SubscriptionTier.FREE)

    def set_user_tier(self, user_id: str, tier: SubscriptionTier) -> None:
        self.user_subscriptions[user_id] = tier

    def get_remaining_applies(self, user_id: str) -> int:
        tier = self.get_user_tier(user_id)
        limit = TierConfig.LIMITS[tier]["daily_applies"]
        today = self._get_today_str()

        record = self.usage_ledger.get(user_id, {"date": today, "count": 0})
        if record["date"] != today:
            return limit

        return max(0, limit - record["count"])

    def can_apply(self, user_id: str) -> bool:
        return self.get_remaining_applies(user_id) > 0

    def record_apply(self, user_id: str) -> bool:
        """Increments daily apply count if within limits."""
        if not self.can_apply(user_id):
            return False

        today = self._get_today_str()
        record = self.usage_ledger.get(user_id, {"date": today, "count": 0})
        if record["date"] != today:
            record = {"date": today, "count": 0}

        record["count"] += 1
        self.usage_ledger[user_id] = record
        return True

    def get_usage_summary(self, user_id: str) -> Dict[str, Any]:
        tier = self.get_user_tier(user_id)
        config = TierConfig.LIMITS[tier]
        remaining = self.get_remaining_applies(user_id)
        applied_today = config["daily_applies"] - remaining if tier != SubscriptionTier.ELITE else self.usage_ledger.get(user_id, {}).get("count", 0)

        return {
            "user_id": user_id,
            "tier": tier.value,
            "daily_limit": "Unlimited" if tier == SubscriptionTier.ELITE else config["daily_applies"],
            "applied_today": applied_today,
            "remaining_today": "Unlimited" if tier == SubscriptionTier.ELITE else remaining,
            "can_use_residential_proxies": config["can_use_residential_proxies"],
            "has_0day_priority_feeds": config["has_0day_priority_feeds"],
            "has_triple_threat_outreach": config["has_triple_threat_outreach"],
            "price_usd_monthly": config["price_usd_monthly"]
        }


# Global Rate Limiter Singleton
rate_limiter = RateLimiter()
