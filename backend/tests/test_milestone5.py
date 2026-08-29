"""
JobCopilot - Milestone 5 End-to-End Test Suite
Tests Privacy-First Email Parser, 5-Way Recruiter Intent Classifier,
2-Way Pipeline Synchronization, and Intelligent Follow-Up Engine.
"""

import sys
import uuid
from pathlib import Path
import pytest

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.core.models import CandidateProfile, JobListing, ApplicationStatus, EmailIntent, Project
from app.core.database import DatabaseManager
from app.email.parser import EmailParser
from app.email.classifier import EmailClassifier
from app.email.sync import EmailSyncEngine
from app.email.followup import FollowUpEngine


class TestMilestone5:

    @pytest.fixture(autouse=True)
    def setup_isolated_env(self, tmp_path):
        self.db_path = tmp_path / "test_m5.db"
        self.db = DatabaseManager(self.db_path)
        self.profile = CandidateProfile(
            full_name="Satyajit Nayak",
            email="scorpionsatyajit@gmail.com",
            phone="+91 7008053476",
            location="Bangalore, India",
            skills=["Python", "FastAPI", "PyTorch"],
            projects=[Project(name="Medical AI System", description="Diagnostic tool", metrics="96.19% accuracy")]
        )
        self.db.save_profile(self.profile)

    # 1. Test Privacy-First Parser & Tracking Pixel Stripper
    def test_email_parser_pixel_stripping(self):
        raw_html = """
        <div style="font-family: Arial;">
          <p>Hi Satyajit,</p>
          <p>We received your application for the Software Engineer role.</p>
          <p>Click <a href="https://calendly.com/techcorp/chat">here to schedule</a>.</p>
          <img src="https://mandrillapp.com/track/open.php?u=123" width="1" height="1" style="display:none;" />
        </div>
        """
        parsed = EmailParser.parse_raw_email(
            sender="jobs@techcorp.io",
            recipient="scorpionsatyajit@gmail.com",
            subject="Interview with TechCorp",
            body_html=raw_html
        )
        assert parsed["has_tracking_pixels"] is True
        assert "mandrillapp.com" not in parsed["body_text"]
        assert "calendly.com/techcorp/chat" in parsed["body_text"]
        assert "Software Engineer" in parsed["body_text"]

    # 2. Test 5-Way Intent Classification & Scheduling Links
    def test_intent_classification(self):
        # Interview
        sub_iv = "Invitation to Interview: AI Engineer"
        body_iv = "Please book a 30-minute chat: https://calendly.com/company/30min"
        intent_iv, _ = EmailClassifier.classify_intent(sub_iv, body_iv)
        assert intent_iv == EmailIntent.INTERVIEW_INVITE
        assert len(EmailClassifier.extract_scheduling_links(body_iv)) == 1

        # Online Assessment
        sub_oa = "Coding Challenge: Backend Engineer"
        body_oa = "Please complete the HackerRank test at https://hackerrank.com/test/123"
        intent_oa, _ = EmailClassifier.classify_intent(sub_oa, body_oa)
        assert intent_oa == EmailIntent.ASSESSMENT

        # Rejection
        sub_rej = "Your application to TechCorp"
        body_rej = "Unfortunately, we have decided to pursue other candidates at this time."
        intent_rej, _ = EmailClassifier.classify_intent(sub_rej, body_rej)
        assert intent_rej == EmailIntent.REJECTION

        # Confirmation
        sub_conf = "Application Confirmation"
        body_conf = "Thank you for applying. We have received your application."
        intent_conf, _ = EmailClassifier.classify_intent(sub_conf, body_conf)
        assert intent_conf == EmailIntent.CONFIRMATION

    # 3. Test 2-Way Pipeline Synchronization
    @pytest.mark.asyncio
    async def test_pipeline_synchronization(self):
        job_id = f"job_m5_{uuid.uuid4().hex[:6]}"
        job = JobListing(
            job_id=job_id,
            fingerprint="fp_m5_test",
            platform="Greenhouse",
            company="LinearCorp",
            title="Backend Engineer",
            url="https://boards.greenhouse.io/linearcorp/jobs/1",
            status=ApplicationStatus.SUBMITTED
        )
        self.db.save_job(job)

        import app.email.sync
        orig_db = app.email.sync.db
        app.email.sync.db = self.db

        try:
            res = await EmailSyncEngine.process_inbound_email(
                sender="recruiting@linearcorp.com",
                recipient="scorpionsatyajit@gmail.com",
                subject="Interview with LinearCorp for Backend Engineer",
                body_html="<p>We want to invite you to interview! Book here: https://calendly.com/linearcorp/screen</p>"
            )

            assert res["status"] == "success"
            assert res["intent"] == "INTERVIEW_INVITE"
            assert res["associated_job_id"] == job_id
            assert res["updated_pipeline_status"] == "INTERVIEW"

            # Check DB status
            updated_job = next((j for j in self.db.get_jobs() if j.job_id == job_id), None)
            assert updated_job is not None
            assert updated_job.status == ApplicationStatus.INTERVIEW

        finally:
            app.email.sync.db = orig_db

    # 4. Test Intelligent Follow-Up Engine
    def test_followup_generation(self):
        job = JobListing(
            job_id="job_fu_unit",
            fingerprint="fp_fu_unit",
            platform="Lever",
            company="Supabase",
            title="Database Engineer",
            url="https://jobs.lever.co/supabase/1",
            status=ApplicationStatus.SUBMITTED
        )

        fu7 = FollowUpEngine.generate_followup_email(self.profile, job, stage_days=7)
        assert "Supabase" in fu7["subject"] or "Supabase" in fu7["body"]
        assert "Database Engineer" in fu7["subject"] or "Database Engineer" in fu7["body"]

        fu14 = FollowUpEngine.generate_followup_email(self.profile, job, stage_days=14)
        assert "Medical AI System" in fu14["body"]
        assert "96.19% accuracy" in fu14["body"]
