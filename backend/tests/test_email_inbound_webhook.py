"""
JobCopilot - Inbound Email Webhook & Multi-Tenant Routing Test Suite
Validates subaddress parsing, Postmark/SendGrid webhook ingestion, and pipeline state updates.
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole, JobListing, ApplicationStatus


@pytest.mark.asyncio
async def test_inbound_webhook_subaddress_attribution():
    """Asserts subaddress recipient (radar+usr_xyz@jobcopilot.app) attributes correctly to tenant."""
    user_id = f"usr_radar_{uuid.uuid4().hex[:6]}"
    email = f"{user_id}@test.com"
    user = User(user_id=user_id, email=email, password_hash="test", role=UserRole.FREE)
    db.create_user(user)

    # Create tracked job for this user
    job = JobListing(
        job_id=f"job_email_{uuid.uuid4().hex[:6]}",
        user_id=user_id,
        fingerprint=f"fp_{uuid.uuid4().hex[:8]}",
        platform="Greenhouse",
        company="Stripe",
        title="Backend Engineer",
        url="https://stripe.com",
        status=ApplicationStatus.SUBMITTED
    )
    db.save_job(job, user_id=user_id)

    # Inbound email from recruiter
    payload = {
        "sender": "recruiter@stripe.com",
        "recipient": f"radar+{user_id}@jobcopilot.app",
        "subject": "Invitation to Interview: Backend Engineer at Stripe",
        "body_html": "<p>Hi, we loved your application and would like to schedule a 45-min technical screen.</p>",
        "body_text": "Hi, we loved your application and would like to schedule a 45-min technical screen."
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/email/inbound-webhook", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["user_id"] == user_id
        assert data["result"]["intent"] == "INTERVIEW_INVITE"

    # Verify job status was automatically moved to INTERVIEW for this user
    updated_job = db.get_job_by_id(job.job_id, user_id=user_id)
    assert updated_job is not None
    assert updated_job.status == ApplicationStatus.INTERVIEW
