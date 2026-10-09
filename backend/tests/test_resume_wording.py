"""
AI resume wording is reviewable: the user sees each reworded bullet next to their own,
picks one, and the application uses exactly that pick (not a fresh rewrite).
"""

import asyncio
import uuid

import pytest

from app.core.llm_client import llm_client
from app.core.models import CandidateProfile, WorkExperience
from app.core.resume_compiler import ResumeCompiler
from app.core.resume_tailor import ResumeTailor
from app.core.settings import settings

JD = "Backend role using Python, FastAPI and PostgreSQL."
BULLETS = ["Built Python services handling 2M requests a day", "Moved reporting to PostgreSQL and FastAPI"]


@pytest.fixture
def setup(monkeypatch):
    calls = {"n": 0}

    async def fake_llm(self, prompt, system_prompt=None, fallback_fn=None, **_):
        calls["n"] += 1
        return f"- Reworded take {calls['n']}: built Python services at scale\n- Reworded take {calls['n']}: PostgreSQL + FastAPI reporting"

    async def no_pdf(cls, html, path):
        return path

    monkeypatch.setattr(type(llm_client), "generate_completion", fake_llm)
    monkeypatch.setattr(ResumeCompiler, "compile_to_pdf", classmethod(no_pdf))
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    profile = CandidateProfile(id=user_id, user_id=user_id, full_name="W", email="w@test.com", phone="1", location="Pune",
                               skills=["Python", "FastAPI", "PostgreSQL"],
                               experience=[WorkExperience(company="Acme", title="Engineer", start_date="2022", end_date="Present",
                                                          highlights=list(BULLETS))])
    yield profile, calls
    settings.purge_user_files(user_id)


def _compile(profile, job_id="job_w1"):
    return asyncio.run(ResumeTailor.compile_tailored_resume_for_job(profile, job_id, "Backend Engineer", JD, "Acme"))[2]


def test_applying_reuses_the_wording_that_was_shown(setup):
    profile, calls = setup
    shown = _compile(profile).experience[0].highlights
    assert calls["n"] == 1 and shown[0].startswith("Reworded take 1")
    # Applying later compiles again: same words, no new rewrite.
    assert _compile(profile).experience[0].highlights == shown
    assert calls["n"] == 1

    wording = ResumeTailor.current_wording(profile, "job_w1", "Backend Engineer", JD)
    changes = ResumeTailor.wording_changes(profile, "Backend Engineer", JD, wording)
    assert {c["before"] for c in changes} == set(BULLETS)
    assert all(c["after"].startswith("Reworded take 1") for c in changes)


def test_choosing_original_sends_the_users_own_words(setup):
    profile, _ = setup
    _compile(profile)
    wording = ResumeTailor.load_wording(profile.user_id, "job_w1")
    ResumeTailor.save_wording(profile.user_id, "job_w1", {**wording, "choice": "original"})
    assert sorted(_compile(profile).experience[0].highlights) == sorted(BULLETS)


def test_wording_from_an_older_resume_is_not_used(setup):
    profile, calls = setup
    _compile(profile)
    profile.experience[0].highlights = ["Led a team of four on billing", "Cut cloud costs by 30% with Python tooling"]
    assert ResumeTailor.current_wording(profile, "job_w1", "Backend Engineer", JD) is None
    _compile(profile)
    assert calls["n"] == 2, "a changed resume gets fresh wording"
