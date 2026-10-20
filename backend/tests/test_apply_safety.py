"""
Apply safety: nothing invented reaches an employer's form.

- Answers come only from the user: profile fields they have saved, or answers they gave.
- No canned essays, no defaults, no leftover {placeholders}, no other user's answers.
- A form with an unanswered required question is never submitted.
- Sending for real is behind a server switch that is off by default.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.bot.apply_ledger import apply_ledger
from app.bot.form import answer_for, missing_required
from app.core.database import db
from app.core.models import (
    ApplicationStatus,
    ApplyLedgerStatus,
    CandidateProfile,
    ConsentType,
    HITLEvent,
    JobListing,
    RecruiterPreferences,
    User,
    UserConsent,
    UserRole,
)
from app.core.questionnaire import QuestionnaireEngine
from app.core.settings import settings
from app.core.vector_vault import vault
from app.main import app


def _profile(uid: str, confirmed=(), **prefs) -> CandidateProfile:
    profile = CandidateProfile(
        id=uid, user_id=uid, full_name="Asha Rao", email=f"{uid}@example.test", phone="+91 9000000001",
        location="Pune", skills=["Python", "Go"],
        preferences=RecruiterPreferences(confirmed=list(confirmed), **prefs),
    )
    db.save_profile(profile, user_id=uid)
    return profile


def _uid() -> str:
    return f"usr_{uuid.uuid4().hex[:10]}"


# --- Answers ------------------------------------------------------------------------------


def test_unsaved_preferences_never_answer_a_form():
    # Defaults and resume guesses exist, but the user hasn't saved them: nothing is answered.
    profile = _profile(_uid(), expected_ctc="15 LPA", work_authorization="Citizen", willing_to_relocate=True)
    for question in ("What is your expected CTC?", "Are you legally authorized to work in India?",
                     "Are you willing to relocate?", "What is your notice period?"):
        assert answer_for(question, profile) is None, question


def test_saved_preferences_answer_in_plain_words():
    profile = _profile(
        _uid(),
        confirmed=["expected_ctc", "notice_period_days", "work_authorization", "requires_sponsorship", "willing_to_relocate"],
        expected_ctc="28 LPA", notice_period_days=30, work_authorization="Citizen / Permanent Resident",
        requires_sponsorship=False, willing_to_relocate=False,
    )
    assert answer_for("What is your expected CTC?", profile) == "28 LPA"
    assert answer_for("What is your notice period?", profile) == "30 days"
    assert answer_for("Are you legally authorized to work in India?", profile) == "Citizen / Permanent Resident"
    assert answer_for("Will you require visa sponsorship?", profile) == "No"
    assert answer_for("Are you open to relocate?", profile) == "No"


def test_no_canned_essays_or_placeholders():
    profile = _profile(_uid(), confirmed=["expected_ctc"], expected_ctc="")
    assert answer_for("Why do you want to work at our company?", profile, company="Acme") is None
    assert answer_for("Share a link to a technical project you built.", profile) is None
    assert answer_for("Why should we hire you for this role?", profile) is None
    # Saved but blank: still nothing to say, so nothing is said.
    assert answer_for("What is your expected salary?", profile) is None


def test_years_with_one_skill_are_never_total_years():
    profile = _profile(_uid(), confirmed=["years_of_experience"], years_of_experience=6.0)
    assert answer_for("Total years of experience?", profile) == "6 years"
    assert answer_for("How many years of experience do you have with Kubernetes?", profile) is None


def test_old_copies_of_profile_defaults_are_ignored():
    uid = _uid()
    profile = _profile(uid)
    # What older versions stored for every user from defaults.
    vault.learn_answer("What is your expected CTC / compensation?", "15 LPA", user_id=uid)
    vault.learn_answer("How many years of experience do you have with Python?", "1.0 years", user_id=uid)
    assert answer_for("What is your expected CTC?", profile) is None
    assert answer_for("How many years of experience do you have with Python?", profile) is None


def test_own_answers_are_reused_but_never_another_users():
    owner, other = _uid(), _uid()
    owner_profile, other_profile = _profile(owner), _profile(other)
    vault.learn_answer("Do you have experience leading on-call rotations?", "Yes, for two years at my last job.", user_id=owner)
    assert answer_for("Do you have experience leading on-call rotations?", owner_profile) == "Yes, for two years at my last job."
    assert answer_for("Do you have experience leading on-call rotations?", other_profile) is None


def test_why_this_company_is_never_reused():
    uid = _uid()
    profile = _profile(uid)
    vault.learn_answer("Why do you want to work at Razorpay?", "I use Razorpay every day.", user_id=uid)
    assert answer_for("Why do you want to work at Zomato?", profile, company="Zomato") is None


def test_saving_preferences_marks_them_as_the_users_answers():
    profile = CandidateProfile(full_name="A", email="a@example.test", phone="", location="")
    QuestionnaireEngine.apply_answers_to_profile(profile, {"expected_ctc": "30 LPA", "current_ctc": "", "work_authorization": "Citizen"})
    assert "expected_ctc" in profile.preferences.confirmed
    assert "current_ctc" not in profile.preferences.confirmed  # blank is not an answer
    assert {"work_authorization", "requires_sponsorship"} <= set(profile.preferences.confirmed)


# --- Through the API -------------------------------------------------------------------------


def _client_for(role=UserRole.PRO):
    from datetime import timedelta

    from app.api.auth import create_jwt_token
    uid = _uid()
    db.create_user(User(user_id=uid, email=f"{uid}@example.test", password_hash="x", role=role))
    token = create_jwt_token({"sub": uid, "email": f"{uid}@example.test", "role": role.value, "type": "access"}, timedelta(minutes=15))
    return uid, TestClient(app), {"Authorization": f"Bearer {token}"}


def test_answering_a_held_question_saves_it_for_that_user_only():
    uid, c, headers = _client_for()
    _profile(uid)
    job = JobListing(job_id=f"job_{uuid.uuid4().hex[:8]}", user_id=uid, fingerprint=uuid.uuid4().hex, platform="Greenhouse",
                     company="Acme", title="SDE", url="https://acme.test/job")
    db.save_job(job, user_id=uid)
    question = f"Have you used our product {uuid.uuid4().hex[:6]}?"
    event = HITLEvent(event_id=f"evt_{uuid.uuid4().hex[:8]}", user_id=uid, job_id=job.job_id, company="Acme",
                      role_title="SDE", question_text=question, input_type="text")
    db.save_hitl_event(event, user_id=uid)
    r = c.post("/api/hitl/resolve-held", headers=headers, json={"event_id": event.event_id, "user_answer": "Yes, daily.", "save_to_vault": True})
    assert r.status_code == 200, r.text
    assert any(e.question_pattern == question for e in db.get_vault_entries(uid))
    assert not any(e.question_pattern == question for e in db.get_vault_entries("default"))


def test_questionnaire_without_a_profile_invents_no_contact_details():
    uid, c, headers = _client_for(UserRole.FREE)
    r = c.post("/api/questionnaire", headers=headers, json={"answers": {"expected_ctc": "20 LPA"}})
    assert r.status_code == 200, r.text
    profile = r.json()["profile"]
    assert profile["phone"] == "" and profile["location"] == ""


def test_real_sending_is_off_by_default():
    assert settings.LIVE_SUBMISSION_ENABLED is False
    uid, c, headers = _client_for()
    # Even with the user's consent, the server switch wins.
    db.record_user_consent(UserConsent(consent_id=f"c_{uuid.uuid4().hex[:8]}", user_id=uid,
                                       consent_type=ConsentType.AUTONOMOUS_SUBMISSION, consented=True))
    job = JobListing(job_id=f"job_{uuid.uuid4().hex[:8]}", user_id=uid, fingerprint=uuid.uuid4().hex, platform="Greenhouse",
                     company="Acme", title="SDE", url="https://acme.test/job")
    db.save_job(job, user_id=uid)
    r = c.post(f"/api/jobs/apply-async/{job.job_id}?mode=LIVE", headers=headers)
    assert r.status_code == 403 and "switched off" in r.json()["detail"]
    assert c.get("/api/auth/public-config").json()["live_submission"] is False


@pytest.mark.asyncio
async def test_runner_sends_nothing_while_switched_off():
    from app.bot.runner import AutonomousJobRunner
    uid = _uid()
    db.create_user(User(user_id=uid, email=f"{uid}@example.test", password_hash="x", role=UserRole.PRO))
    _profile(uid)
    job = JobListing(job_id=f"job_{uuid.uuid4().hex[:8]}", user_id=uid, fingerprint=uuid.uuid4().hex, platform="Greenhouse",
                     company="Acme", title="SDE", url="data:text/html,<form></form>")
    db.save_job(job, user_id=uid)
    res = await AutonomousJobRunner(mode="LIVE").execute_application(job_id=job.job_id, user_id=uid)
    assert res["status"] == "error" and res["submitted"] is False
    ledger = apply_ledger.get_ledger_for_job(uid, job.job_id)
    assert str(getattr(ledger.status, "value", ledger.status)) == ApplyLedgerStatus.FAILED.value


# --- In a browser (local pages only) ------------------------------------------------------------

playwright = pytest.importorskip("playwright.async_api", reason="Playwright not installed")


@pytest.mark.asyncio
async def test_required_questions_left_empty_are_reported():
    async with playwright.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content("""
          <form>
            <label for="n">Notice period *</label><input id="n" required>
            <label for="w">Website</label><input id="w">
            <input type="radio" name="relocate" value="yes" required aria-label="Willing to relocate?">
            <input type="radio" name="relocate" value="no">
            <input name="email" required value="a@example.test">
          </form>""")
        assert await missing_required(page) == ["Notice period", "Willing to relocate?"]
        await browser.close()


@pytest.mark.asyncio
async def test_fillers_use_the_users_answers_and_leave_the_rest_empty():
    from app.bot.adapters.greenhouse import GreenhouseAdapter
    uid = _uid()
    profile = _profile(uid, confirmed=["expected_ctc"], expected_ctc="28 LPA")
    profile.phone = ""
    async with playwright.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content("""
          <form>
            <input id="first_name"><input id="last_name"><input id="email"><input id="phone">
            <div class="field"><label>What is your expected CTC?</label><input type="text" name="q1"></div>
            <div class="field"><label>Why do you want to work at Acme?</label><textarea name="q2"></textarea></div>
          </form>""")
        filled = await GreenhouseAdapter.fill_application(page, profile, user_id=uid, company="Acme", role="SDE")
        assert await page.input_value("[name=q1]") == "28 LPA"
        assert await page.input_value("[name=q2]") == ""          # left for the user
        assert await page.input_value("#phone") == ""            # no phone on the profile, none typed
        assert "phone" not in filled
        await browser.close()


@pytest.mark.asyncio
async def test_live_run_with_an_unanswered_required_question_is_held_not_sent(monkeypatch):
    import app.bot.runner as runner_mod
    monkeypatch.setattr(runner_mod.settings, "LIVE_SUBMISSION_ENABLED", True)
    clicked = {"n": 0}

    async def never_confirm(self, page, url_before, timeout_s=10.0):
        clicked["n"] += 1
        return True

    monkeypatch.setattr(runner_mod.AutonomousJobRunner, "_detect_submission_confirmation", never_confirm)
    uid = _uid()
    db.create_user(User(user_id=uid, email=f"{uid}@example.test", password_hash="x", role=UserRole.PRO))
    _profile(uid)
    form = ("<form><label for='np'>Notice period</label><input id='np' required>"
            "<button type='submit'>Submit</button></form>")
    job = JobListing(job_id=f"job_{uuid.uuid4().hex[:8]}", user_id=uid, fingerprint=uuid.uuid4().hex, platform="Greenhouse",
                     company="Acme", title="SDE", url="data:text/html," + form)
    db.save_job(job, user_id=uid)

    res = await runner_mod.AutonomousJobRunner(mode="LIVE").execute_application(job_id=job.job_id, user_id=uid)

    assert res["status"] == "hitl_required" and res["submitted"] is False
    assert res["unanswered"] == ["Notice period"]
    assert clicked["n"] == 0                                   # submit was never pressed
    held = [e for e in db.get_pending_hitl(uid) if e.job_id == job.job_id]
    assert [e.question_text for e in held] == ["Notice period"]
    assert db.get_job_by_id(job.job_id, user_id=uid).status == ApplicationStatus.HITL_REQUIRED
