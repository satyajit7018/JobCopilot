"""
JobCopilot - Indian job sites: search links, priority ranking, and the rule that
discovery only ever shows postings it really read (no built-in sample listings).
"""

import uuid
import pytest
from app.discovery.scrapers import PlatformScrapers
from app.discovery.orchestrator import DiscoveryOrchestrator
from app.core.priority_ranker import PriorityRanker
from app.core.models import CandidateProfile, RecruiterPreferences, ApplicationStatus
from app.core.database import db


def test_search_links_for_indian_job_sites():
    """Search links are built for sites we don't read ourselves."""
    # 1. Query Builder
    query = PlatformScrapers.build_targeted_query(
        skills=["Python", "FastAPI", "PostgreSQL", "Kafka"],
        target_title="Backend Engineer",
        location="Bangalore"
    )
    assert "naukri.com/backend-engineer-jobs-in-bangalore" in query["naukri_url"]
    assert "instahyre.com/search-jobs" in query["instahyre_url"]
    assert "cuvette.tech/app/jobs" in query["cuvette_url"]
    assert "cutshort.io/jobs/backend-engineer-jobs-in-bangalore" in query["cutshort_url"]
    assert "hirist.tech/k/backend-engineer-jobs-in-bangalore.html" in query["hirist_url"]


def test_indian_job_priority_ranking():
    """Validates that Indian tech platforms and Indian tech hub locations receive top priority scores."""
    # Test Naukri Tier 1 scoring
    score_naukri = PriorityRanker.calculate_priority_score(
        match_score=0.90,
        platform="Naukri",
        company="Swiggy",
        freshness_days=1,
        salary_range="30 - 45 LPA",
        candidate_expected_ctc="20 LPA",
        location="Bangalore, India"
    )
    assert score_naukri >= 90.0  # High match + Tier 1 Indian portal + LPA alignment + Bangalore boost

    # Test Instahyre Tier 1 scoring
    score_insta = PriorityRanker.calculate_priority_score(
        match_score=0.85,
        platform="Instahyre",
        company="Razorpay",
        freshness_days=1,
        salary_range="32 - 50 LPA",
        candidate_expected_ctc="25 LPA",
        location="Bangalore"
    )
    assert score_insta >= 88.0

    # Test Cuvette Tier 1 scoring
    score_cuv = PriorityRanker.calculate_priority_score(
        match_score=0.80,
        platform="Cuvette",
        company="Sarvam AI",
        freshness_days=1,
        salary_range="20 - 35 LPA",
        candidate_expected_ctc="18 LPA",
        location="Hyderabad"
    )
    assert score_cuv >= 80.0


REAL_LEAD = {
    "external_id": "gh_real_1",
    "platform": "Greenhouse",
    "company": "Razorpay",
    "title": "Backend Engineer",
    "location": "Bangalore, India",
    "url": "https://job-boards.greenhouse.io/razorpay/jobs/1",
    "description": "Build payment services in Python, FastAPI, Kafka, PostgreSQL and Redis.",
    "posted_date": None,
}


def _only_real_sources(monkeypatch, leads):
    """Stands in for the network: every real source answers with `leads` (or nothing)."""
    from app.discovery.ats_apis import ATSApiFeeders
    from app.discovery.vc_boards import VCBoardFeeders

    first = {"sent": False}

    async def greenhouse(cls, slug, client=None):
        if first["sent"]:
            return []
        first["sent"] = True
        return [dict(lead) for lead in leads]

    async def nothing(cls, *args, **kwargs):
        return []

    monkeypatch.setattr(ATSApiFeeders, "fetch_greenhouse_jobs", classmethod(greenhouse))
    monkeypatch.setattr(ATSApiFeeders, "fetch_lever_jobs", classmethod(nothing))
    monkeypatch.setattr(ATSApiFeeders, "fetch_ashby_jobs", classmethod(nothing))
    monkeypatch.setattr(VCBoardFeeders, "fetch_yc_fast_track_jobs", classmethod(nothing))
    monkeypatch.setattr(VCBoardFeeders, "fetch_hn_who_is_hiring", classmethod(nothing))


@pytest.mark.asyncio
async def test_discovery_invents_nothing_when_sources_are_empty(monkeypatch):
    """No postings read means no postings shown: there are no built-in sample jobs."""
    _only_real_sources(monkeypatch, [])
    orch = DiscoveryOrchestrator(min_match_threshold=0.45)
    assert await orch._fetch_all_raw_leads(["razorpay", "swiggy"]) == []


@pytest.mark.asyncio
async def test_discovery_only_saves_postings_it_really_read(monkeypatch):
    _only_real_sources(monkeypatch, [REAL_LEAD])
    test_uid = f"usr_india_test_{uuid.uuid4().hex[:8]}"
    profile = CandidateProfile(
        user_id=test_uid,
        full_name="Arjun Sharma",
        email="arjun.sharma@example.in",
        phone="+91 9876543210",
        location="Bangalore, India",
        skills=["Python", "FastAPI", "Kafka", "PostgreSQL", "Redis", "Go", "Distributed Systems"],
        target_roles=["Backend Engineer", "Software Engineer", "SDE-2"],
        preferences=RecruiterPreferences(expected_ctc="25 LPA", current_ctc="18 LPA", notice_period_days=30),
    )
    db.save_profile(profile, user_id=test_uid)

    orch = DiscoveryOrchestrator(min_match_threshold=0.45)
    res = await orch.run_discovery_cycle(profile=profile, user_id=test_uid)

    assert res["status"] == "success"
    assert res["total_sourced"] == 1
    saved = db.get_jobs(status=ApplicationStatus.DISCOVERED, user_id=test_uid)
    assert [j.url for j in saved] == [REAL_LEAD["url"]]
    assert not {j.platform for j in saved} & {"Naukri", "Instahyre", "Cuvette", "Cutshort", "Wellfound"}


def test_sample_feeds_are_gone():
    for name in ("fetch_naukri_india_feed", "fetch_instahyre_india_feed", "fetch_cuvette_india_feed",
                 "fetch_cutshort_india_feed", "fetch_wellfound_mock_or_feed"):
        assert not hasattr(PlatformScrapers, name)
