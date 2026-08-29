"""
JobCopilot - Dynamic Per-Job Tailored Resume Engine
Analyzes target Job Descriptions and dynamically aligns skill emphasis,
reorders project highlights, and compiles bespoke ATS-compliant PDF resumes.
"""

import re
import copy
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

from app.core.config import RESUMES_DIR
from app.core.models import CandidateProfile, ResumeVariant, CategorizedSkills, Project, WorkExperience
from app.core.match_scorer import MatchScorer
from app.core.resume_compiler import ResumeCompiler


class ResumeTailor:
    """Dynamically aligns candidate profile emphasis with target Job Descriptions."""

    @classmethod
    def tailor_for_job(cls, profile: CandidateProfile, job_title: str, job_description: str) -> Dict[str, Any]:
        """Convenience method returning tailored skills and project names."""
        tailored, matched = cls.tailor_profile_for_job(profile, job_title, job_description)
        return {
            "tailored_skills": tailored.skills,
            "reordered_projects": [p.name for p in tailored.projects],
            "matched_skills": matched
        }

    @classmethod
    def tailor_profile_for_job(
        cls,
        profile: CandidateProfile,
        job_title: str,
        job_description: str
    ) -> Tuple[CandidateProfile, List[str]]:
        """
        Creates a tailored deep-copy of CandidateProfile with reordered skills,
        promoted projects, and optimized highlight order based on JD keywords.
        """
        tailored = copy.deepcopy(profile)
        jd_skills = MatchScorer.extract_job_required_skills(job_title + " " + job_description)
        jd_skills_lower = [s.lower() for s in jd_skills]

        # 1. Identify Core Matched Competencies
        matched_skills = []
        for s in profile.skills:
            if s.lower() in jd_skills_lower:
                matched_skills.append(s)

        # 2. Reorder Categorized Skills (Promote JD-matched skills to front)
        cat = tailored.categorized_skills
        for field in ["languages", "frameworks", "cloud_devops", "databases", "tools_libraries"]:
            current_list = getattr(cat, field, [])
            matched = [s for s in current_list if s.lower() in jd_skills_lower]
            unmatched = [s for s in current_list if s.lower() not in jd_skills_lower]
            setattr(cat, field, matched + unmatched)

        # 3. Reorder Projects (Promote projects containing JD technologies)
        def project_relevance(proj: Project) -> int:
            score = 0
            for tech in proj.technologies:
                if tech.lower() in jd_skills_lower:
                    score += 2
            for word in proj.description.lower().split():
                if word in jd_skills_lower:
                    score += 1
            return score

        tailored.projects.sort(key=project_relevance, reverse=True)

        # 4. Reorder Work Experience Highlights
        for exp in tailored.experience:
            def highlight_relevance(h: str) -> int:
                return sum(1 for s in jd_skills_lower if s in h.lower())
            exp.highlights.sort(key=highlight_relevance, reverse=True)

        return tailored, matched_skills

    @classmethod
    async def compile_tailored_resume_for_job(
        cls,
        profile: CandidateProfile,
        job_id: str,
        job_title: str,
        job_description: str,
        company_name: str
    ) -> Tuple[Path, str, CandidateProfile]:
        """
        Generates and compiles a bespoke, tailored PDF resume for a specific job application.
        Returns (pdf_path, content_hash, tailored_profile).
        """
        tailored_profile, matched_skills = cls.tailor_profile_for_job(profile, job_title, job_description)
        html_content = ResumeCompiler.generate_resume_html(tailored_profile, tailored_skills=matched_skills[:6])

        # Generate unique content hash
        content_hash = hashlib.sha256(html_content.encode('utf-8')).hexdigest()
        
        # Save to RESUMES_DIR
        clean_comp = re.sub(r'\W+', '_', company_name.lower())
        clean_title = re.sub(r'\W+', '_', job_title.lower())
        out_filename = f"Resume_{clean_comp}_{clean_title}_{job_id[:6]}.pdf"
        out_path = RESUMES_DIR / out_filename

        # Compile PDF via Chromium
        await ResumeCompiler.compile_to_pdf(html_content, out_path)

        return out_path, content_hash, tailored_profile
