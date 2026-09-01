"""
JobCopilot - Composite Priority Queue Ranker
Ranks jobs on a 0-100 scale: Match Score (40 pts), Company & Board Tier (25 pts),
Freshness Decay (20 pts), and Compensation Alignment (15 pts).
"""

import re
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
        candidate_expected_ctc: str = "15 LPA",
        location: Optional[str] = None
    ) -> float:
        """
        Computes composite priority score:
        - Match Score: 40 points
        - Platform & Company Tier (with Indian Tech Portal Preference): 25 points
        - Freshness Decay: 20 points
        - Compensation Alignment (LPA / INR Native): 15 points
        """
        score = 0.0

        # 1. Match Score (40 pts)
        score += min(match_score, 1.0) * 40.0

        # 2. Company Signal / Board Tier with Indian Tech Portals Priority (25 pts)
        plat = platform.lower()
        comp = company.lower()
        is_yc = "y combinator" in plat or "y combinator" in comp or "(yc" in comp or bool(re.search(r'\byc\b', comp))
        is_indian_portal = any(p in plat for p in ["instahyre", "naukri", "cuvette", "cutshort", "hirist"])
        is_tier1 = "greenhouse" in plat or "lever" in plat or "ashby" in plat or is_yc or is_indian_portal

        if is_tier1:
            score += 25.0  # Tier 1 direct ATS, YC startups & Indian tech portals
        elif "wellfound" in plat:
            score += 22.0  # High-growth venture startups
        elif "indeed" in plat or "linkedin" in plat:
            score += 18.0  # General job aggregators
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
            score += 8.0

        # 5. Indian Tech Hub Bonus (Location Relevance)
        if location:
            loc_lower = location.lower()
            if any(hub in loc_lower for hub in ["bangalore", "bengaluru", "hyderabad", "pune", "gurgaon", "gurugram", "noida", "mumbai", "india"]):
                score += 2.0  # Extra signal for Indian domestic hub alignment

        return min(max(round(score, 1), 5.0), 100.0)
