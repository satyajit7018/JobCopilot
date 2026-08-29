"""
JobCopilot - Resume-to-Job Description Match Scorer
Computes semantic skill overlap and suitability percentage (0.0 to 1.0).
"""

import re
from typing import List, Set
from app.core.models import CandidateProfile


class MatchScorer:
    @staticmethod
    def compute_match_score(profile: CandidateProfile, job_title: str, job_description: str) -> float:
        text = (job_title + " " + job_description).lower()
        candidate_skills = [s.lower() for s in profile.skills]
        if not candidate_skills:
            return 0.50

        # 1. Skill overlap score (60% weight)
        matched_skills = [s for s in candidate_skills if re.search(r'\b' + re.escape(s) + r'\b', text)]
        skill_score = len(matched_skills) / max(len(candidate_skills), 1)

        # 2. Title relevance score (40% weight)
        title_words = set(re.findall(r'\b[a-zA-Z]+\b', job_title.lower()))
        profile_keywords = set([s.lower() for s in profile.skills] + ["engineer", "developer", "ai", "ml", "python", "data", "software", "backend"])
        title_matches = title_words.intersection(profile_keywords)
        title_score = len(title_matches) / max(len(title_words), 1)

        final_score = (skill_score * 0.60) + (title_score * 0.40)
        return min(max(round(final_score, 2), 0.10), 0.98)
