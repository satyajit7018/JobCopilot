"""Audit regression tests for the apply pipeline (P1-1 to P1-4 and the ledger race)."""
import threading
import uuid

import pytest

from app.bot.apply_ledger import apply_ledger
from app.core.database import db
from app.core.models import (ApplyLedgerEntry, ApplyLedgerStatus, HITLEvent, JobListing, User, UserRole)


def _user(role=UserRole.FREE):
    uid = f"usr_{uuid.uuid4().hex[:10]}"
    db.create_user(User(user_id=uid, email=f"{uid}@t.test", password_hash="x", role=role))
    return uid


def _job(uid):
    job = JobListing(job_id=f"job_{uuid.uuid4().hex[:10]}", user_id=uid, fingerprint=f"fp_{uuid.uuid4().hex[:10]}",
                     platform="Greenhouse", company="Acme", title="SDE", url="https://acme.test/job")
    db.save_job(job, user_id=uid)
    return job


def _ledger(uid, job, status, attempts=1):
    e = ApplyLedgerEntry(ledger_id=f"ledger_{uuid.uuid4().hex[:10]}", user_id=uid, job_id=job.job_id,
                         job_fingerprint=job.fingerprint, status=status, attempt_count=attempts, max_retries=3,
                         idempotency_key=uuid.uuid4().hex, created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00")
    db.insert_ledger_if_absent(e, user_id=uid)
    return e


def test_failed_retry_has_exactly_one_winner():
    uid = _user(); job = _job(uid); _ledger(uid, job, ApplyLedgerStatus.FAILED)
    results, barrier = [], threading.Barrier(8)

    def worker():
        barrier.wait()
        ok, _, _ = apply_ledger.acquire_lock(user_id=uid, job_id=job.job_id, job_fingerprint=job.fingerprint)
        results.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert results.count(True) == 1


def test_mark_in_progress_is_single_use():
    uid = _user(); job = _job(uid); e = _ledger(uid, job, ApplyLedgerStatus.INITIATED)
    assert apply_ledger.mark_in_progress(e.ledger_id, uid) is True
    assert apply_ledger.mark_in_progress(e.ledger_id, uid) is False


def test_dry_run_release_allows_a_later_run():
    uid = _user(); job = _job(uid); e = _ledger(uid, job, ApplyLedgerStatus.INITIATED)
    assert apply_ledger.mark_in_progress(e.ledger_id, uid)
    assert apply_ledger.release_after_dry_run(e.ledger_id, uid)
    ok, _, _ = apply_ledger.acquire_lock(user_id=uid, job_id=job.job_id, job_fingerprint=job.fingerprint)
    assert ok


@pytest.mark.asyncio
async def test_runner_without_browser_never_marks_submitted(monkeypatch):
    import app.bot.runner as runner_mod
    from app.core.models import CandidateProfile
    uid = _user(); job = _job(uid)
    db.save_profile(CandidateProfile(id=uid, user_id=uid, full_name="T", email=f"{uid}@t.test", phone="1", location="X"), user_id=uid)
    monkeypatch.setattr(runner_mod, "HAS_PLAYWRIGHT", False)
    monkeypatch.setattr(runner_mod.settings, "LIVE_SUBMISSION_ENABLED", True)

    live = await runner_mod.AutonomousJobRunner(mode="LIVE").execute_application(job_id=job.job_id, user_id=uid)
    assert live["status"] == "error" and live["submitted"] is False
    assert str(getattr(db.get_job_by_id(job.job_id, user_id=uid).status, "value", "")) != "SUBMITTED"

    job2 = _job(uid)
    dry = await runner_mod.AutonomousJobRunner(mode="dry_run").execute_application(job_id=job2.job_id, user_id=uid)
    assert dry["submitted"] is False   # any non-LIVE mode is a dry run, never a submission
    led = apply_ledger.get_ledger_for_job(uid, job2.job_id)
    assert str(getattr(led.status, "value", led.status)) == "CANCELLED"


def test_resolve_held_requeues_instead_of_faking_submission(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.auth import start_session
    from app.core import celery_app as core_celery
    from app.main import app

    dispatched = {}
    monkeypatch.setattr(core_celery.TaskManager, "dispatch_apply_task",
                        classmethod(lambda cls, **kw: dispatched.update(kw) or "task_123"))
    uid = _user(UserRole.PRO); job = _job(uid); e = _ledger(uid, job, ApplyLedgerStatus.HITL_PAUSED)
    evt = HITLEvent(event_id=f"evt_{uuid.uuid4().hex[:8]}", job_id=job.job_id, company="Acme", role_title="SDE",
                    question_text="Notice period?", input_type="text", user_id=uid)
    db.save_hitl_event(evt, user_id=uid)
    access, _ = start_session(db.get_user_by_id(uid), "PRO", "127.0.0.1", "pytest")

    res = TestClient(app).post("/api/hitl/resolve-held", headers={"Authorization": f"Bearer {access}"},
                               json={"event_id": evt.event_id, "user_answer": "30 days", "save_to_vault": False})
    assert res.status_code == 200 and res.json()["task_id"] == "task_123"
    assert dispatched["ledger_id"] == e.ledger_id and dispatched["submission_mode"] == "DRY_RUN"
    assert str(getattr(db.get_job_by_id(job.job_id, user_id=uid).status, "value", "")) == "QUEUED"


def test_resolve_held_saves_the_answer_but_does_not_apply_for_someone_off_premium(monkeypatch):
    """Applying automatically is Premium. After leaving Premium, a held question can still be
    answered, but the paused application is not sent."""
    from fastapi.testclient import TestClient
    from app.api.auth import start_session
    from app.core import celery_app as core_celery
    from app.main import app

    dispatched = []
    monkeypatch.setattr(core_celery.TaskManager, "dispatch_apply_task",
                        classmethod(lambda cls, **kw: dispatched.append(kw) or "task_should_not_exist"))
    uid = _user(UserRole.FREE); job = _job(uid); e = _ledger(uid, job, ApplyLedgerStatus.HITL_PAUSED)
    evt = HITLEvent(event_id=f"evt_{uuid.uuid4().hex[:8]}", job_id=job.job_id, company="Acme", role_title="SDE",
                    question_text="Notice period?", input_type="text", user_id=uid)
    db.save_hitl_event(evt, user_id=uid)
    access, _ = start_session(db.get_user_by_id(uid), "FREE", "127.0.0.1", "pytest")

    res = TestClient(app).post("/api/hitl/resolve-held", headers={"Authorization": f"Bearer {access}"},
                               json={"event_id": evt.event_id, "user_answer": "30 days", "save_to_vault": False})
    assert res.status_code == 200 and res.json()["task_id"] is None
    assert dispatched == []
    led = apply_ledger.get_ledger_for_job(uid, job.job_id)
    assert led.ledger_id == e.ledger_id and str(getattr(led.status, "value", led.status)) == "HITL_PAUSED"
    assert str(getattr(db.get_job_by_id(job.job_id, user_id=uid).status, "value", "")) != "QUEUED"


@pytest.mark.parametrize("path", ["/api/bot/apply/{job}", "/api/jobs/apply-async/{job}", "/api/bot/apply-async/{job}"])
@pytest.mark.parametrize("mode", ["dry_run", "live", "LIVE ", "anything"])
def test_invalid_submission_mode_is_rejected_before_anything_runs(monkeypatch, path, mode):
    """Audit P1-2: only the exact values DRY_RUN and LIVE are accepted. Checked as a Premium user,
    so the answer comes from the mode check and not from the plan gate."""
    from fastapi.testclient import TestClient
    from app.api.auth import start_session
    from app.bot import runner as runner_mod
    from app.core import celery_app as core_celery
    from app.main import app

    ran = []
    monkeypatch.setattr(core_celery.TaskManager, "dispatch_apply_task",
                        classmethod(lambda cls, **kw: ran.append("dispatched") or "task_should_not_exist"))

    async def never(self, *a, **kw):
        ran.append("executed")
        return {"status": "error"}

    monkeypatch.setattr(runner_mod.AutonomousJobRunner, "execute_application", never)
    uid = _user(UserRole.PRO); job = _job(uid)
    access, _ = start_session(db.get_user_by_id(uid), "PRO", "127.0.0.1", "pytest")

    res = TestClient(app).post(path.format(job=job.job_id), params={"mode": mode}, headers={"Authorization": f"Bearer {access}"})
    assert res.status_code == 422, res.text
    assert ran == []
    assert apply_ledger.get_ledger_for_job(uid, job.job_id) is None
