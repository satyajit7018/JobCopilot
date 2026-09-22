"""
JobCopilot - Inbound Email Webhook & Multi-Tenant Routing Test Suite
Validates subaddress parsing, Postmark/SendGrid webhook ingestion, and pipeline state updates.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import db
from app.core.models import ApplicationStatus, JobListing, User, UserRole
from app.main import app


@pytest.mark.asyncio
async def test_inbound_webhook_subaddress_attribution(monkeypatch):
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

    import hashlib
    import hmac
    import json

    from app.core.settings import settings
    secret = "test-inbound-secret"
    monkeypatch.setattr(settings, "INBOUND_EMAIL_WEBHOOK_SECRET", secret)
    body = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/email/inbound-webhook", content=body,
                            headers={"Content-Type": "application/json", "X-JobCopilot-Signature": sig})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["user_id"] == user_id
        assert data["result"]["intent"] == "INTERVIEW_INVITE"

    # Verify job status was automatically moved to INTERVIEW for this user
    updated_job = db.get_job_by_id(job.job_id, user_id=user_id)
    assert updated_job is not None
    assert updated_job.status == ApplicationStatus.INTERVIEW


@pytest.mark.asyncio
async def test_inbound_webhook_rejects_unsigned_and_ignores_body_user_id(monkeypatch):
    """Audit P0-3: unsigned requests are refused, and a body-supplied user_id can never route mail."""
    from app.core.settings import settings
    from app.email.inbound_provider import InboundEmailProvider

    monkeypatch.setattr(settings, "INBOUND_EMAIL_WEBHOOK_SECRET", None)
    monkeypatch.setattr(settings, "INBOUND_EMAIL_ALLOW_UNSIGNED", False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/email/inbound-webhook", json={"sender": "a@b.c", "subject": "x", "body_text": "y",
                                                               "recipient": "radar@jobcopilot.app"})
        assert res.status_code == 403

    parsed = InboundEmailProvider.parse_webhook_payload(
        {"sender": "a@b.c", "subject": "x", "body_text": "y", "recipient": "radar+usr_real@jobcopilot.app",
         "user_id": "usr_victim"})
    assert parsed["user_id"] == "usr_real"
