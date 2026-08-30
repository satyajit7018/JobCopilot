"""
JobCopilot - Intelligent Recruiter Follow-Up Engine
Tracks submitted applications and generates concise, polite 7-day and 14-day
follow-up drafts with Anti-AI cliché filtering and value-add project updates.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.core.models import CandidateProfile, JobListing, ApplicationStatus, OutreachRecord, OutreachChannel
from app.core.database import db
from app.core.cover_letter import CoverLetterGenerator


class FollowUpEngine:
    """Automates timely follow-ups for submitted job applications."""

    @classmethod
    def generate_followup_email(
        cls,
        profile: CandidateProfile,
        job: JobListing,
        stage_days: int = 7,
        recipient_name: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generates a concise, polite follow-up email.
        """
        first_name = recipient_name.split()[0] if recipient_name else "there"
        top_project = profile.projects[0] if profile.projects else None

        subject = f"Following up: {job.title} — {profile.full_name}"

        if stage_days <= 8:
            # Stage 1: 7-Day Gentle Check-in
            s1 = f"Hi {first_name}, I hope your week is going well."
            s2 = f"I am checking in regarding my application submitted last week for the {job.title} position at {job.company}."
            s3 = f"I remain very interested in contributing to your team's engineering roadmap and would welcome the chance to answer any preliminary questions."
        else:
            # Stage 2: 14-Day Value-Add Follow-up
            s1 = f"Hi {first_name}, following up on my application for the {job.title} role at {job.company}."
            if top_project:
                s2 = f"Since applying, I released an update to {top_project.name} ({top_project.metrics or 'performance optimizations'}), which aligns closely with your tech stack."
            else:
                s2 = f"I wanted to reiterate my strong interest in joining your backend engineering team."
            s3 = f"Please let me know if there are any updates or additional details I can provide."

        body = f"{s1}\n\n{s2} {s3}\n\nBest regards,\n{profile.full_name}\n{profile.email} | {profile.phone}"

        return {
            "subject": subject,
            "body": CoverLetterGenerator.sanitize_anti_ai(body),
            "stage_days": stage_days
        }

    @classmethod
    def find_pending_followup_jobs(cls, user_id: str = "", days_threshold: int = 7) -> List[JobListing]:
        """Identifies applications submitted >= days_threshold with no recruiter response for user."""
        jobs = db.get_jobs(user_id=user_id)
        pending = []
        now = datetime.now()

        for job in jobs:
            # Check submitted / in-progress applications
            if job.status in [ApplicationStatus.SUBMITTED, ApplicationStatus.IN_PROGRESS]:
                if job.applied_at:
                    try:
                        applied_date = datetime.fromisoformat(job.applied_at)
                        if (now - applied_date).days >= days_threshold:
                            pending.append(job)
                    except Exception:
                        pass
        return pending

    @classmethod
    def generate_and_save_followup(
        cls,
        profile: CandidateProfile,
        job_id: str,
        stage_days: int = 7,
        recipient_email: Optional[str] = None,
        user_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Generates a follow-up draft and persists it to SQLite outreach_records."""
        target_user = user_id or profile.user_id
        job = db.get_job_by_id(job_id=job_id, user_id=target_user)
        if not job:
            return None

        email_data = cls.generate_followup_email(profile, job, stage_days=stage_days)
        record = OutreachRecord(
            outreach_id=f"out_fu_{uuid.uuid4().hex[:8]}",
            user_id=target_user,
            job_id=job.job_id,
            channel=OutreachChannel.COLD_EMAIL,
            recipient_name=job.company + " Recruiting",
            recipient_contact=recipient_email,
            message_content=f"Subject: {email_data['subject']}\n\n{email_data['body']}",
            status="DRAFT"
        )
        db.save_outreach_record(record, user_id=target_user)

        return {
            "outreach_id": record.outreach_id,
            "job_id": job.job_id,
            "company": job.company,
            "subject": email_data["subject"],
            "body": email_data["body"]
        }
