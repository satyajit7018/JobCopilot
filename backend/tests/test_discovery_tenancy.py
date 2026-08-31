"""
JobCopilot - Multi-Tenant Discovery Pipeline Test Suite
Validates that running discovery saves jobs and scores matches strictly for the requesting tenant.
"""

import uuid
import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole, CandidateProfile, RecruiterPreferences
from app.api.auth import create_jwt_token
from app.discovery.orchestrator import discovery_orchestrator


@pytest.mark.asyncio
async def test_discovery_cycle_multi_tenant_isolation():
    """Asserts discovery saves jobs tagged strictly to the requesting user_id."""
    user_a = f"usr_disc_a_{uuid.uuid4().hex[:6]}"
    user_b = f"usr_disc_b_{uuid.uuid4().hex[:6]}"

    # Setup User A with profile
    db.create_user(User(user_id=user_a, email=f"{user_a}@test.com", password_hash="test", role=UserRole.PRO))
    profile_a = CandidateProfile(
        id=user_a,
        user_id=user_a,
        full_name="User Alpha",
        email=f"{user_a}@test.com",
        phone="+1-555-0100",
        location="Remote",
        skills=["Python", "FastAPI", "PostgreSQL"],
        preferences=RecruiterPreferences(target_roles=["Backend Engineer"])
    )
    db.save_profile(profile_a, user_id=user_a)

    # Setup User B without jobs
    db.create_user(User(user_id=user_b, email=f"{user_b}@test.com", password_hash="test", role=UserRole.PRO))

    token_a = create_jwt_token({"sub": user_a, "email": f"{user_a}@test.com", "role": "PRO", "type": "access"}, timedelta(minutes=15))
    token_b = create_jwt_token({"sub": user_b, "email": f"{user_b}@test.com", "role": "PRO", "type": "access"}, timedelta(minutes=15))

    mock_leads = [
        {
            "platform": "Greenhouse",
            "company": "Stripe",
            "title": "Backend Software Engineer",
            "location": "Remote",
            "url": "https://stripe.com/jobs/123",
            "description": "Building high-performance Python and FastAPI payment services.",
            "salary_range": "$170,000 - $210,000"
        }
    ]

    with patch.object(discovery_orchestrator, "_fetch_all_raw_leads", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_leads
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Run discovery for User A
            res = await ac.post("/api/discovery/run", headers={"Authorization": f"Bearer {token_a}"})
            assert res.status_code == 200

            # Query jobs for User A
            res_a = await ac.get("/api/jobs", headers={"Authorization": f"Bearer {token_a}"})
            assert res_a.status_code == 200
            jobs_a = res_a.json()["jobs"]
            assert len(jobs_a) >= 1
            for j in jobs_a:
                assert j["user_id"] == user_a

            # Query jobs for User B -> Must be empty (Zero Cross-Tenant Leakage)
            res_b = await ac.get("/api/jobs", headers={"Authorization": f"Bearer {token_b}"})
            assert res_b.status_code == 200
            jobs_b = res_b.json()["jobs"]
            assert len(jobs_b) == 0
