"""
JobCopilot - Conversion Feedback Loop & ML Weight Tuning Engine
Correlates tailored resume variations, keywords, and outreach strategies with real-world
recruiter responses (interviews & offers), producing empirical weight adjustments for MatchScorer.
"""

import math
import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple

from app.core.models import ApplicationStatus, ConversionSignal
from app.core.database import get_db

logger = logging.getLogger("jobcopilot.analytics.feedback")


class ConversionFeedbackLoop:
    """Mines application outcome histories and computes calibrated feature weights."""

    MIN_SAMPLES_FOR_CONFIDENCE = 2
    MIN_MULTIPLIER = 0.70
    MAX_MULTIPLIER = 1.30

    @classmethod
    def calibrate_candidate_signals(cls, user_id: str) -> Dict[str, Any]:
        """
        Analyzes past job submissions for a candidate, extracts skill & title features,
        computes empirical response rates, and persists calibrated ConversionSignals.
        """
        db = get_db()
        jobs = db.get_jobs(user_id=user_id)
        if not jobs:
            return {"status": "no_data", "signals_updated": 0}

        applied_jobs = [j for j in jobs if j.status in (
            ApplicationStatus.SUBMITTED, ApplicationStatus.RESPONDED,
            ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER,
            ApplicationStatus.REJECTED
        )]

        if not applied_jobs:
            return {"status": "insufficient_applied_jobs", "signals_updated": 0}

        total_applied = len(applied_jobs)
        total_callbacks = sum(1 for j in applied_jobs if j.status in (ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER))
        baseline_rate = (total_callbacks / total_applied) if total_applied > 0 else 0.05
        effective_baseline = max(baseline_rate, 0.05)

        # Feature accumulators: (feature_type, feature_key) -> {"samples": int, "callbacks": int}
        stats: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(lambda: {"samples": 0, "callbacks": 0})

        for j in applied_jobs:
            is_callback = j.status in (ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER)

            # 1. Platform feature
            plat = j.platform or "Direct"
            stats[("platform", plat.lower())]["samples"] += 1
            if is_callback:
                stats[("platform", plat.lower())]["callbacks"] += 1

            # 2. Seniority feature
            from app.core.match_scorer import MatchScorer
            seniority = MatchScorer.infer_job_seniority(j.title, j.description or "")
            stats[("seniority", seniority.lower())]["samples"] += 1
            if is_callback:
                stats[("seniority", seniority.lower())]["callbacks"] += 1

            # 3. Extract skills from description
            skills = MatchScorer.extract_job_required_skills(f"{j.title} {j.description or ''}")
            for sk in set(skills):
                stats[("skill", sk.lower())]["samples"] += 1
                if is_callback:
                    stats[("skill", sk.lower())]["callbacks"] += 1

        signals_updated = 0
        now_iso = datetime.utcnow().isoformat()

        for (f_type, f_key), counts in stats.items():
            samples = counts["samples"]
            callbacks = counts["callbacks"]

            # Only calibrate features with observed submissions
            if samples < cls.MIN_SAMPLES_FOR_CONFIDENCE:
                multiplier = 1.0
                rate = (callbacks / samples) if samples > 0 else 0.0
            else:
                rate = callbacks / samples
                lift = rate / effective_baseline
                # Dampened multiplier formula: 1.0 + (lift - 1.0) * 0.25, bounded strictly [0.70, 1.30]
                raw_multiplier = 1.0 + (lift - 1.0) * 0.25
                multiplier = max(cls.MIN_MULTIPLIER, min(cls.MAX_MULTIPLIER, round(raw_multiplier, 3)))

            signal = ConversionSignal(
                user_id=user_id,
                feature_type=f_type,
                feature_key=f_key,
                sample_count=samples,
                callback_count=callbacks,
                conversion_rate=round(rate, 4),
                weight_multiplier=multiplier,
                updated_at=now_iso
            )
            db.upsert_conversion_signal(signal)
            signals_updated += 1

        return {
            "status": "calibrated",
            "total_applied": total_applied,
            "total_callbacks": total_callbacks,
            "baseline_conversion_rate": round(baseline_rate * 100, 2),
            "signals_updated": signals_updated
        }

    @classmethod
    def get_feature_multiplier(cls, user_id: str, feature_type: str, feature_key: str) -> float:
        """
        Retrieves the empirical weight multiplier for a given feature.
        Returns bounded multiplier [0.70, 1.30] or 1.0 if insufficient data.
        """
        db = get_db()
        signals = db.get_conversion_signals(user_id=user_id, feature_type=feature_type)
        key_lower = feature_key.lower().strip()
        for s in signals:
            if s.feature_key.lower().strip() == key_lower:
                return float(s.weight_multiplier)
        return 1.0

    @classmethod
    def get_top_converting_insights(cls, user_id: str) -> Dict[str, Any]:
        """Returns candidate's highest and lowest converting skills, platforms, and seniorities."""
        db = get_db()
        signals = db.get_conversion_signals(user_id=user_id)
        if not signals:
            cls.calibrate_candidate_signals(user_id)
            signals = db.get_conversion_signals(user_id=user_id)

        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s in signals:
            by_type[s.feature_type].append({
                "feature": s.feature_key,
                "samples": s.sample_count,
                "callbacks": s.callback_count,
                "conversion_rate_percent": round(s.conversion_rate * 100, 1),
                "multiplier": s.weight_multiplier
            })

        for f_type in by_type:
            by_type[f_type].sort(key=lambda x: (x["conversion_rate_percent"], x["samples"]), reverse=True)

        return {
            "top_skills": by_type.get("skill", [])[:10],
            "platforms": by_type.get("platform", []),
            "seniorities": by_type.get("seniority", [])
        }
