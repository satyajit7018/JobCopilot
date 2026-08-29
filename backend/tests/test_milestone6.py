"""
JobCopilot - Milestone 6 End-to-End System Test Suite
Tests Funnel Analytics, Email Radar UI simulation, Bot Telemetry,
and End-to-End Autonomous Workflow Integration.
"""

import sys
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.main import app
from app.core.models import CandidateProfile, RecruiterPreferences, JobListing, ApplicationStatus, Project
from app.core.database import db
from app.core.analytics import AnalyticsEngine


class TestMilestone6:

    @pytest.fixture(autouse=True)
    def setup_profile(self):
        profile = CandidateProfile(
            profile_id="default_user",
            full_name="Satyajit Nayak",
            email="scorpionsatyajit@gmail.com",
            phone="+91 7008053476",
            location="Bangalore, India",
            skills=["Python", "FastAPI", "PyTorch", "Docker"],
            preferences=RecruiterPreferences(
                expected_ctc="20 LPA",
                current_employer="CurrentTech"
            ),
            projects=[Project(name="JobCopilot", description="Autonomous OS", metrics="100% test coverage")]
        )
        db.save_profile(profile)

    @pytest.mark.asyncio
    async def test_analytics_funnel_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/analytics/funnel")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            metrics = data["metrics"]
            assert "total_sourced" in metrics
            assert "response_rate_percent" in metrics
            assert "platform_distribution" in metrics

    @pytest.mark.asyncio
    async def test_inbound_email_radar_flow(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Post Inbound Email
            email_payload = {
                "sender": "talent@airbnb.com",
                "subject": "Interview Invitation: Senior Software Engineer at Airbnb",
                "body_html": "<p>Hi Satyajit, we would like to interview you! Book here: https://calendly.com/airbnb/screen</p><img src='https://mandrillapp.com/track/open.php?u=1' width='1' height='1'>"
            }
            res = await ac.post("/api/email/inbound", json=email_payload)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            assert data["intent"] == "INTERVIEW_INVITE"
            assert data["has_tracking_pixels"] is True
            assert len(data["scheduling_links"]) > 0

            # 2. Query Messages List
            res_list = await ac.get("/api/email/messages")
            assert res_list.status_code == 200
            list_data = res_list.json()
            assert list_data["count"] >= 1
            assert any("airbnb.com" in m["sender"] for m in list_data["messages"])

    @pytest.mark.asyncio
    async def test_end_to_end_pipeline_lifecycle(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Check API Health
            h_res = await ac.get("/api/health")
            assert h_res.status_code == 200

            # 2. Get Questionnaire
            q_res = await ac.get("/api/questionnaire?profile_id=default_user")
            assert q_res.status_code == 200

            # 3. Discover Jobs
            d_res = await ac.post("/api/discovery/run?profile_id=default_user")
            assert d_res.status_code == 200

            # 4. Fetch Sourced Jobs
            j_res = await ac.get("/api/jobs")
            assert j_res.status_code == 200
            jobs = j_res.json()["jobs"]
            assert len(jobs) > 0

            # 5. Tailor First Job
            target_job = jobs[0]
            t_res = await ac.post(f"/api/jobs/{target_job['job_id']}/tailor?profile_id=default_user")
            assert t_res.status_code == 200
            t_data = t_res.json()
            assert "tailored_pdf_path" in t_data
            assert "cover_letter" in t_data
            assert "outreach" in t_data
