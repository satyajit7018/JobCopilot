"""
JobCopilot - LLM Rollout & Versioned Prompt Engine Verification Suite
Validates:
1. Versioned prompt compilation (Tailoring, Interview, Negotiation, Cover Letter)
2. ResumeTailor async bullet optimization and transparent fallback
3. InterviewStudio async dossier & STAR evaluation with fallback
4. SalaryNegotiation async counter-script with fallback
5. CoverLetterGenerator async generation with anti-AI cliché stripping
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.core.prompts import (
    TailoringPrompts, InterviewPrompts, NegotiationPrompts, CoverLetterPrompts
)
from app.core.models import CandidateProfile, WorkExperience, Project, RecruiterPreferences
from app.core.resume_tailor import ResumeTailor
from app.core.interview_studio import InterviewStudioEngine
from app.core.negotiation import SalaryNegotiationEngine
from app.core.cover_letter import CoverLetterGenerator


def test_versioned_prompts_integrity():
    """Validates prompt templates and version numbers."""
    assert TailoringPrompts.VERSION == "1.0.0"
    assert InterviewPrompts.VERSION == "1.0.0"
    assert NegotiationPrompts.VERSION == "1.0.0"
    assert CoverLetterPrompts.VERSION == "1.0.0"

    # Tailoring prompt builder
    t_prompt = TailoringPrompts.build_bullet_optimization_prompt(
        candidate_bullets=["Built APIs in Python", "Scaled Postgres"],
        job_title="Backend Engineer",
        company_name="Stripe",
        target_skills=["Python", "Kafka", "Postgres"],
        job_description="High-volume payments platform."
    )
    assert "Target Role: Backend Engineer at Stripe" in t_prompt
    assert "Python, Kafka, Postgres" in t_prompt

    # Interview STAR prompt builder
    star_prompt = InterviewPrompts.build_star_evaluation_prompt(
        question="Describe a difficult distributed systems bug you resolved.",
        candidate_answer="We had a split-brain issue in Redis cluster so I implemented Raft consensus.",
        role_title="Staff SDE",
        company_name="Uber"
    )
    assert "Company: Uber" in star_prompt
    assert "Role: Staff SDE" in star_prompt

    # Negotiation prompt builder
    neg_prompt = NegotiationPrompts.build_counter_script_prompt(
        company_name="Razorpay",
        role_title="Lead Architect",
        offered_base=40.0,
        target_base=48.0,
        offered_equity=15.0,
        target_equity=25.0,
        competing_offers_summary="Cred offering 50 LPA"
    )
    assert "Company: Razorpay" in neg_prompt
    assert "Cred offering 50 LPA" in neg_prompt


@pytest.mark.asyncio
async def test_resume_tailor_async_rollout():
    """Validates tailor_profile_for_job_async execution and fallback."""
    profile = CandidateProfile(
        id="usr_test_llm_01",
        full_name="Aarav Sharma",
        email="aarav@test.in",
        phone="+91 98765 43210",
        location="Bangalore, India",
        skills=["Python", "FastAPI", "Kafka", "Docker"],
        experience=[
            WorkExperience(
                company="FinTech Corp",
                title="Backend Engineer",
                start_date="2023",
                end_date="Present",
                highlights=[
                    "Engineered payment settlement microservices handling 50,000 daily webhooks.",
                    "Optimized Postgres query indexes cutting p99 response time from 320ms to 45ms."
                ]
            )
        ]
    )

    tailored, matched = await ResumeTailor.tailor_profile_for_job_async(
        profile=profile,
        job_title="Staff Backend SDE",
        job_description="Seeking Python and Kafka experts to scale real-time message brokers.",
        company_name="Swiggy"
    )
    assert len(tailored.experience) == 1
    assert len(tailored.experience[0].highlights) == 2
    assert "Python" in matched or "Kafka" in matched


@pytest.mark.asyncio
async def test_interview_studio_async_rollout():
    """Validates generate_company_dossier_async and evaluate_candidate_response_async."""
    # 1. Dossier async
    dossier = await InterviewStudioEngine.generate_company_dossier_async(
        company_name="Stripe",
        role_title="Senior Infrastructure Engineer"
    )
    assert dossier["company"] == "Stripe"
    assert len(dossier["common_interview_rounds"]) >= 3
    assert len(dossier["likely_tech_stack"]) > 0

    # 2. STAR evaluation async
    eval_res = await InterviewStudioEngine.evaluate_candidate_response_async(
        question="Tell me about a time you handled an architectural scaling bottleneck.",
        candidate_answer=(
            "At my previous startup, our order dispatch pipeline suffered from 2.5s p99 latency during flash sales. "
            "I was tasked with reducing latency to under 100ms. I designed an asynchronous Kafka event pipeline, "
            "implemented distributed Redis locking for inventory reservations, and tuned our connection pools. "
            "This slashed our p99 latency to 42ms and supported 15,000 orders/second with zero dropped transactions."
        ),
        role_title="Senior Backend Engineer",
        company_name="Zepto",
        key_concepts=["Kafka", "Redis", "Latency", "Throughput"]
    )
    assert eval_res["score"] >= 65
    assert eval_res["has_metrics"] is True
    assert "dimension_scores" in eval_res


@pytest.mark.asyncio
async def test_negotiation_async_rollout():
    """Validates generate_advanced_counter_script_async execution and fallback."""
    script = await SalaryNegotiationEngine.generate_advanced_counter_script_async(
        candidate_name="Satyajit Nayak",
        target_company="100xEngineers",
        role_title="AI Systems Engineer",
        current_base="12 LPA",
        current_equity="2 LPA",
        target_base="16 LPA",
        target_equity="4 LPA",
        competing_company="HyperVerge",
        competing_tc="15 LPA"
    )
    assert "negotiation_email" in script
    assert "phone_talking_points" in script
    assert "100xEngineers" in script["negotiation_email"]
    assert "16 LPA" in script["negotiation_email"]
    assert len(script["phone_talking_points"]) > 50


@pytest.mark.asyncio
async def test_cover_letter_async_rollout():
    """Validates generate_cover_letter_async using CoverLetterPrompts with anti-AI filtration."""
    profile = CandidateProfile(
        id="usr_test_cl",
        full_name="Rohit Verma",
        email="rohit@example.in",
        phone="+91 99887 76655",
        location="Pune, India",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
        projects=[
            Project(
                name="CloudQueue",
                description="High-scale distributed messaging broker",
                technologies=["Python", "Redis", "Docker"],
                metrics="handled 100k msg/sec"
            )
        ]
    )

    letter = await CoverLetterGenerator.generate_cover_letter_async(
        profile=profile,
        company_name="BrowserStack",
        job_title="Backend Systems Engineer",
        job_description="Developing real-time test execution grids."
    )
    assert "BrowserStack" in letter
    assert "Rohit Verma" in letter
    # Strict anti-AI validation
    assert CoverLetterGenerator.has_banned_cliches(letter) is False
