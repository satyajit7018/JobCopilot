"""
JobCopilot - Indian Tech Job Portals & Priority Ingestion Test Suite
Validates Naukri, Instahyre, Cuvette, Cutshort, and Hirist scrapers,
query generators, LPA compensation parsing, and priority ranking.
"""

import pytest
from app.discovery.scrapers import PlatformScrapers
from app.discovery.orchestrator import DiscoveryOrchestrator
from app.core.priority_ranker import PriorityRanker
from app.core.models import CandidateProfile, RecruiterPreferences, ApplicationStatus
from app.core.database import db


@pytest.mark.asyncio
async def test_indian_job_platform_scrapers_and_queries():
    """Validates boolean query builders and structured feeds for Indian job portals."""
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

    # 2. Naukri Feed
    naukri_leads = await PlatformScrapers.fetch_naukri_india_feed()
    assert len(naukri_leads) >= 4
    for lead in naukri_leads:
        assert lead["platform"] == "Naukri"
        assert "LPA" in lead["salary_range"]
        assert any(hub in lead["location"] for hub in ["Bangalore", "Bengaluru", "Mumbai", "Pune", "Gurgaon", "Gurugram"])

    # 3. Instahyre Feed
    insta_leads = await PlatformScrapers.fetch_instahyre_india_feed()
    assert len(insta_leads) >= 4
    for lead in insta_leads:
        assert lead["platform"] == "Instahyre"
        assert lead["company"] in ["Razorpay", "Cred", "BrowserStack", "Groww"]
        assert "LPA" in lead["salary_range"]

    # 4. Cuvette Feed
    cuv_leads = await PlatformScrapers.fetch_cuvette_india_feed()
    assert len(cuv_leads) >= 3
    for lead in cuv_leads:
        assert lead["platform"] == "Cuvette"
        assert "LPA" in lead["salary_range"]

    # 5. Cutshort Feed
    cut_leads = await PlatformScrapers.fetch_cutshort_india_feed()
    assert len(cut_leads) >= 2
    for lead in cut_leads:
        assert lead["platform"] == "Cutshort"
        assert "LPA" in lead["salary_range"]


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


@pytest.mark.asyncio
async def test_discovery_orchestrator_indian_jobs_ingestion():
    """Validates that the Discovery Orchestrator ingests and saves Indian tech leads."""
    test_uid = "usr_india_test_99"
    profile = CandidateProfile(
        user_id=test_uid,
        full_name="Arjun Sharma",
        email="arjun.sharma@example.in",
        phone="+91 9876543210",
        location="Bangalore, India",
        skills=["Python", "FastAPI", "Kafka", "PostgreSQL", "Redis", "Go", "Distributed Systems"],
        target_roles=["Backend Engineer", "Software Engineer", "SDE-2"],
        preferences=RecruiterPreferences(
            expected_ctc="25 LPA",
            current_ctc="18 LPA",
            notice_period_days=30,
            remote_preference="Remote / Hybrid",
            willing_to_relocate=True,
            company_blacklist=[]
        )
    )
    db.save_profile(profile, user_id=test_uid)

    orch = DiscoveryOrchestrator(min_match_threshold=0.45)
    res = await orch.run_discovery_cycle(profile=profile, user_id=test_uid)

    assert res["status"] == "success"
    assert res["total_sourced"] > 10
    assert res["matched_and_saved"] > 0

    # Verify jobs saved in database for user
    user_jobs = db.get_jobs(status=ApplicationStatus.DISCOVERED, user_id=test_uid)
    indian_platforms = {j.platform for j in user_jobs}
    # Check that at least some Indian portals were ingested and saved
    assert any(p in indian_platforms for p in ["Naukri", "Instahyre", "Cuvette", "Cutshort", "Wellfound"])
