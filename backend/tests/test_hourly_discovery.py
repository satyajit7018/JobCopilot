"""
Fresh matches every hour, without re-doing work.

Postings are fetched once per run and shared by every user; each user only has
postings scored that they haven't seen. A changed profile resets that memory.
A manual "Find new jobs" is spaced 15 minutes apart and reuses recent postings.
"""

import asyncio
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token
from app.core.database import db
from app.core.match_scorer import MatchScorer
from app.core.models import CandidateProfile, User, UserRole
from app.discovery.orchestrator import DiscoveryOrchestrator
from app.main import app

SKILLS = ["Python", "Go", "FastAPI", "PostgreSQL", "Redis", "Docker", "Kubernetes", "AWS"]


def _lead(n: int) -> dict:
    return {"company": f"Acme {n}", "title": "Backend Engineer", "location": "Remote", "url": f"https://acme.test/{n}",
            "description": "Python, Go, FastAPI, PostgreSQL, Redis, Docker, Kubernetes on AWS."}


def _user_with_profile() -> User:
    user = User(user_id=f"usr_{uuid.uuid4().hex[:12]}", email=f"hourly_{uuid.uuid4().hex[:8]}@test.com",
                password_hash="x", full_name="Hourly", role=UserRole.FREE, is_active=True)
    db.create_user(user)
    db.save_profile(CandidateProfile(id=user.user_id, user_id=user.user_id, full_name="H", email=user.email,
                                     phone="1", location="Pune, India", skills=SKILLS), user_id=user.user_id)
    return user


@pytest.fixture
def feeds(monkeypatch):
    """Fake postings source that counts fetches; tests add postings to state["leads"]."""
    state = {"fetches": 0, "leads": [_lead(1), _lead(2)]}

    async def fetch(self, _companies):
        state["fetches"] += 1
        return [dict(lead) for lead in state["leads"]]

    monkeypatch.setattr(DiscoveryOrchestrator, "_fetch_all_raw_leads", fetch)
    return state


def test_hourly_run_fetches_once_for_everyone(feeds):
    users = [_user_with_profile() for _ in range(3)]
    try:
        result = asyncio.run(DiscoveryOrchestrator(min_match_threshold=0.0).run_for_all_users())
        assert feeds["fetches"] == 1
        assert result["status"] == "success"
        for u in users:
            assert len(db.get_jobs(user_id=u.user_id)) == 2
    finally:
        for u in users:
            db.hard_delete_user_account(u.user_id)


def test_only_new_postings_are_scored(feeds, monkeypatch):
    user = _user_with_profile()
    calls = []
    real = MatchScorer.compute_match_score.__func__

    def counting(cls, **kwargs):
        calls.append(kwargs["job_title"])
        return real(cls, **kwargs)

    monkeypatch.setattr(MatchScorer, "compute_match_score", classmethod(counting))
    orch = DiscoveryOrchestrator(min_match_threshold=0.99)  # nothing saved: "seen" alone must stop re-scoring
    profile = db.get_profile(user_id=user.user_id)
    try:
        asyncio.run(orch.run_discovery_cycle(profile, user_id=user.user_id))
        assert len(calls) == 2
        feeds["leads"].append(_lead(3))
        asyncio.run(orch.run_discovery_cycle(profile, user_id=user.user_id))
        assert len(calls) == 3, "only the new posting is scored on the second run"
    finally:
        db.hard_delete_user_account(user.user_id)


def _client(user: User) -> TestClient:
    tc = TestClient(app)
    token = create_jwt_token({"sub": user.user_id, "email": user.email, "role": "FREE", "type": "access"}, timedelta(minutes=30))
    tc.headers["Authorization"] = f"Bearer {token}"
    return tc


def test_profile_change_rechecks_old_postings(feeds):
    from app.core.cache import cache_manager

    user = _user_with_profile()
    orch = DiscoveryOrchestrator(min_match_threshold=0.99)
    try:
        asyncio.run(orch.run_discovery_cycle(db.get_profile(user_id=user.user_id), user_id=user.user_id))
        assert asyncio.run(cache_manager.get(user.user_id, "discovery_seen", "fingerprints"))
        res = _client(user).put("/api/profile/background", json={"skills": ["Rust"], "experience": [], "education": []})
        assert res.status_code == 200
        assert not asyncio.run(cache_manager.get(user.user_id, "discovery_seen", "fingerprints"))
    finally:
        db.hard_delete_user_account(user.user_id)


def test_manual_search_cooldown(feeds):
    user = _user_with_profile()
    tc = _client(user)
    try:
        first = tc.post("/api/discovery/run")
        assert first.status_code == 200
        second = tc.post("/api/discovery/run")
        assert second.status_code == 429
        assert "every hour" in second.json()["detail"]
    finally:
        db.hard_delete_user_account(user.user_id)


def test_recent_postings_are_reused(feeds):
    orch = DiscoveryOrchestrator()
    asyncio.run(orch.get_leads(3600))
    asyncio.run(orch.get_leads(3600))
    assert feeds["fetches"] == 1
    asyncio.run(orch.get_leads(0))
    assert feeds["fetches"] == 2


def test_saved_jobs_are_left_alone_by_new_searches(feeds):
    from app.core.models import ApplicationStatus

    user = _user_with_profile()
    tc = _client(user)
    orch = DiscoveryOrchestrator(min_match_threshold=0.0)
    try:
        asyncio.run(orch.run_discovery_cycle(db.get_profile(user_id=user.user_id), user_id=user.user_id))
        job = db.get_jobs(user_id=user.user_id)[0]
        assert tc.patch(f"/api/jobs/{job.job_id}/status", json={"status": "SAVED"}).status_code == 200
        from app.core.cache import cache_manager
        asyncio.run(cache_manager.invalidate_namespace(user.user_id, "discovery_seen"))  # force a full re-check
        asyncio.run(orch.run_discovery_cycle(db.get_profile(user_id=user.user_id), user_id=user.user_id))
        after = db.get_job_by_id(job.job_id, user_id=user.user_id)
        assert after.status == ApplicationStatus.SAVED
        assert after.applied_at is None  # saving isn't applying
        assert len(db.get_jobs(user_id=user.user_id)) == 2
    finally:
        db.hard_delete_user_account(user.user_id)
