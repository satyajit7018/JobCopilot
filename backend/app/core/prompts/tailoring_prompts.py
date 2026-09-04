"""
JobCopilot - Resume Tailoring Prompts (v1.0)
Versioned templates for aligning candidate bullets with target Job Descriptions.
"""

from typing import List


class TailoringPrompts:
    VERSION = "1.0.0"

    SYSTEM_PROMPT = (
        "You are an elite Staff Software Engineer and ATS optimization expert. "
        "Your task is to rephrase engineering resume bullet points to naturally highlight target "
        "technologies and keywords from the job description while strictly preserving facts and metrics. "
        "Never invent fake metrics or hallucinate non-existent experience. Output concise bullet points."
    )

    @classmethod
    def build_bullet_optimization_prompt(
        cls,
        candidate_bullets: List[str],
        job_title: str,
        company_name: str,
        target_skills: List[str],
        job_description: str = ""
    ) -> str:
        skills_str = ", ".join(target_skills) if target_skills else "relevant modern backend engineering tools"
        bullets_text = "\n".join(f"- {b}" for b in candidate_bullets)
        jd_excerpt = job_description[:500] if job_description else "Focus on scale, reliability, and modern software architectures."

        return (
            f"Target Role: {job_title} at {company_name}\n"
            f"Required Core Technologies: {skills_str}\n"
            f"Job Description Excerpt:\n{jd_excerpt}\n\n"
            f"Candidate Work Experience Bullets:\n{bullets_text}\n\n"
            f"Instructions:\n"
            f"1. Rewrite each bullet point so that relevant target technologies ({skills_str}) are front-loaded.\n"
            f"2. Retain all quantitative impact numbers (latency, throughput, cost reductions, team sizes).\n"
            f"3. Return exactly the same number of bullets, each starting with '- '.\n"
            f"4. Do not add introductory or concluding text."
        )
