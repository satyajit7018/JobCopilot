"""
JobCopilot - Multi-Tenant Concurrency & Race Condition Test Suite
Validates atomic transactions, daily apply quota boundaries under parallel load,
and multi-tenant data isolation under high concurrency.
"""

import asyncio
import uuid
import pytest
from datetime import timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole, CandidateProfile, JobListing, ApplicationStatus
from app.api.auth import create_jwt_token
from app.core.rate_limiter import rate_limiter


@pytest.mark.asyncio
async def test_concurrent_rate_limiting_quota():
    """Asserts that 10 concurrent apply attempts strictly enforce the FREE tier limit of 5 applies/day."""
    user_id = f"usr_race_{uuid.uuid4().hex[:6]}"
    email = f"{user_id}@test.com"
    user = User(user_id=user_id, email=email, password_hash="test", role=UserRole.FREE)
    db.create_user(user)

    token = create_jwt_token({"sub": user_id, "email": email, "role": "FREE", "type": "access"}, timedelta(minutes=15))
    headers = {"Authorization": f"Bearer {token}"}

    # Pre-create 10 jobs
    jobs = []
    for i in range(10):
        job = JobListing(
            job_id=f"job_race_{i}_{uuid.uuid4().hex[:6]}",
            user_id=user_id,
            fingerprint=f"fp_race_{i}",
            platform="Greenhouse",
            company=f"Company {i}",
            title="Software Engineer",
            url=f"https://company{i}.com",
            status=ApplicationStatus.DISCOVERED
        )
        db.save_job(job, user_id=user_id)
        jobs.append(job)

    transport = ASGITransport(app=app)

    async def try_apply(job_id: str):
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
            return await ac.post(f"/api/jobs/apply-async/{job_id}", json={"mode": "DRY_RUN"})

    # Launch 10 simultaneous applications
    responses = await asyncio.gather(*[try_apply(j.job_id) for j in jobs])

    accepted = [r for r in responses if r.status_code == 202]
    rate_limited = [r for r in responses if r.status_code == 429]

    # Exactly 5 should succeed (FREE limit = 5/day)
    assert len(accepted) == 5
    # Exactly 5 should be rate limited (429)
    assert len(rate_limited) == 5


@pytest.mark.asyncio
async def test_concurrent_multi_tenant_profile_isolation():
    """Asserts that 5 simultaneous tenants reading and writing profiles experience zero cross-tenant contamination."""
    tenant_ids = [f"usr_tenant_{i}_{uuid.uuid4().hex[:6]}" for i in range(5)]

    for tid in tenant_ids:
        db.create_user(User(user_id=tid, email=f"{tid}@test.com", password_hash="test", role=UserRole.PRO))

    async def tenant_worker(tid: str):
        token = create_jwt_token({"sub": tid, "email": f"{tid}@test.com", "role": "PRO", "type": "access"}, timedelta(minutes=15))
        headers = {"Authorization": f"Bearer {token}"}
        transport = ASGITransport(app=app)
        
        # Save profile
        profile = CandidateProfile(
            id=tid,
            user_id=tid,
            full_name=f"Candidate {tid}",
            email=f"{tid}@test.com",
            phone=f"+1-555-{tid[-4:]}",
            location="Cloud",
            skills=[f"Skill_{tid}"]
        )
        db.save_profile(profile, user_id=tid)

        # Retrieve profile via API
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
            res = await ac.get("/api/auth/me")
            assert res.status_code == 200
            assert res.json()["user_id"] == tid
            assert res.json()["email"] == f"{tid}@test.com"

        # Verify DB retrieval matches precisely
        fetched = db.get_profile(user_id=tid)
        assert fetched is not None
        assert fetched.user_id == tid
        assert fetched.full_name == f"Candidate {tid}"
        assert fetched.skills == [f"Skill_{tid}"]

    # Run all 5 tenants concurrently
    await asyncio.gather(*[tenant_worker(tid) for tid in tenant_ids])
