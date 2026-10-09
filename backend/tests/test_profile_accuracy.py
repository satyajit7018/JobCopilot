"""
Profiles and applications must reflect what the person actually said and did.

- The resume reader used to make up a job ("Senior Software Engineer at Technology
  Solutions, 2023"), projects with invented results, certifications and a school
  called "University". It now reads entries as written and leaves gaps empty.
- Re-running a search overwrote jobs already applied to (status back to "new").
- Marking a job applied by hand never recorded when.
- A field the vault couldn't decrypt was shown (and could be saved back) as "[ENCRYPTED]".
- Fallback cover letters and outreach claimed experience and results nobody gave.
"""

import json
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token
from app.core.cover_letter import CoverLetterGenerator
from app.core.database import DatabaseManager, db
from app.core.models import ApplicationStatus, CandidateProfile, JobListing, User, UserRole
from app.core.resume_parser import ResumeParser
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures" / "resumes"
client = TestClient(app)

INVENTED = ("Technology Solutions", "Sub-50ms", "10k+ requests", "sub-50ms latency", "scaled system",
            "Remote / Global", "Seeking challenging technical opportunities")


@pytest.mark.parametrize("name", ["standard_software_engineer", "career_changer_junior", "indian_fintech_lead"])
def test_reads_the_real_employer_and_title(name):
    expected = json.loads((FIXTURES / f"{name}.json").read_text())
    profile = ResumeParser.parse_to_profile((FIXTURES / f"{name}.txt").read_text())
    first = profile.experience[0]
    assert first.company == expected["expected_company"]
    assert first.title == expected["expected_title"]
    assert first.start_date and first.end_date
    assert first.highlights, "bullets under the job become its highlights"


def test_title_company_on_one_line_and_years_stated():
    text = """Asha Rao
asha@example.test | Pune, India

SUMMARY
Backend engineer with 5 years of experience in Python and Go.

EXPERIENCE
Senior Software Engineer, Example Payments - Pune
Jan 2022 - Present
- Built a reconciliation service handling 2M events a day

EDUCATION
B.Tech Computer Science, Example Institute, 2019
"""
    p = ResumeParser.parse_to_profile(text)
    assert (p.experience[0].title, p.experience[0].company) == ("Senior Software Engineer", "Example Payments")
    assert (p.experience[0].start_date, p.experience[0].end_date) == ("Jan 2022", "Present")
    assert p.preferences.years_of_experience == 5.0
    assert [(e.degree, e.institution, e.graduation_year) for e in p.education] == [("B.Tech Computer Science", "Example Institute", "2019")]
    assert p.summary.startswith("Backend engineer with 5 years")


def test_prose_resume():
    p = ResumeParser.parse_to_profile((FIXTURES / "messy_unstructured_resume.txt").read_text())
    assert (p.experience[0].company, p.experience[0].start_date, p.experience[0].end_date) == ("PayTM", "2019", "Present")
    assert p.location == "Gurgaon, India"
    assert p.education[0].institution == "Delhi Technological University"


def test_years_from_dates_when_not_stated():
    text = "EXPERIENCE\nAcme | Remote\nEngineer | 2018 - 2020\n- Did things\nBeta | Remote\nEngineer | 2020 - 2022\n- More\n"
    assert 3.5 <= ResumeParser.calculate_estimated_yoe(text) <= 5.0


def test_nothing_is_invented_for_a_sparse_resume():
    p = ResumeParser.parse_to_profile("Jane Doe\njane@example.test\nSkills: Python, AWS, architect of my own projects")
    assert p.experience == []
    assert p.projects == []
    assert p.education == []
    assert p.certifications == []
    assert p.preferences.why_looking_for_role == ""
    blob = p.model_dump_json()
    for phrase in INVENTED:
        assert phrase not in blob


def test_fallback_letters_only_use_profile_facts():
    profile = ResumeParser.parse_to_profile((FIXTURES / "standard_software_engineer.txt").read_text())
    letter = CoverLetterGenerator.generate_cover_letter(profile, "Acme", "Backend Engineer")
    assert "CloudScale Systems Inc" in letter
    for phrase in INVENTED + ("AI systems", "sub-50ms"):
        assert phrase not in letter
    profile.preferences.notice_period_days = 30
    assert "30-day notice period" in CoverLetterGenerator.generate_cover_letter(profile, "Acme", "Backend Engineer")


def test_undecryptable_fields_read_as_empty():
    stored = {"_pii_encrypted": True, "phone": "env:v1:not-decryptable", "location": "env:v1:also-bad",
              "preferences": {"expected_ctc": "env:v1:nope"}}
    out = DatabaseManager._decrypt_profile_dict(stored)
    assert out["phone"] == "" and out["location"] == "" and out["preferences"]["expected_ctc"] == ""


