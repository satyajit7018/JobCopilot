"""
JobCopilot - Smart Recruiter Baseline Questionnaire Engine
Generates the 8 core recruiter questions schema, auto-pre-fills 70%+ from parsed resume,
and applies user confirmed responses back to the candidate profile and Knowledge Vault.
"""

from typing import Dict, Any, List, Optional
from app.core.models import CandidateProfile, RecruiterPreferences, DemographicPreferences
from app.core.compensation import CompensationConverter


class QuestionnaireEngine:
    """Manages the 8 canonical recruiter baseline questions and auto-prefilling."""

    QUESTIONS_SCHEMA = [
        {
            "id": "expected_ctc",
            "question": "What is your expected salary / CTC?",
            "description": "Used by ATS compensation filters. We automatically convert to foreign currencies.",
            "type": "salary_slider",
            "default_value": "15 LPA",
            "options": []
        },
        {
            "id": "current_ctc",
            "question": "What is your current salary / CTC?",
            "description": "Used when required by Indian or enterprise recruiter forms.",
            "type": "text",
            "default_value": "0 LPA",
            "options": []
        },
        {
            "id": "notice_period_days",
            "question": "What is your notice period / earliest available start date?",
            "description": "0 days = Immediate Joiner, 15 days, 30 days, 60 days, 90 days.",
            "type": "select",
            "default_value": 0,
            "options": ["Immediate (0 days)", "15 days", "30 days", "60 days", "90 days"]
        },
        {
            "id": "work_authorization",
            "question": "What is your work authorization status?",
            "description": "Citizen, Permanent Resident, or requires visa sponsorship.",
            "type": "select",
            "default_value": "Citizen",
            "options": [
                "Citizen / Permanent Resident",
                "Require Visa Sponsorship",
                "Authorized to work with existing visa (OPT/CPT/H1B)",
                "Open to contractor / remote work"
            ]
        },
        {
            "id": "willing_to_relocate",
            "question": "Are you open to relocation?",
            "description": "Helps match with hybrid or on-site roles in top tech hubs.",
            "type": "boolean",
            "default_value": True,
            "options": ["Yes, willing to relocate", "No, remote / local only"]
        },
        {
            "id": "remote_preference",
            "question": "What is your preferred work mode?",
            "description": "Remote, Hybrid, or On-site.",
            "type": "select",
            "default_value": "Remote / Hybrid / On-site",
            "options": [
                "Remote Only",
                "Remote / Hybrid",
                "Remote / Hybrid / On-site",
                "On-site Only"
            ]
        },
        {
            "id": "years_of_experience",
            "question": "Total professional years of experience?",
            "description": "Used for seniority filtering and experience gate questions.",
            "type": "number",
            "default_value": 1.0,
            "options": []
        },
        {
            "id": "why_looking_for_role",
            "question": "Why are you looking for a new role? (Career Narrative)",
            "description": "Used as the baseline template for company 'Why should we hire you?' questions.",
            "type": "textarea",
            "default_value": "Seeking high-growth technical opportunities to build high-scale, reliable distributed systems and AI solutions.",
            "options": []
        }
    ]

    @classmethod
    def get_questions_schema(cls) -> List[Dict[str, Any]]:
        """Returns the full questionnaire schema for UI rendering."""
        return cls.QUESTIONS_SCHEMA

    @classmethod
    def prefill_from_profile(cls, profile: CandidateProfile) -> Dict[str, Any]:
        """Auto-pre-fills questionnaire answers from parsed CandidateProfile."""
        prefs = profile.preferences
        yoe = prefs.years_of_experience if prefs.years_of_experience > 0 else 1.0

        # Build clean narrative if empty
        narrative = prefs.why_looking_for_role
        if not narrative:
            top_skills = ", ".join(profile.skills[:4]) if profile.skills else "Software Engineering"
            narrative = f"Experienced in {top_skills}, looking to contribute to ambitious engineering teams building scalable software."

        # Notice period label
        notice_label = f"{prefs.notice_period_days} days" if prefs.notice_period_days > 0 else "Immediate (0 days)"

        # Multi-currency slider equivalents
        salary_equivalents = CompensationConverter.get_salary_slider_equivalents(prefs.expected_ctc)

        return {
            "full_name": profile.full_name,
            "email": profile.email,
            "phone": profile.phone,
            "location": profile.location,
            "linkedin_url": profile.linkedin_url or "",
            "github_url": profile.github_url or "",
            "portfolio_url": profile.portfolio_url or "",
            "skills": profile.skills,
            "expected_ctc": prefs.expected_ctc,
            "expected_ctc_equivalents": salary_equivalents,
            "current_ctc": prefs.current_ctc,
            "notice_period_days": prefs.notice_period_days,
            "notice_period_label": notice_label,
            "work_authorization": prefs.work_authorization,
            "requires_sponsorship": prefs.requires_sponsorship,
            "willing_to_relocate": prefs.willing_to_relocate,
            "remote_preference": prefs.remote_preference,
            "years_of_experience": yoe,
            "why_looking_for_role": narrative,
            "current_employer": prefs.current_employer or ""
        }

    @classmethod
    def apply_answers_to_profile(cls, profile: CandidateProfile, answers: Dict[str, Any]) -> CandidateProfile:
        """Applies user-confirmed questionnaire answers back into CandidateProfile."""
        prefs = profile.preferences

        if "expected_ctc" in answers:
            prefs.expected_ctc = str(answers["expected_ctc"])
        if "current_ctc" in answers:
            prefs.current_ctc = str(answers["current_ctc"])
        if "notice_period_days" in answers:
            # Parse integer from string or int
            val = answers["notice_period_days"]
            if isinstance(val, str):
                digits = "".join(filter(str.isdigit, val))
                prefs.notice_period_days = int(digits) if digits else 0
            else:
                prefs.notice_period_days = int(val)
        if "work_authorization" in answers:
            prefs.work_authorization = str(answers["work_authorization"])
            prefs.requires_sponsorship = "sponsorship" in prefs.work_authorization.lower()
        if "willing_to_relocate" in answers:
            prefs.willing_to_relocate = bool(answers["willing_to_relocate"])
        if "remote_preference" in answers:
            prefs.remote_preference = str(answers["remote_preference"])
        if "years_of_experience" in answers:
            prefs.years_of_experience = float(answers["years_of_experience"])
        if "why_looking_for_role" in answers:
            prefs.why_looking_for_role = str(answers["why_looking_for_role"])
        if "current_employer" in answers:
            prefs.current_employer = str(answers["current_employer"])
            if prefs.current_employer and prefs.current_employer not in prefs.company_blacklist:
                prefs.company_blacklist.append(prefs.current_employer)

        # Update contact info if provided
        if "full_name" in answers and answers["full_name"]:
            profile.full_name = str(answers["full_name"])
        if "email" in answers and answers["email"]:
            profile.email = str(answers["email"])
        if "phone" in answers and answers["phone"]:
            profile.phone = str(answers["phone"])
        if "location" in answers and answers["location"]:
            profile.location = str(answers["location"])
        if "linkedin_url" in answers:
            profile.linkedin_url = str(answers["linkedin_url"])
        if "github_url" in answers:
            profile.github_url = str(answers["github_url"])

        profile.preferences = prefs
        return profile
