"""
JobCopilot - Comprehensive Test Suite for Career Acceleration Pillars:
1. Multi-Track Reverse Interview Questions
2. Interviewer Persona Recon & Engineering Blog Intel
3. Multi-Offer 4-Year TC Progression Matrix & Advanced Counter-Offer Scripts
4. Alumni Referral (280-char note + email) & 5-Day Recruiter Follow-Up Nudges
5. Interview Invitation Broadcast & Custom Mock Generation
"""

import sys
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.main import app
from app.core.interview_studio import InterviewStudioEngine
from app.core.negotiation import SalaryNegotiationEngine
from app.core.outreach_generator import OutreachGenerator


class TestCareerAccelerationPillars:

    # 1. Reverse-Interview Questions
    def test_reverse_interview_questions_generation(self):
        questions = InterviewStudioEngine.generate_reverse_interview_questions(
            role_title="Staff Distributed Systems Engineer",
            company_name="Stripe"
        )
        assert len(questions) == 3
        themes = [q["theme"] for q in questions]
        assert any("Distributed Systems" in t or "Technical Debt" in t or "Team Culture" in t for t in themes)
        for q in questions:
            assert len(q["question"]) > 20

    # 2. Interviewer Recon & Engineering Intel
    def test_interviewer_recon_and_intel(self):
        recon = InterviewStudioEngine.analyze_interviewer_profile(
            interviewer_name="Sarah Chen",
            interviewer_role="Principal Architect (ex-Amazon Bar Raiser)"
        )
        assert "Bar Raiser" in recon["inferred_persona"]
        assert len(recon["tactical_tips"]) >= 3
        assert "leadership principles" in recon["core_focus"].lower()

        intel = InterviewStudioEngine.get_company_engineering_intel("Uber")
        assert intel["company"] == "Uber"
        assert len(intel["recent_initiatives"]) >= 2
        assert any("H3" in init or "Uber" in init or "microservices" in init for init in intel["recent_initiatives"])

    # 3. Multi-Offer Comparison Matrix
    def test_multi_offer_comparison(self):
        offers = [
            {
                "company": "Stripe",
                "base_lpa": 50.0,
                "bonus_lpa": 10.0,
                "equity_grant_total_lpa": 60.0,
                "sign_on_lpa": 15.0,
                "role_title": "Staff Engineer"
            },
            {
                "company": "Uber",
                "base_lpa": 45.0,
                "bonus_lpa": 8.0,
                "equity_grant_total_lpa": 80.0,
                "sign_on_lpa": 10.0,
                "role_title": "Staff Engineer"
            }
        ]
        comparison = SalaryNegotiationEngine.compare_multiple_offers(offers)
        assert comparison["status"] == "success"
        assert len(comparison["offers_comparison"]) == 2
        stripe = next(o for o in comparison["offers_comparison"] if o["company"] == "Stripe")
        assert stripe["year_1_tc"] == 90.0
        assert stripe["four_year_cumulative_tc"] == 315.0
        assert comparison["top_year_1_company"] == "Stripe"
        assert comparison["highest_year_1_tc"] == 90.0

    # 4. Advanced Counter Script Generator
    def test_advanced_counter_script(self):
        scripts = SalaryNegotiationEngine.generate_advanced_counter_script(
            candidate_name="Alex Mercer",
            target_company="Stripe",
            role_title="Staff Engineer",
            current_base="45 LPA",
            current_equity="15 LPA/yr",
            target_base="52 LPA",
            target_equity="20 LPA/yr",
            competing_company="Uber",
            competing_tc="75 LPA"
        )
        assert "Alex Mercer" in scripts["negotiation_email"]
        assert "Uber" in scripts["negotiation_email"]
        assert "52 LPA" in scripts["negotiation_email"]
        assert "Express strong enthusiasm" in scripts["phone_talking_points"]

    # 5. Alumni Referral Pitch & Recruiter Nudge
    def test_alumni_and_recruiter_outreach(self):
        pitch = OutreachGenerator.generate_alumni_referral_pitch(
            candidate_name="Alex Mercer",
            company_name="Netflix",
            role_title="Senior Platform Engineer",
            contact_name="Jordan",
            common_ground="our university alumni network"
        )
        assert len(pitch["linkedin_note_280"]) <= 280
        assert "Jordan" in pitch["linkedin_note_280"]
        assert "Netflix" in pitch["email_subject"]

        nudge = OutreachGenerator.generate_recruiter_followup_nudge(
            candidate_name="Alex Mercer",
            company_name="Netflix",
            role_title="Senior Platform Engineer",
            recruiter_name="Sarah",
            days_elapsed=5
        )
        assert "Following up" in nudge["subject"]
        assert "5 business days" in nudge["body"]
        assert "Alex Mercer" in nudge["body"]

    # 6. REST API Endpoints Integration
    @pytest.mark.asyncio
    async def test_career_acceleration_endpoints(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Reverse Questions Endpoint
            r1 = await ac.get("/api/interview/reverse-questions?role=Senior+Backend+Engineer&company=Netflix")
            assert r1.status_code == 200
            assert len(r1.json()["questions"]) == 3

            # 2. Interviewer Recon Endpoint
            r2 = await ac.post("/api/interview/interviewer-recon", json={
                "interviewer_name": "Marcus Aurelius",
                "interviewer_role": "Director of Engineering"
            })
            assert r2.status_code == 200
            assert "Engineering Manager" in r2.json()["recon"]["inferred_persona"]

            # 3. Engineering Intel Endpoint
            r3 = await ac.get("/api/interview/engineering-intel?company=Stripe")
            assert r3.status_code == 200
            assert len(r3.json()["intel"]["recent_initiatives"]) >= 2

            # 4. Multi-Offer Compare Endpoint
            r4 = await ac.post("/api/salary/compare-offers", json={
                "offers": [
                    {"company": "Google", "base_lpa": 50, "bonus_lpa": 10, "equity_grant_total_lpa": 60, "sign_on_lpa": 10, "role_title": "L5"},
                    {"company": "Meta", "base_lpa": 52, "bonus_lpa": 12, "equity_grant_total_lpa": 80, "sign_on_lpa": 15, "role_title": "E5"}
                ]
            })
            assert r4.status_code == 200
            assert len(r4.json()["offers_comparison"]) == 2

            # 5. Advanced Counter Script Endpoint
            r5 = await ac.post("/api/salary/counter-script", json={
                "candidate_name": "Alex Mercer",
                "target_company": "Google",
                "role_title": "L5 Software Engineer",
                "current_base": "50 LPA",
                "current_equity": "15 LPA",
                "target_base": "56 LPA",
                "target_equity": "20 LPA",
                "competing_company": "Meta",
                "competing_tc": "85 LPA"
            })
            assert r5.status_code == 200
            assert "scripts" in r5.json()

            # 6. Alumni Referral Endpoint
            r6 = await ac.post("/api/outreach/alumni-referral", json={
                "candidate_name": "Alex Mercer",
                "company_name": "Google",
                "role_title": "Software Engineer",
                "contact_name": "David"
            })
            assert r6.status_code == 200
            assert "pitch" in r6.json()

            # 7. Recruiter Nudge Endpoint
            r7 = await ac.post("/api/outreach/recruiter-nudge", json={
                "candidate_name": "Alex Mercer",
                "company_name": "Google",
                "role_title": "Software Engineer",
                "recruiter_name": "Jessica",
                "days_elapsed": 6
            })
            assert r7.status_code == 200
            assert "nudge" in r7.json()
