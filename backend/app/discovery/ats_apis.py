"""
JobCopilot - Direct ATS REST API Feeders
High-throughput, asynchronous ingestion for Greenhouse, Lever, and Ashby job boards.
Extracts 0-day openings directly from public JSON APIs in < 150ms per company.
"""

import re
import html
import asyncio
from typing import List, Dict, Any, Optional
import httpx

from app.core.models import JobListing, ApplicationStatus

try:
    import h2
    HAS_H2 = True
except ImportError:
    HAS_H2 = False


class ATSApiFeeders:
    """Fetches real-time job listings directly from ATS public REST APIs."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    @staticmethod
    def _clean_html(html_text: str) -> str:
        """Strips HTML tags and unescapes entities into clean text."""
        if not html_text:
            return ""
        unescaped = html.unescape(html_text)
        cleaned = re.sub(r'<[^>]+>', ' ', unescaped)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    @classmethod
    async def fetch_greenhouse_jobs(cls, company_slug: str, client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
        """
        Fetches job postings from Greenhouse API:
        https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true
        """
        url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
        jobs = []

        async def _fetch(c: httpx.AsyncClient):
            try:
                res = await c.get(url, headers=cls.HEADERS, timeout=8.0)
                if res.status_code == 200:
                    data = res.json()
                    raw_jobs = data.get("jobs", [])
                    for rj in raw_jobs:
                        title = rj.get("title", "").strip()
                        location = rj.get("location", {}).get("name", "Remote")
                        job_url = rj.get("absolute_url", "")
                        job_id = str(rj.get("id", ""))
                        description = cls._clean_html(rj.get("content", ""))
                        updated_at = rj.get("updated_at")

                        jobs.append({
                            "external_id": job_id,
                            "platform": "Greenhouse",
                            "company": company_slug.capitalize(),
                            "title": title,
                            "location": location,
                            "url": job_url,
                            "description": description,
                            "posted_date": updated_at
                        })
            except Exception:
                pass

        if client:
            await _fetch(client)
        else:
            async with httpx.AsyncClient(http2=HAS_H2) as c:
                await _fetch(c)

        return jobs

    @classmethod
    async def fetch_lever_jobs(cls, company_slug: str, client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
        """
        Fetches job postings from Lever API:
        https://api.lever.co/v0/postings/{company}?mode=json
        """
        url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
        jobs = []

        async def _fetch(c: httpx.AsyncClient):
            try:
                res = await c.get(url, headers=cls.HEADERS, timeout=8.0)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list):
                        for rj in data:
                            title = rj.get("text", "").strip()
                            categories = rj.get("categories", {})
                            location = categories.get("location", "Remote")
                            job_url = rj.get("hostedUrl", "")
                            job_id = str(rj.get("id", ""))
                            description = rj.get("descriptionPlain") or cls._clean_html(rj.get("description", ""))
                            created_at = rj.get("createdAt")

                            jobs.append({
                                "external_id": job_id,
                                "platform": "Lever",
                                "company": company_slug.capitalize(),
                                "title": title,
                                "location": location,
                                "url": job_url,
                                "description": description,
                                "posted_date": str(created_at) if created_at else None
                            })
            except Exception:
                pass

        if client:
            await _fetch(client)
        else:
            async with httpx.AsyncClient(http2=HAS_H2) as c:
                await _fetch(c)

        return jobs

    @classmethod
    async def fetch_ashby_jobs(cls, company_slug: str, client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
        """
        Fetches job postings from Ashby HQ Job Board API:
        https://api.ashbyhq.com/posting-api/job-board/{company}
        """
        url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
        jobs = []

        async def _fetch(c: httpx.AsyncClient):
            try:
                res = await c.get(url, headers=cls.HEADERS, timeout=8.0)
                if res.status_code == 200:
                    data = res.json()
                    job_postings = data.get("jobs", []) or data.get("jobPostings", [])
                    for rj in job_postings:
                        title = rj.get("title", "").strip()
                        location = rj.get("locationName") or rj.get("location", "Remote")
                        job_url = rj.get("jobUrl") or rj.get("applyUrl", "")
                        job_id = str(rj.get("id", ""))
                        description = rj.get("descriptionPlain") or cls._clean_html(rj.get("descriptionHtml", ""))
                        published_at = rj.get("publishedAt")

                        jobs.append({
                            "external_id": job_id,
                            "platform": "Ashby",
                            "company": company_slug.capitalize(),
                            "title": title,
                            "location": location,
                            "url": job_url,
                            "description": description,
                            "posted_date": str(published_at) if published_at else None
                        })
            except Exception:
                pass

        if client:
            await _fetch(client)
        else:
            async with httpx.AsyncClient(http2=HAS_H2) as c:
                await _fetch(c)

        return jobs

    @classmethod
    async def fetch_all_company_jobs(cls, company_slug: str) -> List[Dict[str, Any]]:
        """Tries Greenhouse, Lever, and Ashby in parallel for a given company slug."""
        async with httpx.AsyncClient(http2=HAS_H2) as client:
            results = await asyncio.gather(
                cls.fetch_greenhouse_jobs(company_slug, client),
                cls.fetch_lever_jobs(company_slug, client),
                cls.fetch_ashby_jobs(company_slug, client),
                return_exceptions=True
            )
            all_jobs = []
            for res in results:
                if isinstance(res, list):
                    all_jobs.extend(res)
            return all_jobs
