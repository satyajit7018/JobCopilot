"""
JobCopilot - Analytics Event Warehouse & Cohort Analysis Engine
Streams full-lifecycle candidate funnel telemetry, aggregates retention and conversion cohorts,
and computes platform efficiency benchmarks with multi-tenant isolation.
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.database import get_db
from app.core.models import AnalyticsEvent, ApplicationStatus

logger = logging.getLogger("jobcopilot.analytics.warehouse")


class AnalyticsWarehouse:
    """Manages event stream ingestion, funnel metrics, and cohort retention matrices."""

    @classmethod
    def track_event(
        cls,
        user_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> AnalyticsEvent:
        """
        Records an event into the analytics warehouse.
        Standard event_types:
        - job.discovered, job.scored, resume.tailored, job.applied,
        - interview.received, offer.received, job.rejected, email.parsed
        """
        event = AnalyticsEvent(
            user_id=user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            properties=properties or {},
            created_at=datetime.utcnow().isoformat()
        )
        db = get_db()
        db.record_analytics_event(event)
        return event

    @classmethod
    def get_funnel_cohorts(cls, user_id: str, interval: str = "weekly") -> List[Dict[str, Any]]:
        """
        Groups applications into weekly or monthly cohorts based on application date,
        tracking conversion progression across stages: Applied -> Interview -> Offer -> Rejected.
        """
        db = get_db()
        jobs = db.get_jobs(user_id=user_id)
        if not jobs:
            return []

        cohorts: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "applied": 0,
            "interviews": 0,
            "offers": 0,
            "rejected": 0,
            "pending": 0,
            "durations": []
        })

        for job in jobs:
            # Use applied_at or created_at for cohort grouping
            date_str = job.applied_at or job.created_at
            if not date_str:
                continue

            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00").split("+")[0])
            except Exception:
                dt = datetime.utcnow()

            if interval == "monthly":
                cohort_key = dt.strftime("%Y-%m")
            else:
                # Default: weekly (ISO calendar week: YYYY-Www)
                year, week, _ = dt.isocalendar()
                cohort_key = f"{year}-W{week:02d}"

            cohort = cohorts[cohort_key]
            cohort["applied"] += 1

            if job.status == ApplicationStatus.INTERVIEW:
                cohort["interviews"] += 1
            elif job.status == ApplicationStatus.OFFER:
                cohort["offers"] += 1
                cohort["interviews"] += 1  # Offers traversed interview
            elif job.status == ApplicationStatus.REJECTED:
                cohort["rejected"] += 1
            else:
                cohort["pending"] += 1

            # Track response latency if responded
            interview_date = getattr(job, "interview_date", None)
            created_at = getattr(job, "created_at", None)
            if job.applied_at and (interview_date or job.status in (ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER, ApplicationStatus.REJECTED)):
                try:
                    app_dt = datetime.fromisoformat(job.applied_at.replace("Z", "").split("+")[0])
                    end_str = interview_date or created_at
                    if end_str:
                        end_dt = datetime.fromisoformat(end_str.replace("Z", "").split("+")[0])
                        days = max(0, (end_dt - app_dt).total_seconds() / 86400.0)
                        cohort["durations"].append(days)
                except Exception:
                    pass

        result = []
        for cohort_key in sorted(cohorts.keys()):
            data = cohorts[cohort_key]
            applied = data["applied"]
            interviews = data["interviews"]
            offers = data["offers"]
            rejected = data["rejected"]

            interview_rate = round((interviews / applied) * 100, 1) if applied > 0 else 0.0
            offer_rate = round((offers / applied) * 100, 1) if applied > 0 else 0.0
            avg_days_to_response = round(sum(data["durations"]) / max(len(data["durations"]), 1), 1) if data["durations"] else None

            result.append({
                "cohort_period": cohort_key,
                "total_applied": applied,
                "interviews_count": interviews,
                "offers_count": offers,
                "rejected_count": rejected,
                "interview_conversion_rate": interview_rate,
                "offer_conversion_rate": offer_rate,
                "avg_response_days": avg_days_to_response
            })

        return result

    @classmethod
    def get_platform_conversion_analytics(cls, user_id: str) -> Dict[str, Any]:
        """
        Calculates callback rates, interview conversions, and application counts
        segmented by ATS board / job portal platform (e.g. Greenhouse, Lever, Ashby, LinkedIn, Naukri).
        """
        db = get_db()
        jobs = db.get_jobs(user_id=user_id)
        if not jobs:
            return {}

        platforms: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "applied": 0,
            "interviews": 0,
            "offers": 0,
            "rejected": 0,
            "avg_match_score": 0.0,
            "scores": []
        })

        for job in jobs:
            plat = job.platform or "Direct"
            p_data = platforms[plat]
            p_data["applied"] += 1
            p_data["scores"].append(job.match_score)

            if job.status == ApplicationStatus.INTERVIEW:
                p_data["interviews"] += 1
            elif job.status == ApplicationStatus.OFFER:
                p_data["offers"] += 1
                p_data["interviews"] += 1
            elif job.status == ApplicationStatus.REJECTED:
                p_data["rejected"] += 1

        analytics = {}
        for plat, data in platforms.items():
            applied = data["applied"]
            interviews = data["interviews"]
            offers = data["offers"]
            callback_rate = round((interviews / applied) * 100, 1) if applied > 0 else 0.0
            avg_score = round(sum(data["scores"]) / max(len(data["scores"]), 1) * 100, 1) if data["scores"] else 0.0

            analytics[plat] = {
                "total_applied": applied,
                "interviews": interviews,
                "offers": offers,
                "callback_rate_percent": callback_rate,
                "avg_match_score": avg_score
            }

        return analytics

    @classmethod
    def get_velocity_benchmarks(cls, user_id: str) -> Dict[str, Any]:
        """Calculates end-to-end velocity metrics and pipeline turnaround times."""
        db = get_db()
        jobs = db.get_jobs(user_id=user_id)

        response_latencies = []
        interview_latencies = []

        for job in jobs:
            if not job.applied_at:
                continue
            try:
                app_dt = datetime.fromisoformat(job.applied_at.replace("Z", "").split("+")[0])
                interview_date = getattr(job, "interview_date", None)
                created_at = getattr(job, "created_at", None)
                if job.status in (ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER) and interview_date:
                    int_dt = datetime.fromisoformat(interview_date.replace("Z", "").split("+")[0])
                    diff_days = (int_dt - app_dt).total_seconds() / 86400.0
                    if diff_days >= 0:
                        interview_latencies.append(diff_days)
                        response_latencies.append(diff_days)
                elif job.status == ApplicationStatus.REJECTED and created_at:
                    up_dt = datetime.fromisoformat(created_at.replace("Z", "").split("+")[0])
                    diff_days = (up_dt - app_dt).total_seconds() / 86400.0
                    if diff_days >= 0:
                        response_latencies.append(diff_days)
            except Exception:
                pass

        def _median(vals: List[float]) -> Optional[float]:
            if not vals:
                return None
            s = sorted(vals)
            n = len(s)
            mid = n // 2
            return round((s[mid] if n % 2 != 0 else (s[mid - 1] + s[mid]) / 2.0), 1)

        return {
            "median_days_to_first_response": _median(response_latencies),
            "median_days_to_interview": _median(interview_latencies),
            "total_tracked_responses": len(response_latencies)
        }
