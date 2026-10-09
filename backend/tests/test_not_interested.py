"""
"Not interested because..." hides the job and teaches new searches what to skip.
"""

import asyncio
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token
from app.core import match_feedback
from app.core.database import db
from app.core.models import ApplicationStatus, CandidateProfile, JobListing, User, UserRole
from app.discovery.orchestrator import DiscoveryOrchestrator
from app.main import app

SKILLS = ["Python", "Go", "FastAPI", "PostgreSQL", "Redis", "Docker"]


@pytest.fixture
def user():
    u = User(user_id=f"usr_{uuid.uuid4().hex[:12]}", email=f"ni_{uuid.uuid4().hex[:8]}@test.com",
             password_hash="x", full_name="NI", role=UserRole.FREE, is_active=True)
    db.create_user(u)
    db.save_profile(CandidateProfile(id=u.user_id, user_id=u.user_id, full_name="N", email=u.email, phone="1",
                                     location="Pune, India", skills=SKILLS), user_id=u.user_id)
    yield u
    db.hard_delete_user_account(u.user_id)


def _client(u: User) -> TestClient:
    tc = TestClient(app)
    tc.headers["Authorization"] = "Bearer " + create_jwt_token(
        {"sub": u.user_id, "email": u.email, "role": "FREE", "type": "access"}, timedelta(minutes=30))
    return tc


def _job(u: User, **kw) -> JobListing:
    job = JobListing(job_id=f"job_{uuid.uuid4().hex[:12]}", user_id=u.user_id, fingerprint=uuid.uuid4().hex,
                     platform="Direct", company=kw.get("company", "Acme"), title=kw.get("title", "Backend Engineer"),
                     location=kw.get("location", "Remote"), url="https://acme.test/1",
                     salary_range=kw.get("salary"), status=ApplicationStatus.DISCOVERED)
    db.save_job(job, user_id=u.user_id)
    return job


@pytest.mark.parametrize("reason,fields,label", [
    ("seniority", {"title": "Staff Backend Engineer"}, "Staff roles"),
    ("location", {"location": "Bangalore, India"}, "On-site jobs in Bangalore"),
    ("field", {"title": "Senior Frontend Engineer (React)"}, "“Frontend Engineer” roles"),
    ("salary", {"salary": "10 - 16 LPA"}, "Jobs paying up to 16 LPA"),
    ("company", {"company": "Initech"}, "Jobs at Initech"),
])
def test_reason_hides_job_and_adds_rule(user, reason, fields, label):
    job = _job(user, **fields)
    tc = _client(user)
    res = tc.post(f"/api/jobs/{job.job_id}/not-interested", json={"reason": reason})
    assert res.status_code == 200
    assert res.json()["rule"]["label"] == label
    assert db.get_job_by_id(job.job_id, user_id=user.user_id).status == ApplicationStatus.DISMISSED
    rules = tc.get("/api/match-preferences").json()["rules"]
    assert [r["label"] for r in rules] == [label]


def test_vague_reasons_add_no_rule(user):
    tc = _client(user)
    for reason, fields in [("seniority", {"title": "Backend Engineer"}), ("location", {"location": "Remote"}),
                           ("salary", {"salary": None}), ("other", {})]:
        job = _job(user, **fields)
        body = tc.post(f"/api/jobs/{job.job_id}/not-interested", json={"reason": reason}).json()
        assert body["rule"] is None and body["note"]
    assert tc.get("/api/match-preferences").json()["rules"] == []
    assert tc.post(f"/api/jobs/{job.job_id}/not-interested", json={"reason": "bogus"}).status_code == 400


def test_new_searches_skip_and_removing_the_rule_brings_jobs_back(user, monkeypatch):
    leads = [{"company": "Globex", "title": "Staff Backend Engineer", "location": "Remote", "url": "https://g.test/1",
              "description": "Lead our payments platform in Go and Python with FastAPI, PostgreSQL, Redis and Docker."},
             {"company": "Acme", "title": "Backend Engineer", "location": "Remote", "url": "https://a.test/2",
              "description": "Python, Go, FastAPI, PostgreSQL, Redis, Docker."}]

    async def fetch(self, _companies):
        return [dict(lead) for lead in leads]

    monkeypatch.setattr(DiscoveryOrchestrator, "_fetch_all_raw_leads", fetch)
    tc = _client(user)
    rule = tc.post(f"/api/jobs/{_job(user, title='Staff Platform Engineer').job_id}/not-interested",
                   json={"reason": "seniority"}).json()["rule"]
    orch = DiscoveryOrchestrator(min_match_threshold=0.0)
    asyncio.run(orch.run_discovery_cycle(user_id=user.user_id))
    titles = {j.title for j in db.get_jobs(user_id=user.user_id) if j.status == ApplicationStatus.DISCOVERED}
    assert titles == {"Backend Engineer"}

    assert tc.delete(f"/api/match-preferences/{rule['id']}").json()["rules"] == []
    asyncio.run(orch.run_discovery_cycle(user_id=user.user_id))
    titles = {j.title for j in db.get_jobs(user_id=user.user_id) if j.status == ApplicationStatus.DISCOVERED}
    assert titles == {"Backend Engineer", "Staff Backend Engineer"}


def test_core_title_and_salary_parsing():
    assert match_feedback.core_title("Sr. Backend Engineer II - Payments") == "backend engineer"
    assert match_feedback.core_title("Junior Data Analyst (Remote)") == "data analyst"
    assert match_feedback.salary_max_lpa("28 - 45 LPA") == 45
    assert match_feedback.salary_max_lpa("$120k - $150k") is None
    rules = [match_feedback.rule_for("location", JobListing(job_id="j", fingerprint="f", platform="p", company="c",
                                                              title="t", location="Pune, India", url="u"))]
    assert match_feedback.skips(rules, "Engineer", "Pune, Maharashtra", "x", None)
    assert not match_feedback.skips(rules, "Engineer", "Remote (Pune)", "x", None)


def test_new_resume_keeps_skip_rules(user):
    tc = _client(user)
    tc.post(f"/api/jobs/{_job(user, company='Initech').job_id}/not-interested", json={"reason": "company"})
    resume = "Nia Rao\nnia@example.test\nBackend engineer. Skills: Python, Go, FastAPI, PostgreSQL, Redis, Docker, Kubernetes."
    assert tc.post("/api/upload-resume", data={"raw_text": resume}).status_code == 200
    assert [r["label"] for r in tc.get("/api/match-preferences").json()["rules"]] == ["Jobs at Initech"]
