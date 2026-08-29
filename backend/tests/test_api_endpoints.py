"""
JobCopilot - REST & WebSocket API Integration Tests
Tests /api/upload-resume, /api/questionnaire, /api/vault, /api/hitl, and /api/jobs.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.main import app
from app.core.database import db
from app.core.models import HITLEvent, JobListing

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["storage"] == "sqlite_wal"


def test_upload_resume_and_auto_prefill():
    sample_text = """
    Jane Doe
    jane@doe.tech | +1 (555) 345-6789 | https://linkedin.com/in/janedoe | https://github.com/janedoe
    San Francisco, CA
    
    Education:
    Stanford University, Bachelor of Science in Computer Science, 2024
    
    Skills:
    Python, TypeScript, React, FastAPI, Docker, PostgreSQL, PyTorch
    
    Projects:
    Autonomous Agent Swarm: Multi-agent coordination system with 99.9% uptime.
    """
    res = client.post("/api/upload-resume", data={"raw_text": sample_text, "profile_id": "test_jane"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["profile"]["full_name"] == "Jane Doe"
    assert "Python" in data["profile"]["skills"]
    assert "questions_schema" in data
    assert len(data["questions_schema"]) == 8
    assert data["prefilled_questionnaire"]["full_name"] == "Jane Doe"


def test_questionnaire_lifecycle():
    # 1. Fetch questionnaire
    res = client.get("/api/questionnaire?profile_id=test_jane")
    assert res.status_code == 200
    data = res.json()
    assert len(data["questions_schema"]) == 8

    # 2. Submit confirmed questionnaire
    submit_payload = {
        "profile_id": "test_jane",
        "answers": {
            "expected_ctc": "150000 USD",
            "current_ctc": "120000 USD",
            "notice_period_days": 15,
            "work_authorization": "Citizen",
            "current_employer": "Meta"
        }
    }
    res_sub = client.post("/api/questionnaire", json=submit_payload)
    assert res_sub.status_code == 200
    res_data = res_sub.json()
    assert res_data["profile"]["preferences"]["expected_ctc"] == "150000 USD"
    assert "Meta" in res_data["profile"]["preferences"]["company_blacklist"]


def test_vault_endpoints():
    res = client.get("/api/vault")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] > 0

    learn_payload = {
        "question": "What is your favorite design pattern?",
        "answer": "I favor Dependency Injection and Factory patterns for modularity."
    }
    res_learn = client.post("/api/vault/learn", json=learn_payload)
    assert res_learn.status_code == 200
    assert res_learn.json()["status"] == "success"


def test_hitl_resolution_endpoint():
    # Save a test HITL event
    event = HITLEvent(
        event_id="evt_api_test",
        job_id="job_api_1",
        company="Stripe",
        role_title="Backend Engineer",
        question_text="How many years of Python experience?"
    )
    db.save_hitl_event(event)

    # Resolve event
    res = client.post("/api/hitl/resolve", json={"event_id": "evt_api_test", "user_answer": "4 years"})
    assert res.status_code == 200
    assert res.json()["status"] == "success"
