"""
JobCopilot - A/B Testing & Statistical Experimentation Framework
Provides deterministic variant routing, conversion tracking, two-sample Z-tests,
p-value statistical significance evaluation, and 95% confidence intervals.
"""

import math
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from app.core.models import ABExperiment, ABVariant, ABAssignment
from app.core.database import get_db

logger = logging.getLogger("jobcopilot.analytics.ab_testing")


class ABTestingEngine:
    """Manages multi-variant experiments, deterministic routing, and statistical validation."""

    @classmethod
    def create_experiment(
        cls,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        variants: Optional[List[Dict[str, Any]]] = None
    ) -> ABExperiment:
        """Initializes a new A/B experiment with default control/treatment if none supplied."""
        raw_variants = variants or [
            {"variant_id": "control_a", "name": "Control (Keyword Dense)", "weight": 0.5, "description": "Standard keyword prioritization"},
            {"variant_id": "variant_b", "name": "Treatment (STAR Narrative)", "weight": 0.5, "description": "Accomplishment and STAR-focused emphasis"}
        ]
        parsed_variants = [ABVariant(**v) for v in raw_variants]

        experiment = ABExperiment(
            user_id=user_id,
            name=name,
            description=description,
            variants=parsed_variants,
            status="ACTIVE"
        )
        db = get_db()
        db.create_ab_experiment(experiment)
        return experiment

    @classmethod
    def assign_variant(cls, experiment_id: str, user_id: str, entity_id: str) -> str:
        """
        Deterministically assigns an entity (e.g. a job application or outreach attempt)
        to a variant using SHA-256 hash modulus mapping.
        Guarantees that an entity always sees the exact same variant across re-runs.
        """
        db = get_db()
        existing = db.get_ab_assignment(experiment_id, user_id, entity_id)
        if existing:
            return existing.variant

        experiment = db.get_ab_experiment(experiment_id, user_id)
        if not experiment or not experiment.variants:
            return "control_a"

        # Deterministic hash to integer 0..999
        hash_digest = hashlib.sha256(f"{user_id}:{entity_id}:{experiment_id}".encode("utf-8")).hexdigest()
        bucket = int(hash_digest[:8], 16) % 1000  # 0 to 999

        # Normalize weights to cumulative integer buckets
        total_weight = sum(v.weight for v in experiment.variants) or 1.0
        cumulative = 0.0
        selected_variant = experiment.variants[0].variant_id

        for v in experiment.variants:
            cumulative += (v.weight / total_weight) * 1000.0
            if bucket < cumulative:
                selected_variant = v.variant_id
                break

        # Persist assignment
        db.assign_ab_variant(experiment_id, user_id, entity_id, selected_variant)
        return selected_variant

    @classmethod
    def record_conversion(cls, experiment_id: str, user_id: str, entity_id: str) -> bool:
        """Records a successful conversion (e.g. interview callback or offer) for the assignment."""
        db = get_db()
        return db.record_ab_conversion(experiment_id, user_id, entity_id)

    @classmethod
    def evaluate_experiment(cls, experiment_id: str, user_id: str) -> Dict[str, Any]:
        """
        Computes sample sizes, conversion rates, standard errors, two-sample pooled Z-score,
        two-tailed p-value, 95% confidence intervals, and statistical significance.
        """
        db = get_db()
        experiment = db.get_ab_experiment(experiment_id, user_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found.")

        stats = db.get_ab_experiment_stats(experiment_id, user_id)
        variants_dict = stats.get("variants", {})

        # Ensure all defined variants are represented in stats
        for v in experiment.variants:
            if v.variant_id not in variants_dict:
                variants_dict[v.variant_id] = {
                    "samples": 0,
                    "conversions": 0,
                    "conversion_rate_percent": 0.0
                }

        # If at least 2 variants, perform two-sample test (Control vs Treatment)
        variant_keys = list(variants_dict.keys())
        stats_evaluation: Dict[str, Any] = {
            "experiment_id": experiment_id,
            "name": experiment.name,
            "status": experiment.status,
            "total_samples": stats.get("total_samples", 0),
            "total_conversions": stats.get("total_conversions", 0),
            "variants": variants_dict,
            "significance_tested": False,
            "is_statistically_significant": False,
            "p_value": None,
            "z_score": None,
            "winner": None
        }

        if len(variant_keys) >= 2:
            key_a, key_b = variant_keys[0], variant_keys[1]
            var_a = variants_dict[key_a]
            var_b = variants_dict[key_b]

            n_a, x_a = var_a["samples"], var_a["conversions"]
            n_b, x_b = var_b["samples"], var_b["conversions"]

            stats_evaluation["significance_tested"] = True

            if n_a >= 5 and n_b >= 5:
                p_a = x_a / n_a
                p_b = x_b / n_b

                # Pooled sample proportion
                p_pool = (x_a + x_b) / (n_a + n_b)
                se_pool = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n_a + 1.0 / n_b)) if p_pool not in (0.0, 1.0) else 0.0

                if se_pool > 0.0:
                    z_score = (p_b - p_a) / se_pool
                    # Two-tailed p-value using normal distribution error function: p = 1.0 - erf(|z| / sqrt(2))
                    p_value = 1.0 - math.erf(abs(z_score) / math.sqrt(2.0))
                else:
                    z_score = 0.0
                    p_value = 1.0

                # 95% Confidence Interval for difference in proportions
                se_diff = math.sqrt((p_a * (1.0 - p_a) / n_a) + (p_b * (1.0 - p_b) / n_b))
                ci_margin = 1.96 * se_diff
                rate_diff = p_b - p_a

                is_sig = p_value < 0.05
                winner = None
                if is_sig:
                    winner = key_b if p_b > p_a else key_a

                stats_evaluation.update({
                    "is_statistically_significant": is_sig,
                    "p_value": round(p_value, 4),
                    "z_score": round(z_score, 4),
                    "difference_in_conversion_rate": round(rate_diff * 100, 2),
                    "confidence_interval_95": [
                        round((rate_diff - ci_margin) * 100, 2),
                        round((rate_diff + ci_margin) * 100, 2)
                    ],
                    "winner": winner
                })
            else:
                stats_evaluation["reason"] = f"Insufficient sample size (require >= 5 samples per variant; got {n_a} and {n_b})"

        return stats_evaluation
