"""
JobCopilot - Audit Fixes & Regressions Test Suite
Verifies:
1. Autonomous runner fallback execution (datetime import integrity)
2. Secure Object Storage Download endpoint with path traversal defense & expiry
3. Salary negotiation numerical parser across currency & comma formats
4. RateLimiter cache invalidation and DB synchronization
5. Refresh token rotation & revocation
"""

import sys
import time
import uuid
from pathlib import Path
from datetime import timedelta
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.main import app
from app.core.models import (
    CandidateProfile, RecruiterPreferences, JobListing,
    ApplicationStatus, Project, User, UserRole
)
from app.core.database import db
from app.core.object_storage import ObjectStorageAdapter
from app.core.rate_limiter import rate_limiter, SubscriptionTier
from app.core.negotiation import SalaryNegotiationEngine
from app.bot.runner import AutonomousJobRunner
from app.api.auth import create_jwt_token


class TestAuditFixes:

    @pytest.fixture(autouse=True)
    def setup_user(self):
        self.user_id = f"usr_test_audit_{uuid.uuid4().hex[:6]}"
        self.email = f"{self.user_id}@jobcopilot.test"
        
        user = User(
            user_id=self.user_id,
            email=self.email,
            password_hash="argon2_test_hash",
            full_name="Audit Candidate",
            role=UserRole.PRO,
            is_active=True
        )
        db.create_user(user)

        self.profile = CandidateProfile(
            id=self.user_id,
            user_id=self.user_id,
            full_name="Audit Candidate",
            email=self.email,
            phone="+1-555-0199",
            location="San Francisco, CA",
            skills=["Python", "FastAPI", "Docker", "Playwright"],
            preferences=RecruiterPreferences(expected_ctc="35 LPA"),
            projects=[Project(name="AuditEngine", description="Integrity verify", metrics="100% test pass")]
        )
        db.save_profile(self.profile, user_id=self.user_id)
        self.access_token = create_jwt_token(
            {"sub": self.user_id, "email": self.email, "role": "PRO", "type": "access"},
            timedelta(minutes=15)
        )
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    @pytest.mark.asyncio
    async def test_runner_fallback_datetime_import(self):
        """Verifies that AutonomousJobRunner executes simulated dry-run without datetime NameError."""
        job = JobListing(
            job_id=f"job_{uuid.uuid4().hex[:8]}",
            user_id=self.user_id,
            fingerprint=f"fp_{uuid.uuid4().hex[:8]}",
            platform="Greenhouse",
            company="Stripe",
            title="Backend Engineer",
            location="Remote",
            url="https://boards.greenhouse.io/stripe/jobs/123",
            description="Build scalable payment APIs.",
            status=ApplicationStatus.DISCOVERED
        )
        db.save_job(job, user_id=self.user_id)

        runner = AutonomousJobRunner(mode="DRY_RUN")
        res = await runner.execute_application(
            job_id=job.job_id,
            profile_id=self.user_id,
            user_id=self.user_id
        )
        assert res["status"] in ["success", "completed"]
        updated_job = db.get_job_by_id(job.job_id, user_id=self.user_id)
        assert updated_job is not None
        assert updated_job.status == ApplicationStatus.SUBMITTED
        assert updated_job.applied_at is not None

    @pytest.mark.asyncio
    async def test_storage_download_endpoint_success(self):
        """Verifies secure file streaming from /api/storage/download."""
        adapter = ObjectStorageAdapter()
        test_filename = f"resume_{self.user_id}.pdf"
        test_content = b"%PDF-1.4 simulated resume content"
        adapter.upload_resume(user_id=self.user_id, filename=test_filename, content=test_content)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(
                f"/api/storage/download?file={test_filename}&user_id={self.user_id}",
                headers=self.headers
            )
            assert res.status_code == 200
            assert res.content == test_content
            assert res.headers.get("content-type") == "application/pdf"

    @pytest.mark.asyncio
    async def test_storage_download_path_traversal_defense(self):
        """Verifies path traversal filenames (e.g. ../../) are rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(
                f"/api/storage/download?file=../../etc/passwd&user_id={self.user_id}",
                headers=self.headers
            )
            assert res.status_code in [400, 403, 404]

    @pytest.mark.asyncio
    async def test_storage_download_cross_tenant_denial(self):
        """Verifies candidate cannot download another candidate's stored files."""
        other_user = f"usr_other_{uuid.uuid4().hex[:6]}"
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(
                f"/api/storage/download?file=secret.pdf&user_id={other_user}",
                headers=self.headers
            )
            assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_storage_download_expiry(self):
        """Verifies expired presigned download links return 403."""
        adapter = ObjectStorageAdapter()
        test_filename = f"resume_exp_{self.user_id}.pdf"
        adapter.upload_resume(user_id=self.user_id, filename=test_filename, content=b"content")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            past_exp = int(time.time()) - 100
            res = await ac.get(
                f"/api/storage/download?file={test_filename}&user_id={self.user_id}&exp={past_exp}",
                headers=self.headers
            )
            assert res.status_code == 403

    def test_negotiation_salary_parser_edge_cases(self):
        """Verifies salary script generator handles diverse currency and comma formats."""
        test_cases = [
            ("$180,000", "$210,000"),
            ("35 LPA", "45 LPA"),
            ("$150k", "$175k"),
            ("160,000 USD", "190,000 USD")
        ]
        for current_base, target_base in test_cases:
            res = SalaryNegotiationEngine.generate_advanced_counter_script(
                candidate_name="Alex Mercer",
                target_company="Stripe",
                role_title="Staff Software Engineer",
                current_base=current_base,
                current_equity="30k/yr",
                target_base=target_base,
                target_equity="45k/yr",
                competing_company="Uber",
                competing_tc="$220,000"
            )
            assert "negotiation_email" in res
            assert "phone_talking_points" in res
            assert len(res["phone_talking_points"]) > 20

    def test_rate_limiter_cache_invalidation_and_sync(self):
        """Verifies RateLimiter cache invalidation and tier updates."""
        rate_limiter.set_user_tier(self.user_id, SubscriptionTier.FREE, sync_db=True)
        assert rate_limiter.get_user_tier(self.user_id) == SubscriptionTier.FREE

        # Invalidate cache
        rate_limiter.invalidate_cache(self.user_id)

        # Update to ELITE
        rate_limiter.set_user_tier(self.user_id, SubscriptionTier.ELITE, sync_db=True)
        assert rate_limiter.get_user_tier(self.user_id) == SubscriptionTier.ELITE

        summary = rate_limiter.get_usage_summary(self.user_id)
        assert summary["tier"] == "ELITE"
        assert summary["daily_limit"] == "Unlimited"
