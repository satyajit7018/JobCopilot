"""
JobCopilot - Milestone 1 End-to-End Test Suite
Tests data architecture, cryptographic vault, resume parser,
questionnaire auto-prefill, compensation engine, and hybrid vector vault.
"""

import os
import sys
import tempfile
import threading
from pathlib import Path
import pytest

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.core.models import (
    CandidateProfile, RecruiterPreferences, VaultEntry, JobListing,
    HITLEvent, EmailMessage, OutreachRecord, JobCheckpoint, SlotType,
    ApplicationStatus, EmailIntent, OutreachChannel, CategorizedSkills
)
from app.core.database import DatabaseManager
from app.core.credential_vault import CredentialVault
from app.core.resume_parser import ResumeParser
from app.core.questionnaire import QuestionnaireEngine
from app.core.compensation import CompensationConverter
from app.core.vector_vault import KnowledgeVault
from app.core.slot_matcher import SlotMatcher


class TestMilestone1:

    @pytest.fixture(autouse=True)
    def setup_temp_environment(self, tmp_path):
        """Creates isolated database and vault paths for test run."""
        self.db_path = tmp_path / "test_jobcopilot.db"
        self.vault_path = tmp_path / "test_vault.enc"
        self.db = DatabaseManager(self.db_path)
        self.cred_vault = CredentialVault(self.vault_path)

    # 1. Test Core Models
    def test_core_models(self):
        profile = CandidateProfile(
            full_name="Alex Mercer",
            email="alex@prototype.io",
            phone="+1 (555) 019-2831",
            location="San Francisco, CA",
            skills=["Python", "FastAPI", "Docker", "PyTorch"],
            categorized_skills=CategorizedSkills(
                languages=["Python"],
                frameworks=["FastAPI", "PyTorch"],
                cloud_devops=["Docker"]
            ),
            preferences=RecruiterPreferences(
                expected_ctc="140000 USD",
                current_ctc="110000 USD",
                target_currency="USD",
                years_of_experience=3.0
            )
        )
        dumped = profile.dict()
        assert dumped["full_name"] == "Alex Mercer"
        assert dumped["categorized_skills"]["frameworks"] == ["FastAPI", "PyTorch"]
        assert dumped["preferences"]["expected_ctc"] == "140000 USD"

    # 2. Test Database Engine & Concurrency
    def test_database_wal_and_concurrency(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"

        def worker(idx):
            job = JobListing(
                job_id=f"job_concurrent_{idx}",
                fingerprint=f"fp_concurrent_{idx}",
                platform="Greenhouse",
                company=f"Company_{idx}",
                title="Staff AI Engineer",
                url=f"https://boards.greenhouse.io/company/jobs/{idx}",
                salary_range="180k - 220k USD",
                seniority_level="Staff"
            )
            self.db.save_job(job)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()

        jobs = self.db.get_jobs()
        assert len(jobs) == 8

    # 3. Test Atomic HITL Resolution
    def test_hitl_atomic_resolution(self):
        event = HITLEvent(
            event_id="evt_test_atomic",
            job_id="job_concurrent_0",
            company="Anthropic",
            role_title="Research Engineer",
            question_text="Are you willing to relocate to SF?"
        )
        self.db.save_hitl_event(event)

        # First resolution
        assert self.db.resolve_hitl_event("evt_test_atomic", "Yes, fully willing to relocate.") is True
        # Second duplicate resolution must fail
        assert self.db.resolve_hitl_event("evt_test_atomic", "Duplicate answer") is False

    # 4. Test Cryptographic Vault
    def test_credential_vault_encryption(self):
        secrets = {"api_key": "sk-ant-secret12345", "token": "ghp_PersonalAccessToken"}
        self.cred_vault.save_secrets(secrets)
        loaded = self.cred_vault.load_secrets()
        assert loaded["api_key"] == "sk-ant-secret12345"

        phone = "+91 9988776655"
        enc = self.cred_vault.encrypt_field(phone)
        assert enc.startswith("enc:")
        assert self.cred_vault.decrypt_field(enc) == phone

    # 5. Test Resume Parser
    def test_resume_parser(self):
        text_resume = """
        Satyajit Nayak
        scorpionsatyajit@gmail.com | +91 7008053476
        https://linkedin.com/in/satyajit-nayak | https://github.com/satyajit7018
        Bangalore, India

        Education:
        Vellore Institute of Technology, Bachelor of Technology in Computer Science, 2025

        Technical Skills:
        Python, TypeScript, FastAPI, React, PyTorch, Docker, Kubernetes, AWS, PostgreSQL, Redis, Qdrant

        Projects:
        Multimodal Medical Imaging AI System: Diagnostic deep learning system with Grad-CAM interpretability and 96.19% accuracy.
        Vector Search Gateway: Semantic retrieval system with sub-50ms latency using Qdrant and Redis.
        """
        profile = ResumeParser.parse_to_profile(text_resume)
        assert profile.full_name == "Satyajit Nayak"
        assert profile.email == "scorpionsatyajit@gmail.com"
        assert "Python" in profile.categorized_skills.languages
        assert "FastAPI" in profile.categorized_skills.frameworks
        assert "Docker" in profile.categorized_skills.cloud_devops
        assert len(profile.projects) >= 2

    # 6. Test Questionnaire Auto-Prefill
    def test_questionnaire_prefill_and_apply(self):
        profile = CandidateProfile(
            full_name="Elena Vance",
            email="elena@vance.ai",
            phone="+1 (555) 901-2233",
            location="Seattle, WA",
            skills=["Python", "FastAPI", "AWS"],
            preferences=RecruiterPreferences(
                expected_ctc="25 LPA",
                notice_period_days=30,
                current_employer="Amazon"
            )
        )
        prefilled = QuestionnaireEngine.prefill_from_profile(profile)
        assert prefilled["full_name"] == "Elena Vance"
        assert prefilled["expected_ctc"] == "25 LPA"
        assert "Amazon" == prefilled["current_employer"]

        answers = {
            "expected_ctc": "30 LPA",
            "notice_period_days": 15,
            "work_authorization": "Citizen",
            "current_employer": "Google"
        }
        updated = QuestionnaireEngine.apply_answers_to_profile(profile, answers)
        assert updated.preferences.expected_ctc == "30 LPA"
        assert updated.preferences.notice_period_days == 15
        assert "Google" in updated.preferences.company_blacklist

    # 7. Test Compensation Multi-Currency Formatter
    def test_compensation_converter(self):
        base_inr = CompensationConverter.parse_to_base_inr("20 LPA")
        assert base_inr == 2000000.0

        usd_annual = CompensationConverter.format_for_ats(base_inr, "USD", "ANNUAL")
        usd_hourly = CompensationConverter.format_for_ats(base_inr, "USD", "HOURLY")
        eur_annual = CompensationConverter.format_for_ats(base_inr, "EUR", "ANNUAL")
        inr_monthly = CompensationConverter.format_for_ats(base_inr, "INR", "MONTHLY")

        assert "$" in usd_annual
        assert "/hr" in usd_hourly
        assert "€" in eur_annual
        assert "₹" in inr_monthly

    # 8. Test Hybrid Vector Vault
    def test_vector_vault_seeding_and_matching(self):
        vault_instance = KnowledgeVault()
        profile = CandidateProfile(
            full_name="Satyajit Nayak",
            email="scorpionsatyajit@gmail.com",
            phone="+91 7008053476",
            location="Bangalore, India",
            github_url="https://github.com/satyajit7018",
            skills=["Python", "FastAPI", "PyTorch", "Docker"],
            preferences=RecruiterPreferences(
                expected_ctc="24 LPA",
                notice_period_days=0,
                years_of_experience=2.0
            )
        )
        vault_instance.seed_from_profile(profile)

        # Test Salary Query
        ans_sal, score_sal, _ = vault_instance.query_answer("What is your expected salary?", profile=profile)
        assert ans_sal is not None and "24 LPA" in ans_sal

        # Test Availability Query
        ans_av, score_av, _ = vault_instance.query_answer("What is your notice period?", profile=profile)
        assert ans_av is not None and "0 days" in ans_av

        # Test Dynamic Company Essay Query
        ans_comp, score_comp, _ = vault_instance.query_answer(
            "Why do you want to work at our company?",
            profile=profile,
            company="OpenAI",
            domain="Generative AI"
        )
        assert ans_comp is not None and "OpenAI" in ans_comp and "Generative AI" in ans_comp
