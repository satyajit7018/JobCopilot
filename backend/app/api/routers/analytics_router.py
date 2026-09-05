"""
JobCopilot - Analytics, Cohort Warehouse & A/B Experimentation Router
Provides real-time pipeline funnel analytics, cohort retention matrices, conversion feedback loops,
and statistical A/B testing evaluation with tenant isolation.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from app.core.models import User
from app.api.auth import get_current_user
from app.core.database import get_db

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


@router.post("/analytics/events")
async def record_telemetry_event(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Ingests a telemetry event into the Analytics Warehouse."""
    from app.analytics.warehouse import AnalyticsWarehouse

    event_type = payload.get("event_type")
    entity_type = payload.get("entity_type", "general")
    entity_id = payload.get("entity_id", "default")
    properties = payload.get("properties", {})

    if not event_type:
        raise HTTPException(status_code=400, detail="Missing required 'event_type' in event payload.")

    event = AnalyticsWarehouse.track_event(
        user_id=current_user.user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        properties=properties
    )
    return {
        "status": "success",
        "event_id": event.event_id,
        "recorded_at": event.created_at
    }


@router.get("/analytics/events")
async def list_telemetry_events(
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user)
):
    """Retrieves recent analytics events for the authenticated tenant."""
    db = get_db()
    events = db.query_analytics_events(
        user_id=current_user.user_id,
        event_type=event_type,
        limit=limit
    )
    return {
        "status": "success",
        "total": len(events),
        "events": [e.model_dump() if hasattr(e, "model_dump") else e.dict() for e in events]
    }


@router.get("/analytics/cohorts")
async def get_cohort_analytics(
    interval: str = Query("weekly", pattern="^(weekly|monthly)$"),
    current_user: User = Depends(get_current_user)
):
    """Returns application cohort progression and conversion velocity over time."""
    from app.analytics.warehouse import AnalyticsWarehouse

    cohorts = AnalyticsWarehouse.get_funnel_cohorts(
        user_id=current_user.user_id,
        interval=interval
    )
    return {
        "status": "success",
        "interval": interval,
        "cohorts": cohorts
    }


@router.get("/analytics/conversions")
async def get_conversion_insights(current_user: User = Depends(get_current_user)):
    """Returns top-converting skills, platform breakdown, and velocity turnaround times."""
    from app.analytics.feedback_loop import ConversionFeedbackLoop
    from app.analytics.warehouse import AnalyticsWarehouse

    insights = ConversionFeedbackLoop.get_top_converting_insights(user_id=current_user.user_id)
    platforms = AnalyticsWarehouse.get_platform_conversion_analytics(user_id=current_user.user_id)
    velocities = AnalyticsWarehouse.get_velocity_benchmarks(user_id=current_user.user_id)

    return {
        "status": "success",
        "insights": insights,
        "platforms": platforms,
        "velocity_benchmarks": velocities
    }


@router.post("/analytics/calibrate")
async def calibrate_conversion_weights(current_user: User = Depends(get_current_user)):
    """Triggers feedback loop calibration to update MatchScorer dynamic empirical weights."""
    from app.analytics.feedback_loop import ConversionFeedbackLoop

    result = ConversionFeedbackLoop.calibrate_candidate_signals(user_id=current_user.user_id)
    return {
        "status": "success",
        "calibration": result
    }


@router.get("/analytics/experiments")
async def list_ab_experiments(current_user: User = Depends(get_current_user)):
    """Lists all active and historical A/B experimentation campaigns."""
    db = get_db()
    experiments = db.list_ab_experiments(user_id=current_user.user_id)
    return {
        "status": "success",
        "experiments": [e.model_dump() if hasattr(e, "model_dump") else e.dict() for e in experiments]
    }


@router.post("/analytics/experiments")
async def create_ab_experiment(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Initializes a new A/B testing experiment."""
    from app.analytics.ab_testing import ABTestingEngine

    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Experiment name is required.")

    experiment = ABTestingEngine.create_experiment(
        user_id=current_user.user_id,
        name=name,
        description=payload.get("description"),
        variants=payload.get("variants")
    )
    return {
        "status": "success",
        "experiment": experiment.model_dump() if hasattr(experiment, "model_dump") else experiment.dict()
    }


@router.post("/analytics/experiments/{experiment_id}/evaluate")
async def evaluate_ab_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user)
):
    """Evaluates sample proportions, two-sample pooled Z-score, p-value, and statistical significance."""
    from app.analytics.ab_testing import ABTestingEngine

    try:
        evaluation = ABTestingEngine.evaluate_experiment(
            experiment_id=experiment_id,
            user_id=current_user.user_id
        )
        return {
            "status": "success",
            "evaluation": evaluation
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
