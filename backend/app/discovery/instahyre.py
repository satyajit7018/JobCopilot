"""
JobCopilot - Instahyre listings.

Reads the public job search that Instahyre's own website uses. It gives the role, company,
cities, the skills asked for and a note about the company, but not the full description,
so the description we keep says exactly that and the posting link carries the rest. A few
pages per run, one at a time: the result is shared by every user for the hour (see
orchestrator.get_leads).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core import company_info

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.instahyre.com/api/v1/job_search"
POSTING_PREFIX = "https://www.instahyre.com/job-"
PAGE_SIZE = 20
# Instahyre's own ids: backend, full-stack, data science / ML, DevOps / cloud.
JOB_FUNCTIONS = (10, 1, 9, 8)
PAGES_PER_FUNCTION = 2
PAUSE_SECONDS = 1.0
HEADERS = {"User-Agent": "JobCopilot/1.0 (job search assistant)", "Accept": "application/json"}


def to_lead(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One search result as a lead, or None when it lacks what a posting needs."""
    if not isinstance(item, dict):
        return None
    employer = item.get("employer") if isinstance(item.get("employer"), dict) else {}
    company = str(employer.get("company_name") or "").strip()
    title = str(item.get("title") or "").strip()
    url = str(item.get("public_url") or "").strip()
    if not (company and title and item.get("id") and url.startswith(POSTING_PREFIX)):
        return None
    skills = [str(k).strip() for k in item.get("keywords") or [] if str(k).strip()]
    about = str(employer.get("instahyre_note") or "").strip()
    parts = []
    if skills:
        parts.append(f"Skills asked for: {', '.join(skills)}.")
    parts.append("The full description is on the Instahyre posting.")
    cities = [c.strip() for c in str(item.get("locations") or "").split(",") if c.strip()]
    return {
        "external_id": f"instahyre_{item['id']}",
        "platform": "Instahyre",
        "company": company,
        "title": title,
        "location": ", ".join(cities) or "India",
        "url": url,
        "description": " ".join(parts),
        "posted_date": None,
        # The company note Instahyre publishes with the posting; shown as "About the company".
        "company_about": about,
    }


async def fetch_instahyre_jobs(client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
    """Recent tech listings from Instahyre. Any failure ends the read with what we have."""
    leads: Dict[str, Dict[str, Any]] = {}
    own = client is None
    http = client or httpx.AsyncClient(timeout=10.0)
    try:
        for function in JOB_FUNCTIONS:
            for page in range(PAGES_PER_FUNCTION):
                res = await http.get(
                    SEARCH_URL,
                    headers=HEADERS,
                    params={"company_size": 0, "isLandingPage": "true", "job_type": 0,
                            "job_functions": function, "offset": page * PAGE_SIZE},
                )
                if res.status_code != 200:
                    # Blocked or changed: stop asking rather than keep knocking.
                    logger.warning("Instahyre search answered %s; stopping this read.", res.status_code)
                    return list(leads.values())
                items = res.json().get("objects") or []
                for item in items:
                    lead = to_lead(item)
                    if lead:
                        leads[lead["external_id"]] = lead
                        company_info.remember(lead["company"], lead["company_about"])
                if len(items) < PAGE_SIZE:
                    break
                await asyncio.sleep(PAUSE_SECONDS)
    except (httpx.HTTPError, ValueError, AttributeError) as e:
        logger.warning("Instahyre read failed: %s", e)
    finally:
        if own:
            await http.aclose()
    return list(leads.values())
