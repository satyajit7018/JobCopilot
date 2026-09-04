"""
JobCopilot - Resume Parser Accuracy & Fixture Benchmark Suite
Tests extraction fidelity across diverse resume topologies (US CS Grad, Indian FinTech Lead,
Junior Career Changer, and Unstructured Messy Text) for both regex and async LLM extraction.
"""

import json
from pathlib import Path
import pytest

from app.core.resume_parser import ResumeParser

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "resumes"


def load_fixture(fixture_name: str):
    txt_path = FIXTURES_DIR / f"{fixture_name}.txt"
    json_path = FIXTURES_DIR / f"{fixture_name}.json"
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()
    with open(json_path, "r", encoding="utf-8") as f:
        expected = json.load(f)
    return text, expected


def test_standard_software_engineer_accuracy():
    """Validates high-accuracy extraction for standard US software engineer resume."""
    text, expected = load_fixture("standard_software_engineer")
    profile = ResumeParser.parse_to_profile(text, profile_id="test_standard")

    assert profile.full_name == expected["full_name"]
    assert profile.email.lower() == expected["email"].lower()
    assert profile.phone == expected["phone"]
    assert "San Francisco" in profile.location
    assert profile.linkedin_url == expected["linkedin_url"]
    assert profile.github_url == expected["github_url"]

    # Skill extraction precision & recall
    extracted_lower = {s.lower() for s in profile.skills}
    for exp_skill in expected["expected_skills"]:
        assert exp_skill.lower() in extracted_lower, f"Missing expected skill: {exp_skill}"

    assert len(profile.education) > 0
    assert "mit" in profile.education[0].institution.lower() or "massachusetts" in profile.education[0].institution.lower()


def test_indian_fintech_lead_accuracy():
    """Validates extraction for Indian candidate with 5-5 phone formatting, LPA CTC, and IIT education."""
    text, expected = load_fixture("indian_fintech_lead")
    profile = ResumeParser.parse_to_profile(text, profile_id="test_indian_lead")

    assert profile.full_name == expected["full_name"]
    assert profile.email.lower() == expected["email"].lower()
    # Matches Indian 5-5 space phone format (+91 98451 23456)
    assert "98451" in profile.phone and "23456" in profile.phone
    assert "Bengaluru" in profile.location or "India" in profile.location

    extracted_lower = {s.lower() for s in profile.skills}
    expected_matches = sum(1 for s in expected["expected_skills"] if s.lower() in extracted_lower)
    accuracy_ratio = expected_matches / len(expected["expected_skills"])
    assert accuracy_ratio >= 0.85, f"Skill accuracy ratio {accuracy_ratio} below threshold 0.85"


def test_career_changer_junior_accuracy():
    """Validates extraction for junior bootcamp graduate with projects emphasis."""
    text, expected = load_fixture("career_changer_junior")
    profile = ResumeParser.parse_to_profile(text, profile_id="test_junior")

    assert profile.full_name == expected["full_name"]
    assert profile.email.lower() == expected["email"].lower()
    assert "Seattle" in profile.location
    assert profile.github_url == expected["github_url"]

    extracted_lower = {s.lower() for s in profile.skills}
    for s in ["javascript", "typescript", "python", "react", "docker"]:
        assert s in extracted_lower, f"Missing core web skill: {s}"

    assert len(profile.projects) >= 1


def test_messy_unstructured_resume_accuracy():
    """Validates robust extraction from messy unstructured text without standard headers."""
    text, expected = load_fixture("messy_unstructured_resume")
    profile = ResumeParser.parse_to_profile(text, profile_id="test_messy")

    assert profile.email == expected["email"]
    assert "91234" in profile.phone and "56789" in profile.phone
    assert "Rahul" in profile.full_name

    extracted_lower = {s.lower() for s in profile.skills}
    assert "python" in extracted_lower
    assert "fastapi" in extracted_lower
    assert "docker" in extracted_lower


@pytest.mark.asyncio
async def test_async_hybrid_llm_parser_flow():
    """Validates that parse_to_profile_async executes cleanly and produces a valid CandidateProfile."""
    text, expected = load_fixture("standard_software_engineer")
    profile = await ResumeParser.parse_to_profile_async(text, profile_id="test_async_std")

    assert profile.full_name == expected["full_name"]
    assert profile.email == expected["email"]
    assert len(profile.skills) >= 5
    assert len(profile.experience) >= 1
    assert len(profile.education) >= 1
