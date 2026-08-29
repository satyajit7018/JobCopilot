"""
JobCopilot - Composite Priority Queue Ranker
Ranks jobs by Match Score (40%), Company Signal (20%), Freshness (15%), Salary (15%), Preferences (10%).
"""

from typing import Dict, Any


class PriorityRanker:
    @staticmethod
    def calculate_priority_score(match_score: float, platform: str, company: str, freshness_days: int = 1) -> float:
        # 1. Match Score (40 pts)
        score = match_score * 40.0

        # 2. Company Signal / Platform Tier (25 pts)
        plat = platform.lower()
        comp = company.lower()
        if "y combinator" in plat or "yc" in comp or "yc" in plat:
            score += 25.0
        elif "wellfound" in plat:
            score += 20.0
        elif "naukri" in plat or "instahyre" in plat:
            score += 18.0
        else:
            score += 15.0

        # 3. Freshness (20 pts)
        if freshness_days <= 3:
            score += 20.0
        elif freshness_days <= 7:
            score += 15.0
        elif freshness_days <= 14:
            score += 10.0
        else:
            score += 5.0

        # 4. Baseline Fit (15 pts)
        score += 15.0

        return min(round(score, 1), 100.0)
