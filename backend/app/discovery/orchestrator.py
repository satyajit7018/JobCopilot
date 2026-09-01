"""
JobCopilot - 0-Day Discovery Orchestrator & Background Poller
Orchestrates parallel ingestion across Greenhouse, Lever, Ashby, Y Combinator,
and HackerNews. Deduplicates, scores against CandidateProfile, ranks priority,
and persists discovered jobs to SQLite.
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx

from app.core.models import JobListing, ApplicationStatus, CandidateProfile
from app.core.database import db
from app.core.deduplicator import JobDeduplicator
from app.core.match_scorer import MatchScorer
from app.core.priority_ranker import PriorityRanker
from app.discovery.ats_apis import ATSApiFeeders
from app.discovery.vc_boards import VCBoardFeeders
from app.discovery.scrapers import PlatformScrapers


class DiscoveryOrchestrator:
    """Coordinates multi-source 0-day job discovery and matching."""

    CURATED_TECH_COMPANIES = [
        # Top Indian Unicorns & High-Scale Tech Employers
        "swiggy", "razorpay", "zepto", "cred", "phonepe",
        "browserstack", "postman", "meesho", "groww", "juspay",
        "zomato", "flipkart", "dream11", "inmobi", "sarvam-ai",
        # Global High-Growth Tech & YC Companies
        "stripe", "retool", "perplexity", "linear",
        "scale", "whatnot", "brex", "vercel",
        "supabase", "sentry", "datadog", "figma", "notion"
    ]

    def __init__(self, min_match_threshold: float = 0.60):
        self.min_match_threshold = min_match_threshold
        self.is_running = False
        self.last_run_at: Optional[str] = None
        self.total_discovered = 0
        self.total_matched = 0

    async def _fetch_all_raw_leads(self, target_companies: List[str]) -> List[Dict[str, Any]]:
        """Fetches raw job openings from Indian tech portals, ATS APIs, and VC feeds concurrently."""
        raw_leads: List[Dict[str, Any]] = []
        try:
            import h2  # type: ignore
            has_h2 = True
        except ImportError:
            has_h2 = False

        async with httpx.AsyncClient(http2=has_h2, timeout=10.0) as client:
            tasks = []
            for comp in target_companies:
                tasks.append(ATSApiFeeders.fetch_greenhouse_jobs(comp, client))
                tasks.append(ATSApiFeeders.fetch_lever_jobs(comp, client))
                tasks.append(ATSApiFeeders.fetch_ashby_jobs(comp, client))

            # VC & Fast-Track Boards
            tasks.append(VCBoardFeeders.fetch_yc_fast_track_jobs())
            tasks.append(VCBoardFeeders.fetch_hn_who_is_hiring(max_posts=15, client=client))

            # Indian Tech Portals & Startup Feeds (Prioritized)
            tasks.append(PlatformScrapers.fetch_naukri_india_feed("Software Engineer"))
            tasks.append(PlatformScrapers.fetch_instahyre_india_feed("Engineer"))
            tasks.append(PlatformScrapers.fetch_cuvette_india_feed("Engineer"))
            tasks.append(PlatformScrapers.fetch_cutshort_india_feed("Engineer"))
            tasks.append(PlatformScrapers.fetch_wellfound_mock_or_feed("Engineer"))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    raw_leads.extend(res)
        return raw_leads

    async def run_discovery_cycle(
        self,
        profile: Optional[CandidateProfile] = None,
        companies: Optional[List[str]] = None,
        max_jobs_per_source: int = 50,
        user_id: str = ""
    ) -> Dict[str, Any]:
        """Runs a complete parallel discovery cycle across all feeds for the user."""
        if not profile:
            if user_id:
                profile = db.get_profile(user_id=user_id)
            if not profile:
                return {"status": "error", "message": "No profile found. Please upload a resume first."}

        self.is_running = True
        self.last_run_at = datetime.now().isoformat()
        target_companies = companies or self.CURATED_TECH_COMPANIES

        try:
            raw_leads = await self._fetch_all_raw_leads(target_companies)
            self.total_discovered += len(raw_leads)

            # 2. Deduplicate, Blacklist Check, Score & Save
            saved_jobs: List[JobListing] = []
            blacklist = [c.lower() for c in profile.preferences.company_blacklist]

            for lead in raw_leads:
                company = lead.get("company", "Company")
                title = lead.get("title", "")
                location = lead.get("location", "Remote")
                url = lead.get("url", "")
                desc = lead.get("description", "")
                salary = lead.get("salary_range")

                # Check employer blacklist for stealth mode
                if any(b in company.lower() for b in blacklist if b):
                    continue

                # Compute Deduplication Fingerprint
                fingerprint = JobDeduplicator.generate_fingerprint(company, title, location, desc)
                # Compute Multi-Factor Match Score
                match_score, match_reasons, missing_skills = MatchScorer.compute_match_score(
                    profile=profile,
                    job_title=title,
                    job_description=desc,
                    job_location=location
                )

                # Filter by candidate match threshold
                if match_score >= self.min_match_threshold:
                    # Compute Priority Score (0-100) with Indian tech hub boost
                    priority_score = PriorityRanker.calculate_priority_score(
                        match_score=match_score,
                        platform=lead.get("platform", "Direct"),
                        company=company,
                        freshness_days=1,
                        salary_range=salary,
                        candidate_expected_ctc=profile.preferences.expected_ctc,
                        location=location
                    )

                    target_user = user_id or getattr(profile, "user_id", "")
                    job = JobListing(
                        job_id=f"job_{uuid.uuid4().hex[:12]}",
                        user_id=target_user,
                        fingerprint=fingerprint,
                        platform=lead.get("platform", "Direct"),
                        company=company,
                        title=title,
                        location=location,
                        url=url,
                        description=desc[:1500],
                        salary_range=salary,
                        seniority_level=MatchScorer.infer_job_seniority(title, desc),
                        match_score=match_score,
                        priority_score=priority_score,
                        match_reasons=match_reasons,
                        missing_skills=missing_skills,
                        status=ApplicationStatus.DISCOVERED
                    )

                    # Persist to Multi-Tenant DB
                    if db.save_job(job, user_id=target_user):
                        saved_jobs.append(job)

            self.total_matched += len(saved_jobs)

            return {
                "status": "success",
                "total_sourced": len(raw_leads),
                "matched_and_saved": len(saved_jobs),
                "top_matches": [j.dict() for j in saved_jobs[:5]]
            }
        finally:
            self.is_running = False


discovery_orchestrator = DiscoveryOrchestrator()
