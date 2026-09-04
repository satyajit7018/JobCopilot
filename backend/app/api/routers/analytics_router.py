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
    """Returns aggregated pipeline funnel metrics for authenticated tenant."""
    from app.core.analytics import AnalyticsEngine
    return {
        "status": "success",
        "metrics": AnalyticsEngine.get_funnel_metrics(user_id=current_user.user_id)
    }
