"""
JobCopilot - VC Portfolio & Fast-Track Job Board Feeders
Parses high-signal 0-day startup jobs from Y Combinator (Work at a Startup),
HackerNews 'Who is Hiring?' threads, and top tier VC portfolio boards.
"""

import re
import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class VCBoardFeeders:
    """Fetches high-signal startup jobs from YC and HackerNews."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    @classmethod
    async def fetch_hn_who_is_hiring(cls, max_posts: int = 20, client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
        """
        Fetches latest job postings from HackerNews 'Ask HN: Who is hiring?' thread
        using the public official Firebase API.
        """
        jobs = []
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            should_close = True

        try:
            search_url = "https://hacker-news.firebaseio.com/v0/user/whoishiring.json"
            res = await client.get(search_url, headers=cls.HEADERS)
            if res.status_code == 200:
                submitted = res.json().get("submitted", [])
                story_id = None
                for sid in submitted[:5]:
                    story_res = await client.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", headers=cls.HEADERS)
                    if story_res.status_code == 200:
                        story_data = story_res.json()
                        title = story_data.get("title", "")
                        if "Ask HN: Who is hiring?" in title:
                            story_id = sid
                            break

                if story_id:
                    story_detail = (await client.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", headers=cls.HEADERS)).json()
                    comment_ids = story_detail.get("kids", [])[:max_posts]

                    tasks = [client.get(f"https://hacker-news.firebaseio.com/v0/item/{cid}.json", headers=cls.HEADERS) for cid in comment_ids]
                    responses = await asyncio.gather(*tasks, return_exceptions=True)

                    for r in responses:
                        if isinstance(r, httpx.Response) and r.status_code == 200:
                            cdata = r.json()
                            if cdata and not cdata.get("deleted") and "text" in cdata:
                                parsed = cls._parse_hn_comment(cdata["text"], cdata["id"])
                                if parsed:
                                    jobs.append(parsed)
        except Exception as e:
            logger.debug(f"HN Who is Hiring fetch error: {e}")
        finally:
            if should_close:
                await client.aclose()

        return jobs

    @classmethod
    def _parse_hn_comment(cls, html_text: str, comment_id: int) -> Optional[Dict[str, Any]]:
        """Parses standard HN Who is Hiring format: 'Company | Role | Location | REMOTE | Salary'."""
        cleaned = re.sub(r'<[^>]+>', ' ', html_text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        lines = [l.strip() for l in cleaned.split('\n') if l.strip()]
        header = lines[0] if lines else cleaned[:150]

        parts = [p.strip() for p in header.split('|')]
        if len(parts) >= 2:
            company = parts[0]
            title = parts[1]
            location = parts[2] if len(parts) > 2 else "Remote"
            is_remote = "remote" in header.lower() or "remote" in cleaned.lower()
            if is_remote and "remote" not in location.lower():
                location += " (Remote)"

            # Look for contact / apply link
            url_match = re.search(r'https?://[^\s<>"]+', html_text)
            job_url = url_match.group(0) if url_match else f"https://news.ycombinator.com/item?id={comment_id}"

            # Extract salary if mentioned (e.g. $180k - $240k, 25-35 LPA, €80k - €100k, $150,000)
            salary_match = re.search(
                r'(\$?\d{2,3}[kK]?\s*(?:-|to)\s*\$?\d{2,3}[kK]|\$\d{2,3}(?:,\d{3})+|\d{1,3}\s*LPA|\d{1,3}\s*-\s*\d{1,3}\s*LPA)',
                cleaned
            )
            salary_range = salary_match.group(0) if salary_match else None

            return {
                "external_id": f"hn_{comment_id}",
                "platform": "HackerNews",
                "company": company,
                "title": title,
                "location": location,
                "url": job_url,
                "description": cleaned,
                "salary_range": salary_range,
                "posted_date": None
            }
        return None

    @classmethod
    async def fetch_yc_fast_track_jobs(cls, role_keyword: str = "Engineer") -> List[Dict[str, Any]]:
        """Curated high-signal Y Combinator startup job listings."""
        yc_tech_hubs = [
            ("superkalam", "SuperKalam (YC W23)", "Greenhouse"),
            ("perplexity", "Perplexity AI", "Ashby"),
            ("curative", "Curative", "Greenhouse"),
            ("postman", "Postman", "Greenhouse"),
            ("retool", "Retool", "Greenhouse"),
            ("scale", "Scale AI", "Greenhouse"),
            ("whatnot", "Whatnot", "Greenhouse"),
            ("brex", "Brex", "Greenhouse")
        ]

        from app.discovery.ats_apis import ATSApiFeeders

        all_yc_jobs = []
        async with httpx.AsyncClient(http2=True, timeout=8.0) as client:
            tasks = []
            for slug, brand_name, platform in yc_tech_hubs:
                if platform == "Greenhouse":
                    tasks.append(ATSApiFeeders.fetch_greenhouse_jobs(slug, client))
                elif platform == "Ashby":
                    tasks.append(ATSApiFeeders.fetch_ashby_jobs(slug, client))
                else:
                    tasks.append(ATSApiFeeders.fetch_lever_jobs(slug, client))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    for j in res:
                        j["platform"] = "Y Combinator"
                        all_yc_jobs.append(j)

        return all_yc_jobs
