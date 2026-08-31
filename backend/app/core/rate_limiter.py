"""
JobCopilot - Tiered Subscription & Rate Limiting Engine
Enforces daily application caps, proxy routing access, and priority queue routing based on user subscription tier.
Backed by persistent database storage (user_daily_usage table).

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
    """Tracks and enforces daily usage quotas per user with DB persistence."""

    def __init__(self):
        self.user_subscriptions: Dict[str, SubscriptionTier] = {}

    def _get_today_str(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def get_user_tier(self, user_id: str) -> SubscriptionTier:
        if user_id in self.user_subscriptions:
            return self.user_subscriptions[user_id]
        from app.core.database import db
        user = db.get_user_by_id(user_id)
        if user and user.role:
            role_val = user.role.value if hasattr(user.role, 'value') else str(user.role)
            try:
                tier = SubscriptionTier(role_val.upper())
                self.user_subscriptions[user_id] = tier
                return tier
            except ValueError:
                pass
        return SubscriptionTier.FREE

    def invalidate_cache(self, user_id: Optional[str] = None) -> None:
        """Invalidates in-memory subscription tier cache for a specific user or all users."""
        if user_id:
            self.user_subscriptions.pop(user_id, None)
        else:
            self.user_subscriptions.clear()

    def set_user_tier(self, user_id: str, tier: SubscriptionTier, sync_db: bool = True) -> None:
        """Sets user tier in-memory and optionally synchronizes to database."""
        self.user_subscriptions[user_id] = tier
        if sync_db:
            try:
                from app.core.database import db
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE users SET role = ?, updated_at = ? WHERE user_id = ?",
                        (tier.value, time.strftime("%Y-%m-%dT%H:%M:%S"), user_id)
                    )
                    conn.commit()
            except Exception:
                pass

    def get_remaining_applies(self, user_id: str) -> int:
        tier = self.get_user_tier(user_id)
        limit = TierConfig.LIMITS[tier]["daily_applies"]
        today = self._get_today_str()
        from app.core.database import db
        used = db.get_daily_usage(user_id, today)
        return max(0, limit - used)

    def can_apply(self, user_id: str) -> bool:
        return self.get_remaining_applies(user_id) > 0

    def record_apply(self, user_id: str) -> bool:
        """Increments daily apply count if within limits."""
        if not self.can_apply(user_id):
            return False

        today = self._get_today_str()
        from app.core.database import db
        db.increment_daily_usage(user_id, today)
        return True

    def get_usage_summary(self, user_id: str) -> Dict[str, Any]:
        tier = self.get_user_tier(user_id)
        config = TierConfig.LIMITS[tier]
        remaining = self.get_remaining_applies(user_id)
        today = self._get_today_str()
        from app.core.database import db
        applied_today = db.get_daily_usage(user_id, today)

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