# --- API ---------------------------------------------------------------------------


def _user_client():
    user = User(user_id=f"usr_{uuid.uuid4().hex[:12]}", email=f"acc_{uuid.uuid4().hex[:8]}@test.com",
                password_hash="x", full_name="Acc Tester", role=UserRole.FREE, is_active=True)
    db.create_user(user)
    token = create_jwt_token({"sub": user.user_id, "email": user.email, "role": "FREE", "type": "access"}, timedelta(minutes=30))
    tc = TestClient(app)
    tc.headers["Authorization"] = f"Bearer {token}"
    return user, tc


def test_background_corrections_are_saved():
    user, tc = _user_client()
    try:
        db.save_profile(CandidateProfile(id=user.user_id, user_id=user.user_id, full_name="A", email=user.email,
                                         phone="1", location="Pune, India", skills=["Python"]), user_id=user.user_id)
        res = tc.put("/api/profile/background", json={
            "skills": ["Go", " go ", "Kafka", ""],
            "experience": [{"title": "Engineer", "company": "Acme", "start_date": "2021", "end_date": "Present"},
                           {"title": "", "company": "", "start_date": "", "end_date": ""}],
            "education": [{"degree": "B.Tech", "institution": "IIT", "graduation_year": "2019"}],
        })
        assert res.status_code == 200
        saved = db.get_profile(user_id=user.user_id)
        assert saved.skills == ["Go", "Kafka"]
        assert [(x.title, x.company) for x in saved.experience] == [("Engineer", "Acme")]
        assert saved.education[0].institution == "IIT"
    finally:
        db.hard_delete_user_account(user.user_id)


def test_marking_applied_records_the_date():
    user, tc = _user_client()
    try:
        job = JobListing(job_id=f"job_{uuid.uuid4().hex[:10]}", user_id=user.user_id, fingerprint=uuid.uuid4().hex,
                         platform="x", company="Acme", title="Engineer", url="https://example.com")
        db.save_job(job, user_id=user.user_id)
        assert tc.patch(f"/api/jobs/{job.job_id}/status", json={"status": "SUBMITTED"}).status_code == 200
        assert db.get_job_by_id(job.job_id, user_id=user.user_id).applied_at
    finally:
        db.hard_delete_user_account(user.user_id)


def test_new_search_keeps_applied_and_hidden_jobs(monkeypatch):
    import asyncio

    from app.core.deduplicator import JobDeduplicator
    from app.discovery.orchestrator import DiscoveryOrchestrator

    user, _ = _user_client()
    try:
        lead = {"company": "Acme", "title": "Backend Engineer", "location": "Pune, India", "url": "https://acme.test/1",
                "description": "Python, Go, FastAPI, PostgreSQL, Redis, Docker, Kubernetes on AWS."}
        hidden_lead = {**lead, "title": "Platform Engineer", "url": "https://acme.test/2"}
        profile = CandidateProfile(id=user.user_id, user_id=user.user_id, full_name="A", email=user.email, phone="1",
                                   location="Pune, India",
                                   skills=["Python", "Go", "FastAPI", "PostgreSQL", "Redis", "Docker", "Kubernetes", "AWS"])
        orch = DiscoveryOrchestrator(min_match_threshold=0.0)

        async def leads(_companies):
            return [lead, hidden_lead]

        monkeypatch.setattr(orch, "_fetch_all_raw_leads", leads)
        asyncio.run(orch.run_discovery_cycle(profile, user_id=user.user_id))
        jobs = {j.title: j for j in db.get_jobs(user_id=user.user_id)}
        applied, hidden = jobs["Backend Engineer"], jobs["Platform Engineer"]
        applied.status, applied.applied_at = ApplicationStatus.SUBMITTED, "2026-10-01T10:00:00"
        hidden.status = ApplicationStatus.DISMISSED
        db.save_job(applied, user_id=user.user_id)
        db.save_job(hidden, user_id=user.user_id)

        asyncio.run(orch.run_discovery_cycle(profile, user_id=user.user_id))
        after = {j.title: j for j in db.get_jobs(user_id=user.user_id)}
        assert len(after) == 2
        assert after["Backend Engineer"].status == ApplicationStatus.SUBMITTED
        assert after["Backend Engineer"].applied_at == "2026-10-01T10:00:00"
        assert after["Platform Engineer"].status == ApplicationStatus.DISMISSED
        assert JobDeduplicator  # fingerprints are what match the re-found postings
    finally:
        db.hard_delete_user_account(user.user_id)
