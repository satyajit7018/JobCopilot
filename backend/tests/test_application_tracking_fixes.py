"""
Application-tracking fixes:
- PATCH /api/jobs/{id}/interview sets or clears the interview date.
- The follow-up draft only says "last week" when that is true.
- The admin "applications" metric counts applied jobs, including ones the
  user marked by hand (it used to read only bot-submitted ledger rows).
"""

import uuid
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token
from app.core.database import DatabaseManager, db
from app.core.models import ApplicationStatus, CandidateProfile, JobListing, User, UserRole
from app.email.followup import FollowUpEngine
from app.main import app


def _user_client():
    user = User(
        user_id=f"usr_{uuid.uuid4().hex[:12]}",
        email=f"tracking_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="test_hash",
        full_name="Tracking Test",
        role=UserRole.FREE,
        is_active=True,
    )
    db.create_user(user)
    token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": "FREE", "type": "access"},
        timedelta(minutes=60),
    )
    tc = TestClient(app)
    tc.headers["Authorization"] = f"Bearer {token}"
    return user, tc


def _job(user_id: str, status=ApplicationStatus.INTERVIEW, applied_at=None) -> JobListing:
    job = JobListing(
        job_id=f"job_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        fingerprint=uuid.uuid4().hex,
        platform="Greenhouse",
        company="Acme",
        title="Backend Engineer",
        url="https://example.com/jobs/1",
        status=status,
        applied_at=applied_at,
    )
    db.save_job(job, user_id=user_id)
    return job


def _stored(job: JobListing) -> JobListing:
    return db.get_job_by_id(job.job_id, user_id=job.user_id)


def test_set_and_clear_interview_date():
    user, tc = _user_client()
    try:
        job = _job(user.user_id)
        when = "2026-11-03T10:30:00.000Z"

        res = tc.patch(f"/api/jobs/{job.job_id}/interview", json={"interview_date": when})
        assert res.status_code == 200
        assert res.json()["interview_date"] == when
        assert _stored(job).interview_date == when
        listed = {j["job_id"]: j for j in tc.get("/api/jobs").json()["jobs"]}
        assert listed[job.job_id]["interview_date"] == when

        res = tc.patch(f"/api/jobs/{job.job_id}/interview", json={"interview_date": None})
        assert res.status_code == 200
        assert _stored(job).interview_date is None
    finally:
        db.hard_delete_user_account(user.user_id)


def test_interview_date_validation_and_tenant_isolation():
    owner, owner_tc = _user_client()
    other, other_tc = _user_client()
    try:
        job = _job(owner.user_id)
        res = owner_tc.patch(f"/api/jobs/{job.job_id}/interview", json={"interview_date": "next tuesday"})
        assert res.status_code == 400

        res = other_tc.patch(f"/api/jobs/{job.job_id}/interview", json={"interview_date": "2026-11-03T10:30:00Z"})
        assert res.status_code == 404
        assert _stored(job).interview_date is None
    finally:
        db.hard_delete_user_account(owner.user_id)
        db.hard_delete_user_account(other.user_id)


def test_followup_wording_matches_the_application_date():
    now = datetime(2026, 10, 9, 12, 0)

    def when(applied_at):
        job = JobListing(job_id="j", fingerprint="f", platform="x", company="Acme", title="Engineer", url="u", applied_at=applied_at)
        return FollowUpEngine._submitted_when(job, now=now)

    assert when(None) == ""
    assert when("not a date") == ""
    assert when("2026-10-01T09:00:00") == " submitted last week"
    assert when("2026-10-07T09:00:00") == " submitted on 7 October"
    assert when("2026-09-20T09:00:00") == " submitted on 20 September"

    profile = CandidateProfile(full_name="T", email="t@example.com", phone="0", location="Remote")
    job = JobListing(job_id="j", fingerprint="f", platform="x", company="Acme", title="Engineer", url="u")
    body = FollowUpEngine.generate_followup_email(profile, job, stage_days=7)["body"]
    assert "last week" not in body
    assert "my application for the Engineer position at Acme" in body


def test_admin_metric_counts_applied_jobs(tmp_path):
    # Own database: the suite runs in parallel, so the shared one changes under us.
    isolated = DatabaseManager(db_path=tmp_path / "metrics.db")
    for status in (ApplicationStatus.DISCOVERED, ApplicationStatus.SUBMITTED, ApplicationStatus.INTERVIEW):
        job = JobListing(
            job_id=f"job_{uuid.uuid4().hex[:12]}",
            fingerprint=uuid.uuid4().hex,
            platform="Greenhouse",
            company="Acme",
            title="Backend Engineer",
            url="https://example.com/jobs/1",
            status=status,
        )
        isolated.save_job(job, user_id="usr_metrics")
    assert isolated.get_admin_system_metrics()["total_applications"] == 2
