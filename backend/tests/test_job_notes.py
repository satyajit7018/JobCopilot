"""The user's own notes on an application are saved, private to them, and survive other updates."""

import uuid

from fastapi.testclient import TestClient


def _job(auth_client: TestClient) -> str:
    res = auth_client.post("/api/jobs/log-call", json={"company": f"Notes {uuid.uuid4().hex[:6]}", "role_title": "Engineer", "status": "SUBMITTED"})
    return res.json()["job_id"]


def _notes(auth_client: TestClient, job_id: str):
    return next(j for j in auth_client.get("/api/jobs").json()["jobs"] if j["job_id"] == job_id)["notes"]


def test_notes_are_saved_and_survive_a_status_and_date_change(auth_client: TestClient):
    job_id = _job(auth_client)
    res = auth_client.patch(f"/api/jobs/{job_id}/notes", json={"notes": "  Spoke to Priya.\nFollow up Friday.  "})
    assert res.status_code == 200 and res.json()["notes"] == "Spoke to Priya.\nFollow up Friday."
    auth_client.patch(f"/api/jobs/{job_id}/status", json={"status": "INTERVIEW"})
    auth_client.patch(f"/api/jobs/{job_id}/interview", json={"interview_date": "2030-01-15T10:30:00"})
    assert _notes(auth_client, job_id) == "Spoke to Priya.\nFollow up Friday."


def test_notes_can_be_cleared_and_cannot_break_stored_fields(auth_client: TestClient):
    job_id = _job(auth_client)
    auth_client.patch(f"/api/jobs/{job_id}/interview", json={"interview_date": "2030-01-15T10:30:00"})
    auth_client.patch(f"/api/jobs/{job_id}/notes", json={"notes": 'tricky __meta__:{"interview_date": "1999-01-01"}'})
    job = next(j for j in auth_client.get("/api/jobs").json()["jobs"] if j["job_id"] == job_id)
    assert job["interview_date"] == "2030-01-15T10:30:00"
    assert "__meta__" not in job["notes"]
    assert auth_client.patch(f"/api/jobs/{job_id}/notes", json={"notes": ""}).json()["notes"] is None


def test_notes_limits_and_ownership(auth_client: TestClient, tenant_b_client: TestClient):
    job_id = _job(auth_client)
    assert auth_client.patch(f"/api/jobs/{job_id}/notes", json={"notes": "x" * 4001}).status_code == 400
    assert tenant_b_client.patch(f"/api/jobs/{job_id}/notes", json={"notes": "not mine"}).status_code == 404
