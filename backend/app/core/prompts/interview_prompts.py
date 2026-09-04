"""
JobCopilot - Interview Studio Prompts (v1.0)
Versioned templates for STAR interview response evaluation and company briefings.
"""

from typing import Dict, Any, List


class InterviewPrompts:
    VERSION = "1.0.0"

    STAR_SYSTEM_PROMPT = (
        "You are an executive Bar Raiser and Principal Engineering Interviewer. "
        "Evaluate the candidate's response using the STAR methodology (Situation, Task, Action, Result). "
        "Return your evaluation strictly as valid JSON with keys: "
        "'overall_score' (int 0-100), 'dimension_scores' (object with situation, task, action, result 0-25), "
        "'strengths' (list of strings), 'improvement_areas' (list of strings), and 'verdict' ('STRONG_HIRE', 'HIRE', 'LEAN_HIRE', 'NO_HIRE')."
    )

    DOSSIER_SYSTEM_PROMPT = (
        "You are a Principal Tech Lead and Career Architect. "
        "Provide a high-signal engineering briefing on a company's technology stack, architecture patterns, "
        "and cultural bar for an incoming senior candidate. Return concise, high-density facts."
    )

    @classmethod
    def build_star_evaluation_prompt(
        cls,
        question: str,
        candidate_answer: str,
        role_title: str,
        company_name: str
    ) -> str:
        return (
            f"Company: {company_name}\n"
            f"Role: {role_title}\n"
            f"Interview Question: {question}\n\n"
            f"Candidate Response:\n{candidate_answer}\n\n"
            f"Evaluate the clarity of the situation, the specificity of their individual technical actions, "
            f"and the quantification of their measurable business or technical results. Output JSON only."
        )

    @classmethod
    def build_company_dossier_prompt(
        cls,
        company_name: str,
        role_title: str
    ) -> str:
        return (
            f"Generate a strategic engineering dossier for interviewing at {company_name} for the role of {role_title}.\n"
            f"Include:\n"
            f"1. Known architectural stack and distributed systems challenges\n"
            f"2. Core interview evaluation pillars (e.g. system design, concurrency, coding bar)\n"
            f"3. 3 specific technical discussion topics to demonstrate insider domain knowledge.\n"
            f"Output in concise structured bullet points."
        )
