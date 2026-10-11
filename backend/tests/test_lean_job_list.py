"""The job list stays small: no descriptions in the list, one job in full on request, answers compressed."""

import uuid

from fastapi.testclient import TestClient

from app.core.database import db
from app.core.models import ApplicationStatus, JobListing

DESCRIPTION = "Build payment services in Python and Go. " * 30


def _job(auth_client: TestClient) -> JobListing:
    user_id = auth_client.get("/api/auth/me").json()["user_id"]
    job = JobListing(
        job_id=f"job_{uuid.uuid4().hex[:12]}", user_id=user_id, fingerprint=uuid.uuid4().hex, platform="Greenhouse",
        company=f"Lean {uuid.uuid4().hex[:6]}", title="Backend Engineer", location="Pune", url="https://example.test/job",
        description=DESCRIPTION, match_score=0.8, status=ApplicationStatus.DISCOVERED,
    )
    assert db.save_job(job, user_id=user_id)
    return job


def test_list_leaves_descriptions_out_and_one_job_has_it(auth_client: TestClient):
    job = _job(auth_client)
    listed = next(j for j in auth_client.get("/api/jobs").json()["jobs"] if j["job_id"] == job.job_id)
    assert "description" not in listed and listed["title"] == "Backend Engineer" and listed["match_score"] == 0.8
    full = auth_client.get(f"/api/jobs/{job.job_id}")
    assert full.status_code == 200 and full.json()["description"].strip() == DESCRIPTION.strip()
    with_text = next(j for j in auth_client.get("/api/jobs", params={"descriptions": "true"}).json()["jobs"] if j["job_id"] == job.job_id)
    assert with_text["description"] == full.json()["description"]


def test_one_job_is_private_and_held_list_still_works(auth_client: TestClient, tenant_b_client: TestClient):
    job = _job(auth_client)
    assert tenant_b_client.get(f"/api/jobs/{job.job_id}").status_code == 404
    assert auth_client.get("/api/jobs/job_does_not_exist").status_code == 404
    held = auth_client.get("/api/jobs/held")
    assert held.status_code == 200 and "detail" not in held.json()


def test_large_answers_are_compressed(auth_client: TestClient):
    for _ in range(5):
        _job(auth_client)
    res = auth_client.get("/api/jobs", headers={"Accept-Encoding": "gzip"})
    assert res.headers.get("content-encoding") == "gzip" and res.json()["count"] >= 5
    # A client that doesn't ask for it gets a plain answer.
    assert auth_client.get("/api/jobs", headers={"Accept-Encoding": "identity"}).headers.get("content-encoding") is None
