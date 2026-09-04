"""
JobCopilot - Epic B Verification Suite
Tests the Idempotent Apply Ledger, Structured Error Taxonomy,
Exponential Backoff, Multi-Provider CAPTCHA Detection, and HITL Evidence Capturing.
"""

import uuid
from datetime import timedelta
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.models import (
    User, JobListing, ApplicationStatus, CandidateProfile,
    ApplyLedgerEntry, ApplyLedgerStatus, HITLEvent
)
from app.core.database import db
from app.api.auth import create_jwt_token
from app.bot.errors import (
    classify_bot_error, is_transient, calculate_backoff_delay,
    BotErrorCategory, DuplicateApplicationError, JobExpiredError, TransientBotError
)
from app.bot.captcha_detector import detect_captcha_in_html
from app.bot.apply_ledger import apply_ledger
from app.bot.runner import AutonomousJobRunner
from app.bot.hitl_agent import HITLAgent


@pytest.fixture
def test_user():
    uid = f"user_epic_b_{uuid.uuid4().hex[:6]}"
    user = User(
        user_id=uid,
        email=f"{uid}@jobcopilot.test",
        password_hash="mock_hash",
        tier="ELITE",
        is_active=True
    )
    db.create_user(user)

    profile = CandidateProfile(
        id=uid,
        user_id=uid,
        full_name="Alex Mercer",
        email=user.email,
        phone="+1 415-555-0199",
        location="San Francisco, CA",
        skills=["Python", "FastAPI", "Playwright", "Distributed Systems"]
    )
    db.save_profile(profile, user_id=uid)

    token = create_jwt_token(
        {"sub": uid, "email": user.email, "role": "PRO", "type": "access"},
        timedelta(minutes=60)
    )
    return {"user": user, "profile": profile, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


def test_error_taxonomy_classification():
    """Validates categorization of transient vs terminal errors and CAPTCHA detection."""
    # Transient classifications
    assert classify_bot_error(None, status_code=429) == BotErrorCategory.TRANSIENT_RATE_LIMIT
    assert is_transient(BotErrorCategory.TRANSIENT_RATE_LIMIT) is True

    assert classify_bot_error(None, status_code=502) == BotErrorCategory.TRANSIENT_SERVER_ERROR
    assert is_transient(BotErrorCategory.TRANSIENT_SERVER_ERROR) is True

    assert classify_bot_error("Navigation timeout of 30000ms exceeded") == BotErrorCategory.TRANSIENT_TIMEOUT
    assert is_transient(BotErrorCategory.TRANSIENT_TIMEOUT) is True

    assert classify_bot_error("Connection reset by peer ECONNRESET") == BotErrorCategory.TRANSIENT_NETWORK
    assert is_transient(BotErrorCategory.TRANSIENT_NETWORK) is True

    # Terminal classifications
    assert classify_bot_error(None, status_code=404) == BotErrorCategory.TERMINAL_JOB_EXPIRED
    assert is_transient(BotErrorCategory.TERMINAL_JOB_EXPIRED) is False

    assert classify_bot_error("The position has been filled and is no longer accepting applications") == BotErrorCategory.TERMINAL_JOB_EXPIRED
    assert classify_bot_error("You have already applied for this vacancy") == BotErrorCategory.TERMINAL_ALREADY_APPLIED
    assert classify_bot_error("Cloudflare Ray ID access denied 403") == BotErrorCategory.TERMINAL_BLOCKED_WAF
    assert classify_bot_error("Please log in to continue with your application") == BotErrorCategory.TERMINAL_AUTH_REQUIRED

    # CAPTCHA / Anti-Bot
    assert classify_bot_error("Recaptcha challenge required") == BotErrorCategory.HITL_CAPTCHA_DETECTED
    assert classify_bot_error("", page_text="<iframe src='https://challenges.cloudflare.com/turnstile'></iframe>") == BotErrorCategory.HITL_CAPTCHA_DETECTED


def test_exponential_backoff_delay():
    """Validates exponential delay growth and jitter constraints."""
    # Attempt 1
    d1 = calculate_backoff_delay(1, base_delay=1.0, jitter=False)
    assert d1 == 1.0

    # Attempt 2
    d2 = calculate_backoff_delay(2, base_delay=1.0, jitter=False)
    assert d2 == 2.0

    # Attempt 3
    d3 = calculate_backoff_delay(3, base_delay=1.0, jitter=False)
    assert d3 == 4.0

    # Attempt with jitter stays within reasonable bounds
    for _ in range(10):
        dj = calculate_backoff_delay(2, base_delay=1.0, jitter=True)
        assert 0.5 <= dj <= 10.0

    # Edge cases
    assert calculate_backoff_delay(0, base_delay=1.0, jitter=False) == 1.0
    assert calculate_backoff_delay(10, base_delay=1.0, max_delay=30.0, jitter=False) == 30.0


def test_captcha_detector_signatures():
    """Validates heuristic detection of reCAPTCHA, hCaptcha, Turnstile, and Arkose."""
    # reCAPTCHA
    recaptcha_html = "<div><iframe src='https://www.google.com/recaptcha/api2/anchor'></iframe></div>"
    res = detect_captcha_in_html(recaptcha_html)
    assert res is not None
    assert res["detected"] is True
    assert res["provider"] == "recaptcha"

    # Turnstile
    turnstile_html = "<div class='cf-turnstile' data-sitekey='abc'></div>"
    res = detect_captcha_in_html(turnstile_html)
    assert res is not None
    assert res["provider"] == "turnstile"

    # hCaptcha
    hcaptcha_html = "<div><iframe src='https://hcaptcha.com/check'></iframe></div>"
    res = detect_captcha_in_html(hcaptcha_html)
    assert res is not None
    assert res["provider"] == "hcaptcha"

    # Textual Challenge
    text_challenge = "<h1>Please verify you are a human before proceeding</h1>"
    res = detect_captcha_in_html(text_challenge)
    assert res is not None
    assert res["provider"] == "generic_challenge"

    # Normal Page
    normal_html = "<html><body><h1>Careers at Stripe</h1><form><input name='email'></form></body></html>"
    assert detect_captcha_in_html(normal_html) is None


def test_idempotent_apply_ledger_lifecycle(test_user):
    """Verifies atomic lock acquisition, duplicate application rejections, and state transitions."""
    uid = test_user["user"].user_id
    job_id = f"job_idem_{uuid.uuid4().hex[:6]}"
    fingerprint = f"fp_{uuid.uuid4().hex[:8]}"

    # 1. Initial lock acquisition succeeds
    acquired, entry, reason = apply_ledger.acquire_lock(
        user_id=uid,
        job_id=job_id,
        job_fingerprint=fingerprint
    )
    assert acquired is True
    assert entry is not None
    assert entry.status == ApplyLedgerStatus.INITIATED
    assert entry.attempt_count == 1

    # 2. Transition to IN_PROGRESS
    apply_ledger.mark_in_progress(entry.ledger_id, user_id=uid)
    e = apply_ledger.get_ledger_for_job(uid, job_id)
    assert e.status == ApplyLedgerStatus.IN_PROGRESS

    # 3. Concurrent lock attempt while IN_PROGRESS is rejected
    acquired2, entry2, reason2 = apply_ledger.acquire_lock(
        user_id=uid,
        job_id=job_id,
        job_fingerprint=fingerprint
    )
    assert acquired2 is False
    assert "actively executing" in reason2

    # 4. Transition to SUBMITTED
    apply_ledger.mark_submitted(entry.ledger_id, user_id=uid, confirmation_id="CONF-12345", screenshot_path="/tmp/shot.png")
    e_sub = apply_ledger.get_ledger_for_job(uid, job_id)
    assert e_sub.status == ApplyLedgerStatus.SUBMITTED
    assert e_sub.confirmation_id == "CONF-12345"

    # 5. Subsequent apply attempt after SUBMITTED is blocked permanently
    acquired3, entry3, reason3 = apply_ledger.acquire_lock(
        user_id=uid,
        job_id=job_id,
        job_fingerprint=fingerprint
    )
    assert acquired3 is False
    assert "already submitted" in reason3
    assert apply_ledger.is_already_applied(uid, fingerprint) is True


def test_apply_ledger_retry_and_exhaustion(test_user):
    """Verifies that transient failures allow retries up to max_retries, then reject."""
    uid = test_user["user"].user_id
    job_id = f"job_retry_{uuid.uuid4().hex[:6]}"
    fingerprint = f"fp_retry_{uuid.uuid4().hex[:8]}"

    # Attempt 1
    acq1, ent1, _ = apply_ledger.acquire_lock(user_id=uid, job_id=job_id, job_fingerprint=fingerprint, max_retries=3)
    assert acq1 is True
    assert ent1.attempt_count == 1
    apply_ledger.mark_failed(ent1.ledger_id, user_id=uid, error_category="TRANSIENT_TIMEOUT", error_message="Timed out")

    # Attempt 2
    acq2, ent2, _ = apply_ledger.acquire_lock(user_id=uid, job_id=job_id, job_fingerprint=fingerprint, max_retries=3)
    assert acq2 is True
    assert ent2.attempt_count == 2
    apply_ledger.mark_failed(ent2.ledger_id, user_id=uid, error_category="TRANSIENT_RATE_LIMIT", error_message="Rate limited")

    # Attempt 3
    acq3, ent3, _ = apply_ledger.acquire_lock(user_id=uid, job_id=job_id, job_fingerprint=fingerprint, max_retries=3)
    assert acq3 is True
    assert ent3.attempt_count == 3
    apply_ledger.mark_failed(ent3.ledger_id, user_id=uid, error_category="TRANSIENT_SERVER_ERROR", error_message="502 Bad Gateway")

    # Attempt 4 (Exceeded max_retries=3)
    acq4, ent4, reason4 = apply_ledger.acquire_lock(user_id=uid, job_id=job_id, job_fingerprint=fingerprint, max_retries=3)
    assert acq4 is False
    assert "exceeded max retries" in reason4.lower()


@pytest.mark.asyncio
async def test_bot_runner_idempotent_execution(test_user):
    """Verifies that AutonomousJobRunner records success in ledger and blocks duplicate calls."""
    uid = test_user["user"].user_id
    job = JobListing(
        job_id=f"job_run_{uuid.uuid4().hex[:6]}",
        user_id=uid,
        fingerprint=f"fp_run_{uuid.uuid4().hex[:8]}",
        platform="Greenhouse",
        company="Stripe",
        title="Backend Engineer",
        location="San Francisco, CA",
        url="https://boards.greenhouse.io/stripe/jobs/123",
        description="Build payment platforms and APIs.",
        status=ApplicationStatus.DISCOVERED
    )
    db.save_job(job, user_id=uid)

    runner = AutonomousJobRunner(mode="DRY_RUN")
    result = await runner.execute_application(
        job_id=job.job_id,
        profile_id=uid,
        user_id=uid
    )
    assert result["status"] == "success"
    assert "ledger_id" in result

    # Verify ledger entry
    ledger = apply_ledger.get_ledger_for_job(uid, job.job_id)
    assert ledger is not None
    assert ledger.status == ApplyLedgerStatus.SUBMITTED

    # Second execution attempt should be blocked by idempotency ledger
    result_dup = await runner.execute_application(
        job_id=job.job_id,
        profile_id=uid,
        user_id=uid
    )
    assert result_dup["status"] == "conflict"
    assert "already submitted" in result_dup["message"].lower()


@pytest.mark.asyncio
async def test_hitl_evidence_capturing_and_api(test_user):
    """Verifies screenshot and DOM evidence persistence in HITL events and API retrieval."""
    uid = test_user["user"].user_id
    job_id = f"job_hitl_{uuid.uuid4().hex[:6]}"

    # Dispatch HITL request with evidence
    evidence_path = "/data/screenshots/hitl_captcha_test.png"
    dom_snip = "<iframe src='https://challenges.cloudflare.com/turnstile' class='cf-turnstile'></iframe>"
    field_sel = ".cf-turnstile"

    event = await HITLAgent.request_human_input(
        job_id=job_id,
        company="Stripe",
        role_title="Backend Engineer",
        question_text="Complete Cloudflare Turnstile challenge to submit form.",
        input_type="captcha",
        screenshot_path=evidence_path,
        dom_snapshot=dom_snip,
        field_selector=field_sel,
        user_id=uid
    )

    # Verify database persistence
    saved_evt = db.get_hitl_event(event.event_id, user_id=uid)
    assert saved_evt is not None
    assert saved_evt.screenshot_path == evidence_path
    assert saved_evt.dom_snapshot == dom_snip
    assert saved_evt.field_selector == field_sel

    # Test GET /api/hitl/{event_id}/evidence endpoint
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/api/hitl/{event.event_id}/evidence", headers=test_user["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["screenshot_path"] == evidence_path
        assert data["dom_snapshot"] == dom_snip
        assert data["field_selector"] == field_sel


@pytest.mark.asyncio
async def test_bot_ledger_api_endpoints(test_user):
    """Verifies /api/bot/ledger and /api/bot/ledger/{job_id} query endpoints."""
    uid = test_user["user"].user_id
    job_id = f"job_api_{uuid.uuid4().hex[:6]}"
    fp = f"fp_api_{uuid.uuid4().hex[:8]}"

    # Seed an entry in ledger
    apply_ledger.acquire_lock(user_id=uid, job_id=job_id, job_fingerprint=fp)
    ledger = apply_ledger.get_ledger_for_job(uid, job_id)
    apply_ledger.mark_submitted(ledger.ledger_id, user_id=uid, confirmation_id="CONF-API-99")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. List ledger
        resp = await ac.get("/api/bot/ledger?limit=10", headers=test_user["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert any(e["job_id"] == job_id for e in data["entries"])

        # 2. Get single job ledger
        resp_single = await ac.get(f"/api/bot/ledger/{job_id}", headers=test_user["headers"])
        assert resp_single.status_code == 200
        single_data = resp_single.json()
        assert single_data["status"] == "success"
        assert single_data["ledger"]["confirmation_id"] == "CONF-API-99"

        # 3. Prevent duplicate apply via POST /api/bot/apply/{job_id}
        resp_apply = await ac.post(f"/api/bot/apply/{job_id}", headers=test_user["headers"])
        assert resp_apply.status_code == 409
        assert "already submitted" in resp_apply.json()["detail"].lower()

        # 4. Prevent duplicate apply via POST /api/jobs/apply-async/{job_id}
        resp_async = await ac.post(f"/api/jobs/apply-async/{job_id}", headers=test_user["headers"])
        assert resp_async.status_code == 409
        assert "already submitted" in resp_async.json()["detail"].lower()


@pytest.mark.asyncio
async def test_bot_runner_captcha_escalation_flow(test_user, monkeypatch):
    """Verifies that CAPTCHA detection triggers HITL escalation, evidence capture, and ledger pause."""
    uid = test_user["user"].user_id
    job = JobListing(
        job_id=f"job_cap_{uuid.uuid4().hex[:6]}",
        user_id=uid,
        fingerprint=f"fp_cap_{uuid.uuid4().hex[:8]}",
        platform="Greenhouse",
        company="Datadog",
        title="Software Engineer",
        location="Remote",
        url="https://boards.greenhouse.io/datadog/jobs/999",
        description="Distributed tracing systems.",
        status=ApplicationStatus.DISCOVERED
    )
    db.save_job(job, user_id=uid)

    # Mock detect_captcha to simulate active Cloudflare Turnstile challenge
    async def mock_detect_captcha(page):
        return {
            "detected": True,
            "provider": "turnstile",
            "selector": ".cf-turnstile",
            "description": "Cloudflare Turnstile challenge detected."
        }

    monkeypatch.setattr("app.bot.runner.detect_captcha", mock_detect_captcha)

    runner = AutonomousJobRunner(mode="LIVE")
    res = await runner.execute_application(
        job_id=job.job_id,
        profile_id=uid,
        user_id=uid
    )
    assert res["status"] == "hitl_required"
    assert res["category"] == "HITL_CAPTCHA_DETECTED"
    assert "hitl_event_id" in res

    # Verify job status transitioned to HITL_REQUIRED
    updated_job = db.get_job_by_id(job.job_id, user_id=uid)
    assert updated_job.status == ApplicationStatus.HITL_REQUIRED

    # Verify ledger transitioned to HITL_PAUSED
    ledger = apply_ledger.get_ledger_for_job(uid, job.job_id)
    assert ledger.status == ApplyLedgerStatus.HITL_PAUSED
