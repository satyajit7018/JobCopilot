"""
JobCopilot - Multi-Factor Resume-to-Job Match Scorer
Computes multi-dimensional alignment: Technical Skills (40%), Title Relevance (30%),
Experience Years (15%), and Location/Remote Compatibility (15%).
"""

import re
from typing import List, Dict, Tuple, Optional
from app.core.models import CandidateProfile


class MatchScorer:
    """Multi-factor candidate-to-job matching engine."""

    SENIORITY_YOE_MAP = {
        "intern": (0.0, 1.0),
        "junior": (0.0, 2.0),
        "entry": (0.0, 2.0),
        "mid": (2.0, 5.0),
        "senior": (4.0, 9.0),
        "lead": (5.0, 12.0),
        "staff": (7.0, 15.0),
        "principal": (10.0, 20.0),
        "director": (10.0, 25.0)
    }

    @classmethod
    def extract_job_required_skills(cls, job_text: str) -> List[str]:
        """Extracts technical skills required from job description."""
        from app.core.resume_parser import ResumeParser
        all_skills, _ = ResumeParser.categorize_skills(job_text)
        return all_skills

    @classmethod
    def infer_job_seniority(cls, title: str, description: str) -> str:
        """Infers job seniority level from title and description text."""
        combined = (title + " " + description[:300]).lower()
        if "intern" in combined:
            return "Intern"
        if "staff" in combined:
            return "Staff"
        if "principal" in combined:
            return "Principal"
        if "lead" in combined:
            return "Lead"
        if "senior" in combined or "sr." in combined:
            return "Senior"
        if "junior" in combined or "jr." in combined or "entry" in combined or "graduate" in combined:
            return "Junior"
        return "Mid-Level"

    @classmethod
    def compute_match_score(
        cls,
        profile: CandidateProfile,
        job_title: str,
        job_description: str,
        job_location: str = "Remote"
    ) -> Tuple[float, List[str], List[str]]:
        """
        Computes weighted match score (0.0 to 1.0) along with positive match reasons
        and missing required skills.
        """
        text = (job_title + " " + job_description).lower()
        candidate_skills = profile.skills
        candidate_skills_lower = {s.lower(): s for s in candidate_skills}

        match_reasons: List[str] = []
        missing_skills: List[str] = []

        # 1. Technical Skill Overlap (40% weight)
        job_skills = cls.extract_job_required_skills(job_description)
        if not job_skills:
            job_skills = [s for s in candidate_skills if re.search(r'\b' + re.escape(s.lower()) + r'\b', text)]

        matched_skills = []
        for js in job_skills:
            if js.lower() in candidate_skills_lower:
                matched_skills.append(candidate_skills_lower[js.lower()])
            else:
                missing_skills.append(js)

        if job_skills:
            skill_ratio = len(matched_skills) / len(job_skills)
            skill_score = min(skill_ratio, 1.0) * 0.40
        else:
            skill_score = 0.0

        if matched_skills:
            match_reasons.append(f"Strong skill match: {', '.join(matched_skills[:4])}")

        # 2. Title Alignment (30% weight)
        title_clean = job_title.lower()
        title_score = 0.0
        profile_skills_lower = list(candidate_skills_lower.keys())
        is_engineer = any(w in title_clean for w in ["engineer", "developer", "architect", "programmer", "specialist", "scientist"])

        if is_engineer:
            title_score = 0.15
            if any(k in title_clean for k in ["ai", "machine learning", "ml", "computer vision", "nlp"]):
                if any(s in profile_skills_lower for s in ["pytorch", "tensorflow", "machine learning", "fastapi"]):
                    title_score = 0.30
                    match_reasons.append("Role aligns directly with your AI / ML specialization.")
            elif "backend" in title_clean and any(s in profile_skills_lower for s in ["python", "fastapi", "django", "postgresql"]):
                title_score = 0.30
                match_reasons.append("Role aligns with your Backend engineering stack.")
            elif "full stack" in title_clean or "fullstack" in title_clean:
                title_score = 0.28
                match_reasons.append("Matches your Full Stack development background.")

        # 3. Experience Level Alignment (15% weight)
        seniority = cls.infer_job_seniority(job_title, job_description)
        yoe = profile.preferences.years_of_experience
        min_yoe, max_yoe = cls.SENIORITY_YOE_MAP.get(seniority.lower(), (1.0, 6.0))

        if is_engineer:
            if min_yoe <= yoe <= max_yoe + 1.0:
                exp_score = 0.15
                match_reasons.append(f"Experience level ({yoe:.1f} yrs) fits {seniority} requirements.")
            elif yoe < min_yoe:
                exp_score = max(0.02, 0.15 - (min_yoe - yoe) * 0.05)
            else:
                exp_score = 0.10
        else:
            exp_score = 0.0

        # 4. Location & Remote Compatibility (15% weight)
        loc_clean = job_location.lower()
        remote_pref = profile.preferences.remote_preference.lower()
        candidate_loc = profile.location.lower()

        if is_engineer:
            if "remote" in loc_clean or "remote" in remote_pref:
                loc_score = 0.15
                match_reasons.append("Matches your Remote / Hybrid work preference.")
            elif any(c in loc_clean for c in ["india", "bangalore", "bengaluru", "hyderabad"]) and "india" in candidate_loc:
                loc_score = 0.15
                match_reasons.append("Local geographic match.")
            else:
                loc_score = 0.08 if profile.preferences.willing_to_relocate else 0.02
        else:
            loc_score = 0.0

        # Aggregate total score
        total_score = skill_score + title_score + exp_score + loc_score
        final_clamped = min(max(round(total_score, 2), 0.05), 0.99)

        return final_clamped, match_reasons, missing_skills[:6]

    @classmethod
    def compute_match_score_semantic(
        cls,
        profile: CandidateProfile,
        job_title: str,
        job_description: str,
        job_location: str = "Remote"
    ) -> Tuple[float, List[str], List[str]]:
        """
        Computes multi-factor match score enhanced with dense semantic vector similarity:
        - 40% Semantic Vector Alignment (deep conceptual match between profile narrative and job requirements)
        - 60% Rule-Based Multidimensional Factors (skills, title, experience, location)
        """
        from app.core.llm_client import llm_client

        base_score, match_reasons, missing_skills = cls.compute_match_score(
            profile, job_title, job_description, job_location
        )

        profile_text = (
            f"{profile.summary} "
            f"Skills: {', '.join(profile.skills[:15])}. "
            f"Experience: {' '.join(h for exp in profile.experience for h in exp.highlights[:2])}"
        ).strip()
        job_text = f"{job_title}. Description: {job_description[:2000]}".strip()

        try:
            p_vec = llm_client.embed_text_sync(profile_text)
            j_vec = llm_client.embed_text_sync(job_text)
            semantic_sim = llm_client.cosine_similarity(p_vec, j_vec)
            normalized_sim = max(0.0, min(1.0, (semantic_sim + 1.0) / 2.0 if semantic_sim < 0 else semantic_sim))
        except Exception:
            normalized_sim = base_score

        blended_score = (normalized_sim * 0.40) + (base_score * 0.60)
        final_score = min(max(round(blended_score, 2), 0.05), 0.99)

        if normalized_sim >= 0.65:
            match_reasons.insert(0, f"High semantic vector alignment ({int(normalized_sim * 100)}% conceptual fit)")

        return final_score, match_reasons, missing_skills
