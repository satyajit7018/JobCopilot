"""
JobCopilot - 2-Way Email State Synchronization Engine
Correlates incoming recruiter communications with tracked job applications,
updates pipeline status automatically, and persists sanitized records to SQLite.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

from app.core.models import EmailMessage, EmailIntent, ApplicationStatus, JobListing
from app.core.database import db
from app.email.parser import EmailParser
from app.email.classifier import EmailClassifier

logger = logging.getLogger(__name__)


class EmailSyncEngine:
    """Synchronizes parsed email communications with the job tracking pipeline."""

    @classmethod
    def find_associated_job(cls, sender: str, subject: str, body_text: str, user_id: str = "") -> Optional[JobListing]:
        """Finds matching job in database for the specified user."""
        jobs = db.get_jobs(user_id=user_id)
        if not jobs:
            return None

        sender_low = sender.lower()
        subject_low = subject.lower()
        body_low = body_text.lower()

        # 1. Exact Company Name match
        for job in jobs:
            comp_norm = job.company.lower().strip()
            if not comp_norm:
                continue

            # Check sender domain (e.g. @stripe.com -> stripe)
            sender_domain = sender_low.split('@')[-1] if '@' in sender_low else ""
            if comp_norm in sender_domain:
                return job

            # Check subject & body mentions
            if comp_norm in subject_low or (comp_norm in body_low and job.title.lower() in body_low):
                return job

        return None

    @classmethod
    async def process_inbound_email(
        cls,
        sender: str,
        recipient: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        user_id: str = "",
        ws_broadcast_callback = None
    ) -> Dict[str, Any]:
        """
        Full inbound processing pipeline:
        1. Strips tracking pixels & sanitizes HTML
        2. Classifies recruiter intent & extracts booking URLs
        3. Correlates with active JobListing for the user
        4. Updates job status and saves EmailMessage record
        """
        # 1. Sanitize & Parse
        parsed = EmailParser.parse_raw_email(sender, recipient, subject, body_html, body_text)
        clean_text = parsed["body_text"]

        # 2. Classify Intent & Extract Links
        intent, confidence = EmailClassifier.classify_intent(subject, clean_text)
        scheduling_links = EmailClassifier.extract_scheduling_links(clean_text)

        # 3. Correlate with Job
        associated_job = cls.find_associated_job(sender, subject, clean_text, user_id=user_id)
        associated_job_id = associated_job.job_id if associated_job else None

        # 4. Update Pipeline Status
        updated_status = None
        if associated_job:
            if intent == EmailIntent.INTERVIEW_INVITE:
                associated_job.status = ApplicationStatus.INTERVIEW
                updated_status = "INTERVIEW"
            elif intent == EmailIntent.ASSESSMENT:
                associated_job.status = ApplicationStatus.RESPONDED
                updated_status = "RESPONDED"
            elif intent == EmailIntent.REJECTION:
                associated_job.status = ApplicationStatus.REJECTED
                updated_status = "REJECTED"
            elif intent == EmailIntent.CONFIRMATION:
                associated_job.status = ApplicationStatus.SUBMITTED
                updated_status = "SUBMITTED"
            
            db.save_job(associated_job, user_id=user_id or associated_job.user_id)

        # 5. Persist Email Record to SQLite
        email_record = EmailMessage(
            message_id=f"msg_{uuid.uuid4().hex[:10]}",
            user_id=user_id,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body_text=clean_text,
            received_at=datetime.now().isoformat(),
            associated_job_id=associated_job_id,
            intent=intent,
            scheduling_links=scheduling_links,
            has_tracking_pixels=parsed["has_tracking_pixels"],
            processed=True
        )
        db.save_email(email_record, user_id=user_id)

        # 6. WebSocket Notification
        if ws_broadcast_callback:
            try:
                await ws_broadcast_callback({
                    "type": "EMAIL_RECEIVED",
                    "intent": intent.value,
                    "company": associated_job.company if associated_job else sender,
                    "role_title": associated_job.title if associated_job else "Software Engineer",
                    "job_id": associated_job_id,
                    "subject": subject,
                    "scheduling_links": scheduling_links,
                    "updated_status": updated_status
                })
            except Exception as e:
                logger.debug(f"WebSocket broadcast error in EmailSyncEngine: {e}")

        return {
            "status": "success",
            "message_id": email_record.message_id,
            "intent": intent.value,
            "associated_job_id": associated_job_id,
            "updated_pipeline_status": updated_status,
            "scheduling_links": scheduling_links,
            "has_tracking_pixels": parsed["has_tracking_pixels"]
        }
