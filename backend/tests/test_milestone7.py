"""
JobCopilot - Milestone 7 Comprehensive Pytest Suite
Tests Voice Mock Interview Studio, Company Dossiers, Salary Negotiation,
Startup ESOP Modeler, and Zero-Collision Calendar Availability.
"""

import sys
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__parent__ if "__parent__" in locals() else __file__).parent.parent.resolve()))

from app.main import app
from app.core.interview_studio import InterviewStudioEngine
from app.core.negotiation import SalaryNegotiationEngine
from app.core.calendar_sync import CalendarAvailabilityEngine


class TestMilestone7:

    # 1. Test Company Dossier & Mock Questions
    def test_dossier_and_questions(self):
        dossier = InterviewStudioEngine.generate_company_dossier("Airbnb", "Distributed Systems Engineer")
        assert dossier["company"] == "Airbnb"
        assert len(dossier["likely_tech_stack"]) > 0

        questions = InterviewStudioEngine.generate_mock_questions("Distributed Systems Engineer", ["Python", "FastAPI", "Kafka"])
        assert len(questions) == 3
        assert "event streaming" in questions[0]["question"]

    # 2. Test Response Scoring Rubric
    def test_interview_response_scoring(self):
        good_answer = """
        I partition the Kafka topic by account ID for concurrency. 
        Each consumer uses Redis idempotency keys to ensure at-least-once delivery, 
        and failures route to a dead letter queue with Prometheus P99 latency tracking.
        """
        eval_good = InterviewStudioEngine.evaluate_candidate_response(
            question="Design 50k req/s pipeline",
            candidate_answer=good_answer,
            key_concepts=["Kafka", "Idempotency", "Partitioning", "Dead Letter Queue", "P99 Latency"]
        )
        assert eval_good["score"] >= 80
        assert eval_good["rating"] == "Excellent"

        short_answer = "A queue."
        eval_short = InterviewStudioEngine.evaluate_candidate_response(
            question="Design 50k req/s pipeline",
            candidate_answer=short_answer
        )
        assert eval_short["score"] <= 40
        assert eval_short["rating"] == "Needs Detail"

    # 3. Test Salary Benchmarking & ESOP Modeler
    def test_salary_and_equity_modeler(self):
        eval_offer = SalaryNegotiationEngine.evaluate_offer(
            base_salary_lpa=35.0,
            bonus_lpa=5.0,
            equity_annual_lpa=8.0,
            role_title="Senior Software Engineer"
        )
        assert eval_offer["total_annual_comp_lpa"] == 48.0
        assert eval_offer["rating"] == "Competitive"

        equity = SalaryNegotiationEngine.model_startup_equity(
            options_count=20000,
            total_company_shares=10000000,
            current_valuation_usd=100000000.0
        )
        assert equity["ownership_percentage"] == 0.2
        assert len(equity["exit_scenarios"]) == 4

    # 4. Test Calendar Availability
    def test_calendar_availability(self):
        slots = CalendarAvailabilityEngine.get_open_slots(timezone_str="IST", days_ahead=3)
        assert len(slots) > 0
        text = CalendarAvailabilityEngine.format_availability_email_text(slots)
        assert "Here are a few times" in text

    # 5. Test REST Endpoints
    @pytest.mark.asyncio
    async def test_milestone7_endpoints(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Dossier
            r1 = await ac.get("/api/interview/dossier?company=Uber&role=Staff+Engineer")
            assert r1.status_code == 200
            assert r1.json()["dossier"]["company"] == "Uber"

            # Negotiation
            r2 = await ac.post("/api/negotiation/evaluate", json={
                "base_salary_lpa": 35.0,
                "bonus_lpa": 5.0,
                "equity_annual_lpa": 10.0,
                "role_title": "Senior Software Engineer"
            })
            assert r2.status_code == 200
            assert r2.json()["evaluation"]["total_annual_comp_lpa"] == 50.0

            # Calendar
            r3 = await ac.get("/api/calendar/availability?timezone=IST&days=3")
            assert r3.status_code == 200
            assert len(r3.json()["slots"]) > 0
