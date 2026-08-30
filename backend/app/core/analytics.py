"""
JobCopilot - Analytics & Funnel Metrics Engine
Computes real-time conversion rates, pipeline velocity, platform distributions,
and Knowledge Vault automation coverage metrics.
"""

from typing import Dict, Any, List
from app.core.models import ApplicationStatus
from app.core.database import db


class AnalyticsEngine:
    """Computes holistic pipeline conversion metrics and telemetry."""

    @classmethod
    def get_funnel_stats(cls, user_id: str = "") -> Dict[str, Any]:
        """Convenience alias for get_funnel_metrics."""
        return cls.get_funnel_metrics(user_id=user_id)

    @classmethod
    def get_funnel_metrics(cls, user_id: str = "") -> Dict[str, Any]:
        """Calculates stage counts, conversion rates, and platform breakdowns for user."""
        jobs = db.get_jobs(user_id=user_id)
        vault_entries = db.get_vault_entries(user_id=user_id)

        total_sourced = len(jobs)
        total_applied = sum(1 for j in jobs if j.status in [
            ApplicationStatus.SUBMITTED, ApplicationStatus.RESPONDED,
            ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED,
            ApplicationStatus.OFFER
        ])

        dry_run_count = sum(1 for j in jobs if getattr(j, "submission_mode", None) == "DRY_RUN")
        live_count = sum(1 for j in jobs if getattr(j, "submission_mode", None) == "LIVE")

        interviews_count = sum(1 for j in jobs if j.status == ApplicationStatus.INTERVIEW)
        assessments_count = sum(1 for j in jobs if j.status == ApplicationStatus.RESPONDED)
        rejections_count = sum(1 for j in jobs if j.status == ApplicationStatus.REJECTED)
        offers_count = sum(1 for j in jobs if j.status == ApplicationStatus.OFFER)

        # Calculate Response Rate
        total_responses = interviews_count + assessments_count + rejections_count
        response_rate = round((total_responses / max(total_applied, 1)) * 100, 1) if total_applied > 0 else 0.0
        interview_conversion_rate = round((interviews_count / max(total_applied, 1)) * 100, 1) if total_applied > 0 else 0.0

        # Platform Distribution
        platform_counts: Dict[str, int] = {}
        for j in jobs:
            plat = j.platform or "Direct"
            platform_counts[plat] = platform_counts.get(plat, 0) + 1

        # Match Score Distribution
        avg_match_score = round(sum(j.match_score for j in jobs) / max(total_sourced, 1) * 100, 1) if total_sourced > 0 else 0.0

        # Knowledge Vault Automation Coverage
        total_vault_uses = sum(e.usage_count for e in vault_entries)
        vault_slots_count = len(vault_entries)

        return {
            "total_sourced": total_sourced,
            "total_applied": total_applied,
            "dry_run_count": dry_run_count,
            "live_count": live_count,
            "interviews_count": interviews_count,
            "assessments_count": assessments_count,
            "rejections_count": rejections_count,
            "offers_count": offers_count,
            "response_rate_percent": response_rate,
            "interview_conversion_rate": interview_conversion_rate,
            "avg_match_score": avg_match_score,
            "platform_distribution": platform_counts,
            "vault_slots_count": vault_slots_count,
            "total_vault_uses": total_vault_uses
        }
