"""
JobCopilot - Async Background Tasks & HTTP 202 Polling Test Suite
Validates task dispatching, 202 Accepted response format, progress polling, and tenant isolation.
"""

import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import create_jwt_token
from app.core.database import db
from app.core.models import ApplicationStatus, JobListing, User, UserRole
from app.main import app


@pytest.fixture
def test_user_headers():
    user_id = f"usr_task_{uuid.uuid4().hex[:6]}"
    email = f"{user_id}@test.com"
    user = User(user_id=user_id, email=email, password_hash="test", role=UserRole.PRO)
    db.create_user(user)
    token = create_jwt_token({"sub": user_id, "email": email, "role": "PRO", "type": "access"}, timedelta(minutes=30))
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_async_apply_and_poll_status(test_user_headers, monkeypatch):
    """Audit P1-1: status reflects the real run. A dry run succeeds but reports submitted=False."""
    import asyncio

    import app.bot.runner as runner_mod
    from app.core.models import CandidateProfile
    monkeypatch.setattr(runner_mod, "HAS_PLAYWRIGHT", False)
    user_id, headers = test_user_headers
    if not db.get_profile(user_id=user_id):
        db.save_profile(CandidateProfile(id=user_id, user_id=user_id, full_name="T", email="t@t.test",
                                         phone="1", location="Remote"), user_id=user_id)
    job_id = f"job_async_{uuid.uuid4().hex[:6]}"
    job = JobListing(
        job_id=job_id,
        user_id=user_id,
        fingerprint="fp_async",
        platform="Ashby",
        company="Ramp",
        title="Software Engineer",
        url="https://ramp.com/jobs",
        status=ApplicationStatus.DISCOVERED
    )
    db.save_job(job, user_id=user_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        # 1. Dispatch 202 Accepted Task
        res = await ac.post(f"/api/jobs/apply-async/{job_id}?mode=DRY_RUN")
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "ACCEPTED"
        assert "task_id" in data
        assert "poll_url" in data

        task_id = data["task_id"]

        # 2. Poll until the real run finishes
        for _ in range(100):
            poll_res = await ac.get(f"/api/tasks/{task_id}")
            assert poll_res.status_code == 200
            poll_data = poll_res.json()
            if poll_data["task"]["status"] not in ("QUEUED", "PENDING", "STARTED", "RUNNING"):
                break
            await asyncio.sleep(0.05)
        assert poll_data["status"] == "success"
        assert poll_data["task"]["task_id"] == task_id
        assert poll_data["task"]["status"] == "SUCCESS", poll_data
        assert poll_data["task"]["progress_percent"] == 100
        assert poll_data["task"]["result"]["submitted"] is False   # a dry run never submits
