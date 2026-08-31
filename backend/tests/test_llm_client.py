"""
JobCopilot - Provider-Agnostic LLM Client & Fallback Test Suite
Validates that LLMClient handles local fallback, OpenAI, and Anthropic configurations safely.
"""

import pytest
from app.core.llm_client import LLMClient
from app.core.cover_letter import CoverLetterGenerator
from app.core.models import CandidateProfile, Project


@pytest.mark.asyncio
async def test_llm_client_deterministic_fallback():
    """Asserts LLMClient returns fallback string or function output when provider is local."""
    client = LLMClient(provider="local")
    fallback_text = "Deterministic high-quality fallback text."
    
    result = await client.generate_completion(
        prompt="Write something",
        fallback_fn=lambda: fallback_text
    )
    assert result == fallback_text


@pytest.mark.asyncio
async def test_cover_letter_with_llm_fallback():
    """Asserts CoverLetterGenerator generates cliché-free letter through async LLM pipeline."""
    profile = CandidateProfile(
        id="usr_llm_test",
        user_id="usr_llm_test",
        full_name="Alex River",
        email="alex@test.com",
        phone="+1-555-0199",
        location="New York, NY",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
        projects=[Project(name="DataPipe", description="High throughput ETL pipeline", technologies=["Python", "PostgreSQL"])]
    )

    letter = await CoverLetterGenerator.generate_cover_letter_async(
        profile=profile,
        company_name="Acme Systems",
        job_title="Senior Backend Engineer",
        job_description="Seeking a Senior Backend Engineer to build resilient APIs."
    )

    assert "Acme Systems" in letter
    assert "Alex River" in letter
    assert not CoverLetterGenerator.has_banned_cliches(letter)
