"""
JobCopilot - Reading postings from Greenhouse, Lever and Ashby.

Each reader is given a stand-in for the job board (httpx.MockTransport), so these tests
check what we do with a board's answer without ever contacting one.
"""

import asyncio

import httpx
import pytest

from app.core.circuit_breaker import ats_api_breaker
from app.discovery.ats_apis import ATSApiFeeders

GREENHOUSE = {"jobs": [{
    "id": 4011, "title": " Backend Engineer ", "location": {"name": "Bengaluru"},
    "absolute_url": "https://boards.greenhouse.io/acme/jobs/4011",
    "content": "&lt;p&gt;Build &lt;b&gt;APIs&lt;/b&gt; in Python.&lt;/p&gt;",
    "first_published": "2026-10-01T09:00:00Z", "updated_at": "2026-10-09T09:00:00Z",
}]}
LEVER = [{
    "id": "lev-1", "text": "Platform Engineer", "categories": {"location": "Pune"},
    "hostedUrl": "https://jobs.lever.co/acme/lev-1", "descriptionPlain": "Run our platform.",
    "createdAt": 1790000000000,
}, {
    "id": "lev-2", "text": "SRE", "categories": {}, "hostedUrl": "https://jobs.lever.co/acme/lev-2",
    "description": "<div>Keep it up.</div>", "createdAt": None,
}]
ASHBY = {"jobs": [{
    "id": "ash-1", "title": "ML Engineer", "locationName": "Remote, India",
    "jobUrl": "https://jobs.ashbyhq.com/acme/ash-1", "descriptionPlain": "Train models.",
    "publishedAt": "2026-10-05T00:00:00Z",
}]}


@pytest.fixture(autouse=True)
def _closed_breaker():
    ats_api_breaker.reset()
    yield
    ats_api_breaker.reset()


def read(fetch, status=200, body=None, seen=None):
    def answer(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(str(request.url))
        return httpx.Response(status, json=body if body is not None else {})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
            return await fetch("acme", client=client)

    return asyncio.run(go())


def test_greenhouse_posting_is_read_with_clean_text_and_first_published_date():
    seen = []
    jobs = read(ATSApiFeeders.fetch_greenhouse_jobs, body=GREENHOUSE, seen=seen)
    assert seen == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"]
    assert jobs == [{
        "external_id": "4011", "platform": "Greenhouse", "company": "Acme", "title": "Backend Engineer",
        "location": "Bengaluru", "url": "https://boards.greenhouse.io/acme/jobs/4011",
        "description": "Build APIs in Python.",
        # the day it was first published, not the day it was last edited
        "posted_date": "2026-10-01T09:00:00Z",
    }]


def test_lever_postings_are_read_with_dates_and_fallbacks():
    seen = []
    first, second = read(ATSApiFeeders.fetch_lever_jobs, body=LEVER, seen=seen)
    assert seen == ["https://api.lever.co/v0/postings/acme?mode=json"]
    assert first["title"] == "Platform Engineer" and first["location"] == "Pune"
    assert first["description"] == "Run our platform." and first["posted_date"].startswith("2026-")
    # no location, no plain text and no date: sensible fallbacks, nothing invented
    assert second["location"] == "Remote" and second["description"] == "Keep it up."
    assert second["posted_date"] is None


def test_ashby_posting_is_read():
    seen = []
    (job,) = read(ATSApiFeeders.fetch_ashby_jobs, body=ASHBY, seen=seen)
    assert seen == ["https://api.ashbyhq.com/posting-api/job-board/acme"]
    assert job["platform"] == "Ashby" and job["external_id"] == "ash-1"
    assert job["location"] == "Remote, India" and job["url"] == "https://jobs.ashbyhq.com/acme/ash-1"
    assert job["description"] == "Train models." and job["posted_date"] == "2026-10-05T00:00:00Z"


@pytest.mark.parametrize("fetch", [ATSApiFeeders.fetch_greenhouse_jobs, ATSApiFeeders.fetch_lever_jobs, ATSApiFeeders.fetch_ashby_jobs])
@pytest.mark.parametrize("status", [404, 500, 503])
def test_a_missing_or_broken_board_gives_no_postings(fetch, status):
    assert read(fetch, status=status) == []


@pytest.mark.parametrize("fetch", [ATSApiFeeders.fetch_greenhouse_jobs, ATSApiFeeders.fetch_lever_jobs, ATSApiFeeders.fetch_ashby_jobs])
def test_an_unexpected_answer_gives_no_postings(fetch):
    assert read(fetch, body={"unexpected": True}) == []


@pytest.mark.parametrize("fetch", [ATSApiFeeders.fetch_greenhouse_jobs, ATSApiFeeders.fetch_lever_jobs, ATSApiFeeders.fetch_ashby_jobs])
def test_boards_are_left_alone_while_the_circuit_is_open(fetch):
    seen = []
    ats_api_breaker.trip()
    assert read(fetch, body=GREENHOUSE, seen=seen) == []
    assert seen == []  # no request was made at all
