"""
JobCopilot - Human-Tone Cover Letter Generator
Produces role-specific, 3-paragraph engineering cover letters with
strict Anti-AI cliché filtering and direct, active technical voice.
"""

import re
from typing import List, Dict, Optional
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
        # 1. Select top matching project
        top_project = profile.projects[0] if profile.projects else None
        proj_highlight = ""
        if top_project:
            tech_str = ", ".join(top_project.technologies[:3]) if top_project.technologies else "Python"
            metric_str = f" with {top_project.metrics}" if top_project.metrics else ""
            proj_highlight = f"Recently, I built {top_project.name} using {tech_str}{metric_str} ({top_project.description.rstrip('.')})."

        # 2. Extract top skills
        skills_str = ", ".join(profile.skills[:4]) if profile.skills else "Python, FastAPI, and distributed systems"

        # Paragraph 1: Direct Hook & Specific Alignment
        p1 = f"I am writing to apply for the {job_title} role at {company_name}. With hands-on experience building backend services and AI systems using {skills_str}, I am drawn to {company_name}'s focus on engineering high-scale, reliable software."

        # Paragraph 2: Concrete Technical Proof
        if proj_highlight:
            p2 = f"{proj_highlight} I focus on writing clean, tested, and maintainable code with sub-50ms latency SLAs and solid automated test coverage."
        else:
            p2 = f"In my work, I focus on architecting robust backend APIs and high-throughput pipelines, prioritizing system reliability and performance."

        # Paragraph 3: Direct Call-to-Action
        links = []
        if profile.github_url: links.append(f"GitHub: {profile.github_url}")
        if profile.portfolio_url: links.append(f"Portfolio: {profile.portfolio_url}")
        link_str = f" Code samples and project documentation are available at {', '.join(links)}." if links else ""

        p3 = f"I am available to start immediately and look forward to discussing how my background fits your team's technical roadmap.{link_str}\n\nBest regards,\n{profile.full_name}\n{profile.email} | {profile.phone}"

        full_letter = f"{p1}\n\n{p2}\n\n{p3}"
        return cls.sanitize_anti_ai(full_letter)
