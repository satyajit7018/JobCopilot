"""
JobCopilot - Composite Priority Queue Ranker
Ranks jobs on a 0-100 scale: Match Score (40 pts), Company & Board Tier (25 pts),
Freshness Decay (20 pts), and Compensation Alignment (15 pts).
"""

from typing import Dict, Any, Optional
from app.core.compensation import CompensationConverter


class PriorityRanker:
    """Computes a holistic 0-100 priority score for queuing autonomous applications."""

    @classmethod
    def calculate_priority_score(
        cls,
        match_score: float,
        platform: str,
        company: str,
        freshness_days: int = 1,
        salary_range: Optional[str] = None,
        candidate_expected_ctc: str = "15 LPA"
    ) -> float:
        """
        Computes composite priority score:
        - Match Score: 40 points
        - Platform & Company Tier: 25 points
        - Freshness Decay: 20 points
        - Compensation Alignment: 15 points
        """
        score = 0.0

        # 1. Match Score (40 pts)
        score += min(match_score, 1.0) * 40.0

        # 2. Company Signal / Board Tier (25 pts)
        plat = platform.lower()
        comp = company.lower()
        if "y combinator" in plat or "yc" in comp or "ashby" in plat or "greenhouse" in plat or "lever" in plat:
            score += 25.0  # Tier 1 direct high-signal ATS & YC
        elif "wellfound" in plat:
            score += 20.0  # Tier 2 venture startups
        elif "naukri" in plat or "indeed" in plat:
            score += 15.0  # Tier 3 broad aggregator
        else:
            score += 18.0

        # 3. Freshness Decay (20 pts)
        if freshness_days <= 1:
            score += 20.0
        elif freshness_days <= 3:
            score += 16.0
        elif freshness_days <= 7:
            score += 12.0
        elif freshness_days <= 14:
            score += 6.0
        else:
            score += 2.0

        # 4. Compensation Alignment (15 pts)
        if salary_range:
            job_inr = CompensationConverter.parse_to_base_inr(salary_range)
            expected_inr = CompensationConverter.parse_to_base_inr(candidate_expected_ctc)
            if job_inr >= expected_inr:
                score += 15.0
            elif job_inr >= expected_inr * 0.8:
                score += 10.0
            else:
                score += 5.0
        else:
            # Neutral compensation baseline
            score += 12.0

        return min(max(round(score, 1), 5.0), 100.0)
