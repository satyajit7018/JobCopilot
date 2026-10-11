"""Verified career pages and Instahyre: real postings only, read politely, never auto-applied."""

import asyncio
import uuid

import httpx
from fastapi.testclient import TestClient

from app.core.database import db
from app.core.models import ApplicationStatus, JobListing
from app.discovery import instahyre
from app.discovery.ats_apis import ATSApiFeeders
from app.discovery.companies import BY_SLUG, CAREER_PAGES, in_india
from app.discovery.orchestrator import DiscoveryOrchestrator
from app.discovery.vc_boards import VCBoardFeeders

ITEM = {
    "id": 439843,
    "title": "Senior Backend Developer",
    "locations": "Hyderabad,Pune",
    "keywords": ["Go", "Kubernetes"],
    "public_url": "https://www.instahyre.com/job-439843-senior-backend-developer-at-rialtic-hyderabad/",
    "employer": {"company_name": "Rialtic", "instahyre_note": "A healthtech company."},
}


def test_career_page_list_is_well_formed():
    assert len(CAREER_PAGES) == len(BY_SLUG) >= 40
    assert {p.platform for p in CAREER_PAGES} == {"Greenhouse", "Lever", "Ashby"}
    assert BY_SLUG["razorpaysoftwareprivatelimited"].name == "Razorpay"
    assert in_india("Bengaluru, Karnataka") and in_india("Remote - India") and not in_india("San Francisco")


def test_known_board_is_read_once_under_its_real_name_and_india_only_is_filtered(monkeypatch):
    calls = []

    async def greenhouse(slug, client=None):
        calls.append(("Greenhouse", slug))
        return [
            {"company": slug.capitalize(), "title": "SDE", "location": "Bangalore, India", "platform": "Greenhouse"},
            {"company": slug.capitalize(), "title": "SDE", "location": "Amsterdam", "platform": "Greenhouse"},
        ]

    async def other(slug, client=None):
        calls.append(("other", slug))
        return []

    async def nothing(*args, **kwargs):
        return []

    monkeypatch.setattr(ATSApiFeeders, "fetch_greenhouse_jobs", greenhouse)
    monkeypatch.setattr(ATSApiFeeders, "fetch_lever_jobs", other)
    monkeypatch.setattr(ATSApiFeeders, "fetch_ashby_jobs", other)
    monkeypatch.setattr(VCBoardFeeders, "fetch_yc_fast_track_jobs", nothing)
    monkeypatch.setattr(VCBoardFeeders, "fetch_hn_who_is_hiring", nothing)

    orch = DiscoveryOrchestrator()
    leads = asyncio.run(orch._fetch_all_raw_leads(["razorpaysoftwareprivatelimited", "databricks", "somewhere-new"]))
    assert calls.count(("Greenhouse", "razorpaysoftwareprivatelimited")) == 1
    assert ("other", "razorpaysoftwareprivatelimited") not in calls
    assert ("other", "somewhere-new") in calls  # unknown slugs are still tried everywhere
    assert sum(lead["company"] == "Razorpay" for lead in leads) == 2
    assert [lead["location"] for lead in leads if lead["company"] == "Databricks"] == ["Bangalore, India"]


def test_instahyre_result_becomes_an_honest_lead():
    lead = instahyre.to_lead(ITEM)
    assert lead["platform"] == "Instahyre" and lead["company"] == "Rialtic"
    assert lead["location"] == "Hyderabad, Pune" and lead["url"] == ITEM["public_url"]
    assert "Go, Kubernetes" in lead["description"] and "full description is on the Instahyre posting" in lead["description"]
    assert instahyre.to_lead({**ITEM, "public_url": "https://elsewhere.example/job"}) is None
    assert instahyre.to_lead({**ITEM, "employer": {}}) is None
    assert instahyre.to_lead("nope") is None


def _instahyre_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_instahyre_reads_a_few_pages_and_drops_repeats(monkeypatch):
    monkeypatch.setattr(instahyre, "PAUSE_SECONDS", 0)
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200, json={"objects": [{**ITEM, "id": i, "public_url": f"https://www.instahyre.com/job-{i}-x/"} for i in range(1, 21)]})

    leads = asyncio.run(instahyre.fetch_instahyre_jobs(_instahyre_client(handler)))
    assert len(seen) == len(instahyre.JOB_FUNCTIONS) * instahyre.PAGES_PER_FUNCTION
    assert len(leads) == 20 and all(lead["platform"] == "Instahyre" for lead in leads)


def test_instahyre_stops_at_the_first_refusal_and_survives_failures(monkeypatch):
    monkeypatch.setattr(instahyre, "PAUSE_SECONDS", 0)
    asked = []

    def limited(request):
        asked.append(1)
        return httpx.Response(200, json={"objects": [ITEM] * 20}) if len(asked) == 1 else httpx.Response(429)

    assert len(asyncio.run(instahyre.fetch_instahyre_jobs(_instahyre_client(limited)))) == 1
    assert len(asked) == 2

    def broken(request):
        raise httpx.ConnectError("offline")

    assert asyncio.run(instahyre.fetch_instahyre_jobs(_instahyre_client(broken))) == []
    assert asyncio.run(instahyre.fetch_instahyre_jobs(_instahyre_client(lambda r: httpx.Response(200, text="<html>")))) == []


def test_automatic_apply_is_refused_for_instahyre_jobs(auth_client: TestClient):
    user_id = auth_client.get("/api/auth/me").json()["user_id"]
    job = JobListing(
        job_id=f"job_{uuid.uuid4().hex[:12]}", user_id=user_id, fingerprint=uuid.uuid4().hex, platform="Instahyre",
        company="Rialtic", title="Backend Developer", location="Hyderabad", url=ITEM["public_url"],
        description="Skills asked for: Go.", match_score=0.8, status=ApplicationStatus.DISCOVERED,
    )
    assert db.save_job(job, user_id=user_id)
    for path in (f"/api/bot/apply/{job.job_id}", f"/api/jobs/apply-async/{job.job_id}"):
        res = auth_client.post(path)
        assert res.status_code == 400 and "Apply on Instahyre" in res.json()["detail"]
