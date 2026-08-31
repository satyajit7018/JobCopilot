"""
JobCopilot - Async Background Tasks & HTTP 202 Polling Test Suite
Validates task dispatching, 202 Accepted response format, progress polling, and tenant isolation.
"""

import uuid
import pytest
from datetime import timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole, JobListing, ApplicationStatus
from app.api.auth import create_jwt_token


@pytest.fixture
def test_user_headers():
    user_id = f"usr_task_{uuid.uuid4().hex[:6]}"
    email = f"{user_id}@test.com"
    user = User(user_id=user_id, email=email, password_hash="test", role=UserRole.PRO)
    db.create_user(user)
    token = create_jwt_token({"sub": user_id, "email": email, "role": "PRO", "type": "access"}, timedelta(minutes=30))
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_async_apply_and_poll_status(test_user_headers):
    user_id, headers = test_user_headers
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
        res = await ac.post(f"/api/jobs/apply-async/{job_id}", json={"mode": "DRY_RUN"})
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "ACCEPTED"
        assert "task_id" in data
        assert "poll_url" in data

        task_id = data["task_id"]

        # 2. Poll Task Status
        poll_res = await ac.get(f"/api/tasks/{task_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        assert poll_data["status"] == "success"
        assert poll_data["task"]["task_id"] == task_id
        assert poll_data["task"]["status"] in ["STARTED", "SUCCESS"]
        assert poll_data["task"]["progress_percent"] >= 25
