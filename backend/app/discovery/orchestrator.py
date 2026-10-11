"""
JobCopilot - 0-Day Discovery Orchestrator & Background Poller
Orchestrates parallel ingestion across Greenhouse, Lever, Ashby, Y Combinator,
and HackerNews. Deduplicates, scores against CandidateProfile, ranks priority,
and persists discovered jobs to SQLite.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.database import db
from app.core.deduplicator import JobDeduplicator
from app.core import match_feedback
from app.core.match_scorer import MatchScorer
from app.core.models import ApplicationStatus, CandidateProfile, JobListing
from app.core.priority_ranker import PriorityRanker
from app.discovery.ats_apis import ATSApiFeeders
from app.discovery.vc_boards import VCBoardFeeders

logger = logging.getLogger(__name__)


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

    # Postings already scored for a user (saved or not) are remembered this long,
    # so hourly runs only score what's new.
    SEEN_TTL_SECONDS = 14 * 24 * 3600

    def __init__(self, min_match_threshold: float = 0.65):
        self.min_match_threshold = min_match_threshold
        # Listings shared by every user: (fetched_at monotonic seconds, leads).
        self._leads: Optional[tuple] = None
        # Created on first use, inside the running event loop.
        self._leads_lock: Optional[asyncio.Lock] = None
        self._all_users_running = False
        self.is_running = False
        self.last_run_at: Optional[str] = None
        self.total_discovered = 0
        self.total_matched = 0

    async def _fetch_all_raw_leads(self, target_companies: List[str]) -> List[Dict[str, Any]]:
        """Fetches real, current job openings from company career pages (ATS APIs) and startup boards."""
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
            tasks.append(VCBoardFeeders.fetch_yc_fast_track_jobs(client=client))
            tasks.append(VCBoardFeeders.fetch_hn_who_is_hiring(max_posts=15, client=client))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    raw_leads.extend(res)
        return raw_leads

    @staticmethod
    def _with_fingerprints(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adds each posting's fingerprint once, instead of once per user."""
        for lead in leads:
            lead["_fp"] = JobDeduplicator.generate_fingerprint(
                lead.get("company", "Company"), lead.get("title", ""),
                lead.get("location", "Remote"), lead.get("description", ""))
        return leads

    async def get_leads(self, max_age_seconds: float = 0) -> List[Dict[str, Any]]:
        """Postings from every source, reused if fetched within max_age_seconds."""
        import time
        if self._leads_lock is None:
            self._leads_lock = asyncio.Lock()
        async with self._leads_lock:
            if self._leads and max_age_seconds > 0 and time.monotonic() - self._leads[0] < max_age_seconds:
                return self._leads[1]
            raw = await self._fetch_all_raw_leads(self.CURATED_TECH_COMPANIES)
            leads = await asyncio.to_thread(self._with_fingerprints, raw)
            self._leads = (time.monotonic(), leads)
            self.total_discovered += len(leads)
            return leads

    @staticmethod
    async def _load_seen(user_id: str) -> set:
        from app.core.cache import cache_manager
        seen = await cache_manager.get(user_id, "discovery_seen", "fingerprints")
        return set(seen or [])

    async def _store_seen(self, user_id: str, seen: set) -> None:
        from app.core.cache import cache_manager
        await cache_manager.set(user_id, "discovery_seen", "fingerprints", sorted(seen), ttl_seconds=self.SEEN_TTL_SECONDS)

    def _score_and_save(
        self, raw_leads: List[Dict[str, Any]], profile: CandidateProfile, user_id: str,
        seen: Optional[set] = None,
    ) -> List[JobListing]:
        """Scores raw leads against the profile and saves the matches (blocking)."""
        saved_jobs: List[JobListing] = []
        blacklist = [c.lower() for c in profile.preferences.company_blacklist]
        skip_rules = profile.preferences.skip_rules
        target_user = user_id or getattr(profile, "user_id", "")
        # Jobs already in the user's list, by fingerprint. A posting found again must not
        # overwrite them: an application or a "Not interested" stays as the user left it.
        existing = {j.fingerprint: j for j in db.get_jobs(user_id=target_user)}

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
            # Skip what the user said they don't want ("Not interested because...").
            if skip_rules and match_feedback.skips(skip_rules, title, location, company, salary):
                continue

            fingerprint = lead.get("_fp") or JobDeduplicator.generate_fingerprint(company, title, location, desc)
            # Already in the user's list (applied, hidden, saved or a current match) or
            # already scored on an earlier run: nothing new to do.
            if fingerprint in existing or (seen is not None and fingerprint in seen):
                continue
            if seen is not None:
                seen.add(fingerprint)
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

        return saved_jobs

    async def run_discovery_cycle(
        self,
        profile: Optional[CandidateProfile] = None,
        companies: Optional[List[str]] = None,
        max_jobs_per_source: int = 50,
        user_id: str = "",
        max_lead_age_seconds: float = 0,
        leads: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Finds new matches for one user: fetch (or reuse) postings, score only new ones, save matches."""
        if not profile:
            if user_id:
                profile = db.get_profile(user_id=user_id)
            if not profile:
                return {"status": "error", "message": "No profile found. Please upload a resume first."}

        self.is_running = True
        self.last_run_at = datetime.now().isoformat()
        target_companies = companies or self.CURATED_TECH_COMPANIES

        try:
            if leads is not None:
                raw_leads = leads
            elif companies:
                raw_leads = self._with_fingerprints(await self._fetch_all_raw_leads(target_companies))
            else:
                raw_leads = await self.get_leads(max_lead_age_seconds)

            target_user = user_id or getattr(profile, "user_id", "")
            seen = await self._load_seen(target_user)
            # Scoring is CPU-heavy (thousands of postings on a first run) and the DB calls are
            # synchronous, so it runs in a worker thread to keep the event loop serving requests.
            saved_jobs = await asyncio.to_thread(self._score_and_save, raw_leads, profile, user_id, seen)
            await self._store_seen(target_user, seen)

            self.total_matched += len(saved_jobs)

            return {
                "status": "success",
                "total_sourced": len(raw_leads),
                "matched_and_saved": len(saved_jobs),
                "top_matches": [j.dict() for j in saved_jobs[:5]]
            }
        finally:
            self.is_running = False


    async def run_for_all_users(self, page_size: int = 200) -> Dict[str, Any]:
        """The hourly run: fetch postings once, then find new matches for every active user."""
        if self._all_users_running:
            return {"status": "skipped", "reason": "previous run still going"}
        self._all_users_running = True
        try:
            leads = await self.get_leads(0)
            users = matched = 0
            offset = 0
            while True:
                page = db.list_all_users(limit=page_size, offset=offset)
                if not page:
                    break
                offset += len(page)
                for row in page:
                    if not row.get("is_active", True):
                        continue
                    profile = db.get_profile(user_id=row["user_id"])
                    if not profile:
                        continue
                    try:
                        result = await self.run_discovery_cycle(profile, user_id=row["user_id"], leads=leads)
                    except Exception:
                        logger.exception("hourly discovery failed for user %s", row["user_id"])
                        continue
                    users += 1
                    matched += result.get("matched_and_saved", 0)
            logger.info("hourly discovery: %d postings, %d users, %d new matches", len(leads), users, matched)
            return {"status": "success", "postings": len(leads), "users": users, "new_matches": matched}
        finally:
            self._all_users_running = False


discovery_orchestrator = DiscoveryOrchestrator()
