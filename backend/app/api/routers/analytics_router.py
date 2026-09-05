"""
JobCopilot - Analytics & Funnel Metrics Router
Provides pipeline conversion rates, time-in-stage benchmarks, and conversion funnel analytics.
"""

from fastapi import APIRouter, Depends
from app.core.models import User
from app.api.auth import get_current_user

router = APIRouter(tags=["analytics"])


@router.get("/analytics/funnel")
async def get_funnel_analytics(current_user: User = Depends(get_current_user)):
    """Returns aggregated pipeline funnel metrics for authenticated tenant with multi-tier caching."""
    from app.core.analytics import AnalyticsEngine
    from app.core.cache import cache_manager

    cached = await cache_manager.get(current_user.user_id, "analytics", "funnel")
    if cached is not None:
        return cached

    result = {
        "status": "success",
        "metrics": AnalyticsEngine.get_funnel_metrics(user_id=current_user.user_id)
    }
    await cache_manager.set(current_user.user_id, "analytics", "funnel", result, ttl_seconds=60)
    return result

