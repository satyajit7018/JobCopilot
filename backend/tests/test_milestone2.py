"""
JobCopilot - Milestone 2 End-to-End Test Suite
Tests 0-Day ATS APIs, VC portfolio boards, 64-bit SimHash deduplication,
multi-factor match scoring, priority queue ranking, and discovery orchestration.
"""

import sys
from pathlib import Path
import pytest
import asyncio

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.core.models import CandidateProfile, RecruiterPreferences, JobListing
from app.core.database import DatabaseManager
from app.core.deduplicator import JobDeduplicator
from app.core.match_scorer import MatchScorer
from app.core.priority_ranker import PriorityRanker
from app.discovery.ats_apis import ATSApiFeeders
from app.discovery.vc_boards import VCBoardFeeders
from app.discovery.scrapers import PlatformScrapers
from app.discovery.orchestrator import DiscoveryOrchestrator


class TestMilestone2:

    @pytest.fixture(autouse=True)
    def setup_profile_and_db(self, tmp_path):
        self.db_path = tmp_path / "test_m2.db"
        self.db = DatabaseManager(self.db_path)
        self.profile = CandidateProfile(
            full_name="Satyajit Nayak",
            email="scorpionsatyajit@gmail.com",
            phone="+91 7008053476",
            location="Bangalore, India",
            skills=["Python", "FastAPI", "PyTorch", "Docker", "PostgreSQL", "Redis"],
            preferences=RecruiterPreferences(
                expected_ctc="20 LPA",
                years_of_experience=2.5,
                remote_preference="Remote / Hybrid",
                company_blacklist=["BannedCorp"]
            )
        )

    # 1. Test ATS API HTML Cleaning
    def test_ats_html_cleaning(self):
        raw_html = "<div><p>Looking for a <strong>Senior Backend Developer</strong></p> &amp; AI Engineer</div>"
        cleaned = ATSApiFeeders._clean_html(raw_html)
        assert cleaned == "Looking for a Senior Backend Developer & AI Engineer"

    # 2. Test HackerNews Comment Parser
    def test_hn_who_is_hiring_parser(self):
        sample = """
        Perplexity AI | AI Research Engineer | San Francisco, CA | REMOTE | $190k - $250k
        Building high-speed real-time conversational search engines.
        Apply at: https://jobs.ashbyhq.com/perplexity
        """
        parsed = VCBoardFeeders._parse_hn_comment(sample, 998877)
        assert parsed is not None
        assert parsed["company"] == "Perplexity AI"
        assert "Engineer" in parsed["title"]
        assert "Remote" in parsed["location"]
        assert parsed["salary_range"] is not None and "190k" in parsed["salary_range"]

    # 3. Test Scraper Query Builder
    def test_platform_scraper_query_builder(self):
        q = PlatformScrapers.build_targeted_query(self.profile.skills, "AI Engineer", "Remote")
        assert "Python" in q["query"]
        assert "indeed.com" in q["indeed_url"]

    # 4. Test Entity Normalization & 64-bit SimHash
    def test_deduplication_and_simhash(self):
        c1 = JobDeduplicator.normalize_company("Stripe (YC S09), Inc.")
        c2 = JobDeduplicator.normalize_company("Stripe LLC")
        assert c1 == c2 == "stripe"

        t1 = JobDeduplicator.normalize_title("Sr. Software Engineer - Backend (Remote)")
        t2 = JobDeduplicator.normalize_title("Senior Software Engineer Back End")
        assert t1 == t2

        desc1 = "We are seeking a senior backend software engineer with deep Python, FastAPI, and PyTorch experience to design low latency microservices."
        desc2 = "We are seeking a senior backend software engineer with deep Python, FastAPI, and PyTorch experience to design low latency microservices. Apply directly on our website."
        h1 = JobDeduplicator.compute_simhash_64(desc1)
        h2 = JobDeduplicator.compute_simhash_64(desc2)
        dist = JobDeduplicator.hamming_distance(h1, h2)
        assert dist <= 8

        is_dup = JobDeduplicator.is_duplicate(
            "Stripe (YC S09), Inc.", "Sr. SWE - Backend", desc1,
            "Stripe LLC", "Senior Software Engineer Back End", desc2
        )
        assert is_dup is True

    # 5. Test Multi-Factor Match Scorer
    def test_match_scorer(self):
        ai_jd = """
        We need a Python / FastAPI developer with PyTorch model deployment skills and Docker experience.
        """
        score_ai, reasons_ai, _ = MatchScorer.compute_match_score(
            self.profile, "AI Systems Engineer", ai_jd, job_location="Bangalore / Remote"
        )
        assert score_ai >= 0.70
        assert len(reasons_ai) >= 2

        chef_jd = "Pastry chef and culinary manager with 5 years bakery experience."
        score_chef, _, _ = MatchScorer.compute_match_score(self.profile, "Head Chef", chef_jd)
        assert score_chef <= 0.20

    # 6. Test Priority Ranker
    def test_priority_ranker(self):
        p_high = PriorityRanker.calculate_priority_score(
            match_score=0.90,
            platform="Y Combinator",
            company="Perplexity",
            freshness_days=1,
            salary_range="$180k - $220k",
            candidate_expected_ctc="20 LPA"
        )
        p_low = PriorityRanker.calculate_priority_score(
            match_score=0.30,
            platform="Indeed",
            company="LegacyCo",
            freshness_days=15
        )
        assert p_high >= 85.0
        assert p_low <= 40.0
        assert p_high > p_low

    # 7. Test Discovery Orchestrator Mock Ingestion
    @pytest.mark.asyncio
    async def test_discovery_orchestrator(self):
        orch = DiscoveryOrchestrator(min_match_threshold=0.50)
        result = await orch.run_discovery_cycle(
            profile=self.profile,
            companies=["linear", "perplexity"]
        )
        assert result["status"] == "success"
        assert result["total_sourced"] > 0
