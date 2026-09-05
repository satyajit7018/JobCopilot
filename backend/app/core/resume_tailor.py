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
    def tailor_for_job(
        cls,
        profile: CandidateProfile,
        job_title: str,
        job_description: str,
        strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convenience method returning tailored skills and project names."""
        tailored, matched = cls.tailor_profile_for_job(profile, job_title, job_description, strategy=strategy)
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
        job_description: str,
        strategy: Optional[str] = None
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

        # 4. Reorder Work Experience Highlights (incorporating A/B testing strategy)
        for exp in tailored.experience:
            def highlight_relevance(h: str) -> int:
                relevance = sum(1 for s in jd_skills_lower if s in h.lower())
                if strategy in ("treatment_star", "variant_b"):
                    has_metric = 1 if any(w in h.lower() for w in ["%", "$", "reduced", "scaled", "improved", "optimized", "increased", "latency"]) else 0
                    relevance += has_metric * 2
                return relevance
            exp.highlights.sort(key=highlight_relevance, reverse=True)

        return tailored, matched_skills

    @classmethod
    async def tailor_profile_for_job_async(
        cls,
        profile: CandidateProfile,
        job_title: str,
        job_description: str,
        company_name: str = "Target Company"
    ) -> Tuple[CandidateProfile, List[str]]:
        """
        AI-powered profile tailoring: uses LLM to optimize work experience bullets
        against target job description, with automatic deterministic fallback.
        """
        from app.core.llm_client import llm_client
        from app.core.prompts.tailoring_prompts import TailoringPrompts

        # 1. Base deterministic reordering
        tailored, matched_skills = cls.tailor_profile_for_job(profile, job_title, job_description)

        if not tailored.experience or not matched_skills:
            return tailored, matched_skills

        # 2. LLM-optimized bullet refinement
        async def _llm_refine():
            for exp in tailored.experience[:2]:
                if not exp.highlights:
                    continue
                prompt = TailoringPrompts.build_bullet_optimization_prompt(
                    candidate_bullets=exp.highlights[:4],
                    job_title=job_title,
                    company_name=company_name,
                    target_skills=matched_skills[:5],
                    job_description=job_description
                )
                raw = await llm_client.generate_completion(
                    prompt=prompt,
                    system_prompt=TailoringPrompts.SYSTEM_PROMPT,
                    fallback_fn=lambda: "\n".join(f"- {h}" for h in exp.highlights[:4])
                )
                lines = [
                    line.strip().lstrip("-* ").strip()
                    for line in raw.split("\n")
                    if line.strip() and len(line.strip()) > 15
                ]
                if lines and len(lines) == len(exp.highlights[:4]):
                    exp.highlights = lines + exp.highlights[4:]
            return tailored

        try:
            return await _llm_refine(), matched_skills
        except Exception:
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
        tailored_profile, matched_skills = await cls.tailor_profile_for_job_async(
            profile=profile,
            job_title=job_title,
            job_description=job_description,
            company_name=company_name
        )
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
