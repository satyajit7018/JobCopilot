"""
JobCopilot - Job Platform Scrapers & Query Aggregators
Targeted query generators and scrapers for Wellfound (AngelList),
Indeed, and Naukri with skill-targeted filtering.
"""

import re
import asyncio
from typing import List, Dict, Any, Optional
import httpx


class PlatformScrapers:
    """Targeted search and feed scraper for Wellfound, Indeed, and Naukri."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html"
    }

    @classmethod
    def build_targeted_query(cls, skills: List[str], target_title: str = "Software Engineer", location: str = "Remote") -> Dict[str, str]:
        """Generates boolean search queries optimized for job platform search engines."""
        top_skills = skills[:4] if skills else ["Python", "FastAPI"]
        skills_clause = " OR ".join([f'"{s}"' for s in top_skills])
        query_string = f'"{target_title}" ({skills_clause})'

        return {
            "query": query_string,
            "title": target_title,
            "location": location,
            "naukri_url": f"https://www.naukri.com/{target_title.lower().replace(' ', '-')}-jobs-in-{location.lower()}",
            "indeed_url": f"https://www.indeed.com/jobs?q={query_string.replace(' ', '+')}&l={location.replace(' ', '+')}",
            "wellfound_url": f"https://wellfound.com/jobs?query={target_title.replace(' ', '+')}&location={location.replace(' ', '+')}"
        }

    @classmethod
    async def fetch_wellfound_mock_or_feed(cls, keyword: str = "Engineer") -> List[Dict[str, Any]]:
        """Parses curated Wellfound startup job listings."""
        sample_wellfound_leads = [
            {
                "external_id": "wf_101",
                "platform": "Wellfound",
                "company": "Kudo Health",
                "title": "Full Stack AI Engineer",
                "location": "Remote",
                "url": "https://wellfound.com/company/kudo-health/jobs/full-stack-ai-engineer",
                "description": "Building diagnostic AI copilots for clinics using Python, FastAPI, React, and PyTorch.",
                "salary_range": "$120k - $160k · 0.25% - 0.5%",
                "posted_date": "2026-08-28"
            },
            {
                "external_id": "wf_102",
                "platform": "Wellfound",
                "company": "Cognition Labs",
                "title": "AI Systems Engineer",
                "location": "San Francisco, CA (Remote)",
                "url": "https://wellfound.com/company/cognition-labs/jobs/ai-systems-engineer",
                "description": "Architecting autonomous coding agents with low-latency LLM evaluation pipelines.",
                "salary_range": "$180k - $250k · 0.1% - 0.3%",
                "posted_date": "2026-08-29"
            },
            {
                "external_id": "wf_103",
                "platform": "Wellfound",
                "company": "Vectorflow",
                "title": "Backend Distributed Systems Engineer",
                "location": "Bangalore / Remote",
                "url": "https://wellfound.com/company/vectorflow/jobs/backend-engineer",
                "description": "Developing real-time streaming vector indexing with Rust, Python, and Redis.",
                "salary_range": "25 - 40 LPA · 0.5%",
                "posted_date": "2026-08-29"
            }
        ]
        return sample_wellfound_leads
