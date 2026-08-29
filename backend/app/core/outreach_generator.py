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
