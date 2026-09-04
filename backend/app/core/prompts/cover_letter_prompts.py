"""
JobCopilot - Cover Letter Prompts (v1.0)
Versioned templates for anti-AI, engineering-focused cover letters.
"""

from typing import List, Optional


class CoverLetterPrompts:
    VERSION = "1.0.0"

    SYSTEM_PROMPT = (
        "You are an expert technical resume and cover letter writer. "
        "Write in an active, direct engineering voice with zero AI marketing clichés. "
        "Never use banned buzzwords (delve, tapestry, beacon, thrilled to apply, esteemed company, synergy). "
        "Output plain text only with exactly 3 focused paragraphs."
    )

    @classmethod
    def build_cover_letter_prompt(
        cls,
        candidate_name: str,
        role_title: str,
        company_name: str,
        skills: List[str],
        top_project_summary: Optional[str] = None,
        job_description: str = ""
    ) -> str:
        proj_part = f"Featured Project: {top_project_summary}\n" if top_project_summary else ""
        jd_part = f"Job Description Excerpt: {job_description[:300]}\n" if job_description else ""
        skills_str = ", ".join(skills[:6]) if skills else "Python, FastAPI, and distributed systems"

        return (
            f"Candidate: {candidate_name}\n"
            f"Target Role: {role_title} at {company_name}\n"
            f"Core Competencies: {skills_str}\n"
            f"{proj_part}"
            f"{jd_part}\n"
            f"Draft a concise 3-paragraph engineering cover letter:\n"
            f"- Paragraph 1: Direct hook on what was built and why this company's scale/stack is compelling.\n"
            f"- Paragraph 2: Concrete technical proof referencing high throughput, sub-50ms latency, or test quality.\n"
            f"- Paragraph 3: Direct call-to-action for interviews, including links to code samples.\n"
            f"Output plain text only."
        )
