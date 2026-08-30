"""
JobCopilot - Triple-Threat Outreach Generator
Generates multi-channel outreach packages: ATS application package,
280-character LinkedIn InMail connection notes, and 3-sentence cold emails.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from app.core.models import CandidateProfile, OutreachRecord, OutreachChannel
from app.core.database import db
from app.core.cover_letter import CoverLetterGenerator


class OutreachGenerator:
    """Drafts targeted multi-channel outreach across LinkedIn and Cold Email."""

    @classmethod
    def generate_linkedin_inmail_note(
        cls,
        profile: CandidateProfile,
        company_name: str,
        job_title: str,
        hiring_manager_name: str = "Hiring Manager"
    ) -> str:
        """
        Generates a concise, high-converting 280-character LinkedIn connection note.
        """
        top_skill = profile.skills[0] if profile.skills else "Python"
        top_project = profile.projects[0].name if profile.projects else "AI systems"

        # Direct, human tone under 280 chars
        first_name = hiring_manager_name.split()[0] if hiring_manager_name else "there"
        note = f"Hi {first_name}, I applied to {company_name}'s {job_title} role. Having built {top_project} using {top_skill}, I'm excited about {company_name}'s engineering. Would love to connect and follow your team's work!"

        # Enforce LinkedIn 280 character limit
        if len(note) > 280:
            note = f"Hi {first_name}, I applied for {company_name}'s {job_title} role. With experience in {top_skill} and backend systems, I'd love to connect and share relevant project work!"

        return CoverLetterGenerator.sanitize_anti_ai(note)

    @classmethod
    def generate_cold_email_to_lead(
        cls,
        profile: CandidateProfile,
        company_name: str,
        job_title: str,
        lead_name: str = "Engineering Lead"
    ) -> Dict[str, str]:
        """
        Generates a concise 3-sentence cold email to the engineering manager or founder.
        """
        first_name = lead_name.split()[0] if lead_name else "there"
        top_project = profile.projects[0] if profile.projects else None

        subject = f"{job_title} candidate — {profile.full_name}"

        # Sentence 1: Direct application context
        s1 = f"Hi {first_name}, I just applied for the {job_title} position at {company_name}."

        # Sentence 2: Technical proof point
        if top_project:
            tech = ", ".join(top_project.technologies[:2]) if top_project.technologies else "Python"
            metric = f" ({top_project.metrics})" if top_project.metrics else ""
            link = f" (code: {profile.github_url})" if profile.github_url else ""
            s2 = f"Given your technical focus, you might find my work building {top_project.name} in {tech}{metric}{link} directly relevant."
        else:
            s2 = f"I specialize in building scalable Python backend microservices and reliable data pipelines with high test coverage."

        # Sentence 3: Frictionless call to action
        s3 = f"If my background aligns with what your team needs, I would be glad to share my code walkthrough."

        body = f"{s1} {s2} {s3}\n\nBest,\n{profile.full_name}\n{profile.email} | {profile.phone}\n{profile.linkedin_url or ''}"

        return {
            "subject": subject,
            "body": CoverLetterGenerator.sanitize_anti_ai(body)
        }

    @classmethod
    def create_triple_threat_package(
        cls,
        profile: CandidateProfile,
        job_id: str,
        company_name: str,
        job_title: str,
        manager_name: Optional[str] = "Hiring Manager",
        manager_contact: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates and stores the complete Triple-Threat outreach package in SQLite.
        """
        # 1. LinkedIn InMail Note
        li_content = cls.generate_linkedin_inmail_note(profile, company_name, job_title, manager_name)
        li_record = OutreachRecord(
            outreach_id=f"out_li_{uuid.uuid4().hex[:8]}",
            job_id=job_id,
            channel=OutreachChannel.LINKEDIN_INMAIL,
            recipient_name=manager_name,
            recipient_contact=manager_contact,
            message_content=li_content,
            status="DRAFT"
        )
        db.save_outreach_record(li_record)

        # 2. Direct Cold Email
        email_data = cls.generate_cold_email_to_lead(profile, company_name, job_title, manager_name)
        email_record = OutreachRecord(
            outreach_id=f"out_em_{uuid.uuid4().hex[:8]}",
            job_id=job_id,
            channel=OutreachChannel.COLD_EMAIL,
            recipient_name=manager_name,
            recipient_contact=manager_contact,
            message_content=f"Subject: {email_data['subject']}\n\n{email_data['body']}",
            status="DRAFT"
        )
        db.save_outreach_record(email_record)

        return {
            "job_id": job_id,
            "linkedin_note": li_content,
            "cold_email": email_data,
            "records": [li_record.dict(), email_record.dict()]
        }

    @classmethod
    def generate_alumni_referral_pitch(
        cls,
        candidate_name: str,
        company_name: str,
        role_title: str,
        contact_name: str = "Fellow Alumni",
        common_ground: str = "our shared university background"
    ) -> Dict[str, str]:
        """Generates tailored 280-char LinkedIn connection note and email for alumni referral requests."""
        first_name = contact_name.split()[0] if contact_name else "there"

        li_note = (
            f"Hi {first_name}! Noticed we both share {common_ground}. I'm applying for {company_name}'s {role_title} role and admire your team's work. "
            f"Would you be open to connecting or sharing 5 mins of advice on engineering culture?"
        )
        if len(li_note) > 280:
            li_note = f"Hi {first_name}! Shared {common_ground} connection here. I'm applying for {company_name}'s {role_title} role. Would love to connect and follow your work!"

        email_subject = f"{common_ground} connection — Quick question regarding {company_name}"
        email_body = (
            f"Hi {first_name},\n\n"
            f"I hope you're having a great week! I came across your profile and noticed {common_ground}.\n\n"
            f"I recently applied for the {role_title} position at {company_name}. Given your experience on the team, I would greatly appreciate any quick insights on the engineering culture or if you'd be open to submitting an internal employee referral.\n\n"
            f"Either way, thank you for your time and continued great work at {company_name}!\n\n"
            f"Best regards,\n{candidate_name}"
        )

        return {
            "linkedin_note_280": CoverLetterGenerator.sanitize_anti_ai(li_note),
            "email_subject": email_subject,
            "email_body": CoverLetterGenerator.sanitize_anti_ai(email_body)
        }

    @classmethod
    def generate_recruiter_followup_nudge(
        cls,
        candidate_name: str,
        company_name: str,
        role_title: str,
        recruiter_name: str = "Recruiter",
        days_elapsed: int = 5,
        recent_highlight: Optional[str] = None
    ) -> Dict[str, str]:
        """Generates polite, high-converting 3-sentence recruiter bump message after application cooling period."""
        first_name = recruiter_name.split()[0] if recruiter_name else "there"
        highlight = recent_highlight or "recently published a new open-source distributed systems walkthrough"

        subject = f"Following up: {role_title} application — {candidate_name}"
        body = (
            f"Hi {first_name},\n\n"
            f"I hope you're having a productive week! I wanted to briefly follow up on my application submitted {days_elapsed} business days ago for the {role_title} role at {company_name}.\n\n"
            f"I remain extremely enthusiastic about contributing to {company_name}'s technical mission, and {highlight} that directly aligns with your team's stack.\n\n"
            f"Please let me know if there are any additional project demos or references I can provide to assist in your review.\n\n"
            f"Best regards,\n{candidate_name}"
        )

        return {
            "subject": subject,
            "body": CoverLetterGenerator.sanitize_anti_ai(body)
        }
