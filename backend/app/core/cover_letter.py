"""
JobCopilot - Human-Tone Cover Letter Generator
Produces role-specific, 3-paragraph engineering cover letters with
strict Anti-AI cliché filtering and direct, active technical voice.
"""

import re

from app.core.models import CandidateProfile


class CoverLetterGenerator:
    """Generates authentic, zero-AI-cliché engineering cover letters."""

    FORBIDDEN_AI_CLICHES = [
        "delve", "tapestry", "testament", "beacon", "pleased to apply",
        "esteemed organization", "passionate", "uniquely positioned",
        "dynamic landscape", "harnessing the power", "seamlessly",
        "groundbreaking", "esteemed company", "thrilled to apply",
        "fervent", "synergy", "paradigm", "in today's fast-paced world"
    ]

    @classmethod
    def sanitize_anti_ai(cls, text: str) -> str:
        """Strips generic AI marketing clichés and replaces them with active voice."""
        cleaned = text
        replacements = {
            r'\bdelve into\b': 'focus on',
            r'\bpleased to apply for\b': 'applying for',
            r'\bthrilled to apply for\b': 'applying for',
            r'\besteemed organization\b': 'team',
            r'\besteemed company\b': 'team',
            r'\buniquely positioned to\b': 'prepared to',
            r'\bpassionate about\b': 'experienced in',
            r'\bharnessing the power of\b': 'using',
            r'\bseamlessly\b': 'directly',
            r'\bgroundbreaking\b': 'impactful',
            r'\bdynamic landscape\b': 'industry',
            r'\ba testament to\b': 'evidence of'
        }
        for pattern, repl in replacements.items():
            cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
        return cleaned

    @classmethod
    def has_banned_cliches(cls, text: str) -> bool:
        """Checks if any forbidden AI cliché exists in text."""
        text_lower = text.lower()
        return any(re.search(r'\b' + re.escape(c) + r'\b', text_lower) for c in cls.FORBIDDEN_AI_CLICHES)

    @classmethod
    def generate_cover_letter(
        cls,
        profile: CandidateProfile,
        company_name: str,
        job_title: str,
        job_description: str = "",
        domain: str = "Technology"
    ) -> str:
        """
        Generates a concise, 3-paragraph cover letter tailored to the role.
        """
        # Only facts from the profile: no invented experience, results or availability.
        top_project = profile.projects[0] if profile.projects else None
        latest = profile.experience[0] if profile.experience else None
        skills_str = ", ".join(profile.skills[:4])

        # Paragraph 1: the role, and who is applying
        p1 = f"I am writing to apply for the {job_title} role at {company_name}."
        if latest and latest.title and latest.company:
            p1 += f" I am currently {'an' if latest.title[:1].lower() in 'aeiou' else 'a'} {latest.title} at {latest.company}" if (latest.end_date or "").lower() == "present" else f" Most recently I was {'an' if latest.title[:1].lower() in 'aeiou' else 'a'} {latest.title} at {latest.company}"
            p1 += f", working with {skills_str}." if skills_str else "."
        elif skills_str:
            p1 += f" I work with {skills_str}."

        # Paragraph 2: one concrete example, taken from the resume
        p2 = ""
        if top_project:
            tech_str = f" using {', '.join(top_project.technologies[:3])}" if top_project.technologies else ""
            metric_str = f" ({top_project.metrics})" if top_project.metrics else ""
            desc = f": {top_project.description.rstrip('.')}" if top_project.description else ""
            p2 = f"One example of my work is {top_project.name}{tech_str}{metric_str}{desc}."
        elif latest and latest.highlights:
            p2 = f"In my current work, I {latest.highlights[0][0].lower()}{latest.highlights[0][1:].rstrip('.')}."

        # Paragraph 3: availability (from the notice period) and links
        links = []
        if profile.github_url: links.append(f"GitHub: {profile.github_url}")
        if profile.portfolio_url: links.append(f"Portfolio: {profile.portfolio_url}")
        link_str = f" You can see my work at {', '.join(links)}." if links else ""
        notice = profile.preferences.notice_period_days if profile.preferences else 0
        start = "I can start immediately" if not notice else f"I can start after my {notice}-day notice period"

        p3 = f"{start} and would welcome the chance to discuss how my background fits your team.{link_str}\n\nBest regards,\n{profile.full_name}\n{profile.email} | {profile.phone}"

        full_letter = "\n\n".join(p for p in (p1, p2, p3) if p)
        return cls.sanitize_anti_ai(full_letter)

    @classmethod
    async def generate_cover_letter_async(
        cls,
        profile: CandidateProfile,
        company_name: str,
        job_title: str,
        job_description: str = "",
        domain: str = "Technology"
    ) -> str:
        """Generates cover letter via configured LLM with automatic deterministic fallback."""
        from app.core.llm_client import llm_client
        from app.core.prompts.cover_letter_prompts import CoverLetterPrompts

        fallback = lambda: cls.generate_cover_letter(profile, company_name, job_title, job_description, domain)
        top_proj = (
            f"{profile.projects[0].name}" + (f" ({profile.projects[0].metrics})" if profile.projects[0].metrics else "")
            if profile.projects else None
        )
        prompt = CoverLetterPrompts.build_cover_letter_prompt(
            candidate_name=profile.full_name,
            role_title=job_title,
            company_name=company_name,
            skills=profile.skills,
            top_project_summary=top_proj,
            job_description=job_description
        )
        raw_text = await llm_client.generate_completion(
            prompt=prompt,
            system_prompt=CoverLetterPrompts.SYSTEM_PROMPT,
            fallback_fn=fallback
        )
        return cls.sanitize_anti_ai(raw_text)
