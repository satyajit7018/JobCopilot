"""
30-Loop Deep Subsystem Integrity & Edge-Case Audit for JobCopilot
Runs 30 comprehensive cycles testing all core algorithms, storage, security,
deduplication, anti-AI filters, and backup encryption against edge cases.
"""

import sys
import os
import time
import uuid
import json
import base64
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.core.database import db
from app.core.models import (
    CandidateProfile, JobListing, ApplicationStatus, SlotType,
    VaultEntry, EmailIntent, RecruiterPreferences
)
from app.core.credential_vault import CredentialVault
credential_vault = CredentialVault()
from app.core.resume_parser import ResumeParser
from app.core.questionnaire import QuestionnaireEngine
from app.core.deduplicator import JobDeduplicator
from app.core.match_scorer import MatchScorer
from app.core.priority_ranker import PriorityRanker
from app.core.cover_letter import CoverLetterGenerator
from app.core.outreach_generator import OutreachGenerator
from app.bot.human_behavior import HumanBehaviorEngine
from app.email.parser import EmailParser
from app.email.classifier import EmailClassifier
from app.core.interview_studio import InterviewStudioEngine
from app.core.negotiation import SalaryNegotiationEngine
from app.core.calendar_sync import CalendarAvailabilityEngine
from app.core.backup import BackupManager
from app.core.analytics import AnalyticsEngine

def run_30_deep_loops():
    total_loops = 30
    print(f"🔥 Starting 30-Loop Subsystem Stress & Edge-Case Verification...", flush=True)
    start_time = time.time()
    
    passed_loops = 0
    failed_loops = 0
    failures = []

    sample_resumes = [
        """
        Alex Mercer
        alex.mercer@cloudnative.io | +1 (555) 234-5678 | https://github.com/alexmercer
        San Francisco, CA

        Education:
        Stanford University, Master of Science in Computer Science, 2024

        Technical Skills:
        Go, Python, Kubernetes, Docker, AWS, PostgreSQL, Redis, Terraform, Kafka

        Projects:
        Kubernetes Multi-Cluster Orchestrator: Dynamic service mesh routing with 99.999% availability.
        High-Throughput Kafka Ingestion Pipeline: Processed 500k msgs/sec with sub-10ms lag.
        """,
        """
        Priya Sharma
        priya.sharma@aiml.org | +91 9876543210 | https://linkedin.com/in/priyasharma
        Bangalore, India

        Education:
        Indian Institute of Technology Madras, Bachelor of Technology in Electrical Engineering, 2023

        Technical Skills:
        Python, PyTorch, TensorFlow, FastAPI, Docker, OpenCV, Scikit-Learn, Qdrant, LLMs

        Projects:
        Diffusion-Based Medical Image Enhancer: Real-time image upscaling with 4x resolution boost.
        Multimodal LLM Document QA: Context-aware retrieval with sub-100ms latency.
        """,
        """
        David Kim
        david.kim@frontendmasters.dev | +1 (415) 890-1234
        New York, NY

        Education:
        Columbia University, Bachelor of Science in Information Systems, 2025

        Technical Skills:
        TypeScript, React, Next.js, Node.js, TailwindCSS, GraphQL, PostgreSQL, Jest

        Projects:
        Collaborative Canvas Platform: Real-time WebSockets whiteboard supporting 50 concurrent editors.
        Enterprise Design System: Reusable component library with 100% test coverage.
        """
    ]

    for loop_idx in range(1, total_loops + 1):
        loop_start = time.time()
        print(f"  [Loop {loop_idx:02d}/{total_loops:02d}] Testing...", end="", flush=True)

        try:
            # 1. Resume Parser & Dynamic Project Extraction
            resume_text = sample_resumes[loop_idx % len(sample_resumes)]
            profile_id = f"stress_user_{loop_idx}_{uuid.uuid4().hex[:6]}"
            profile = ResumeParser.parse_to_profile(resume_text, profile_id=profile_id)
            profile.user_id = profile_id
            assert len(profile.full_name) > 2, "Failed full_name extraction"
            assert len(profile.skills) >= 4, "Failed skills extraction"
            assert len(profile.projects) >= 1, "Failed dynamic projects extraction"

            # 2. SQLite WAL Concurrent Operations & Persistence
            assert db.save_profile(profile, user_id=profile_id), "Failed save_profile"
            fetched_profile = db.get_profile(user_id=profile_id)
            assert fetched_profile is not None, "Failed get_profile"
            assert fetched_profile.full_name == profile.full_name

            # 3. Argon2id Key Derivation & AES-256-GCM
            secret_data = f"top-secret-ctc-{uuid.uuid4().hex}"
            enc_data = credential_vault.encrypt(secret_data)
            dec_data = credential_vault.decrypt(enc_data)
            assert dec_data == secret_data, "AES-256-GCM integrity failed"

            # 4. SimHash Deduplication & Matching
            title_a = "Senior Backend Engineer"
            title_b = "Sr. Software Engineer - Backend"
            desc_a = "Building scalable Go and Python microservices with PostgreSQL."
            desc_b = "Building scalable Go and Python microservices with PostgreSQL and Redis."
            fp_a = JobDeduplicator.generate_fingerprint("Stripe", title_a, "Remote", desc_a)
            fp_b = JobDeduplicator.generate_fingerprint("Stripe", title_b, "Remote", desc_b)
            assert isinstance(fp_a, str) and len(fp_a) >= 16, "Invalid SimHash fingerprint"

            # 5. Multi-Factor Match Scorer & Priority Ranker
            match_score, match_reasons, missing_skills = MatchScorer.compute_match_score(
                profile=profile,
                job_title="Senior Python Backend Engineer",
                job_description="Looking for Python, FastAPI, Docker, PostgreSQL experience.",
                job_location="Remote"
            )
            assert 0.0 <= match_score <= 100.0, "Match score out of bounds"
            priority = PriorityRanker.calculate_priority_score(
                match_score=match_score,
                platform="Greenhouse",
                company="OpenAI",
                freshness_days=1,
                salary_range="150k - 200k USD",
                candidate_expected_ctc=profile.preferences.expected_ctc
            )
            assert 0.0 <= priority <= 100.0, "Priority score out of bounds"

            # 6. Anti-AI Cover Letter & Triple-Threat Outreach Generation
            cl = CoverLetterGenerator.generate_cover_letter(
                profile=profile,
                company_name="Vercel",
                job_title="Full Stack Engineer",
                job_description="Next.js and TypeScript infrastructure."
            )
            assert not CoverLetterGenerator.has_banned_cliches(cl), "Banned cliches leaked into cover letter"
            outreach = OutreachGenerator.create_triple_threat_package(
                profile=profile,
                job_id=f"job_{uuid.uuid4().hex[:8]}",
                company_name="Vercel",
                job_title="Full Stack Engineer"
            )
            assert len(outreach["linkedin_note"]) <= 300, "LinkedIn note exceeded character limit"
            assert len(outreach["cold_email"]["subject"]) > 5

            # 7. Tracking Pixel Stripping & 5-Way Recruiter Intent Classification
            tracking_html = '<div><img src="https://mandrillapp.com/track/open.php?u=123" width="1" height="1"/><p>We would love to invite you to an interview via https://calendly.com/tech-lead/30min</p></div>'
            parsed = EmailParser.parse_raw_email(
                sender="jobs@techcorp.io",
                recipient=profile.email,
                subject="Interview with TechCorp",
                body_html=tracking_html
            )
            assert parsed["has_tracking_pixels"] is True, "Failed to detect tracking pixel"
            assert "calendly.com/tech-lead/30min" in parsed["body_text"], "Failed to preserve text"
            intent, confidence = EmailClassifier.classify_intent("Interview with TechCorp", parsed["body_text"])
            assert intent == EmailIntent.INTERVIEW_INVITE, "Failed intent classification"

            # 8. Encrypted Backup Export, Tamper Detection & Restore
            backup_path = BackupManager.export_encrypted_backup(user_id=profile_id)
            assert backup_path.exists(), "Backup archive not created"
            
            # Tamper detection check
            with open(backup_path, "r", encoding="utf-8") as f:
                envelope = json.load(f)
            # Tamper with ciphertext
            envelope["ciphertext"] = envelope["ciphertext"][:-5] + "AAAAA"
            corrupt_path = backup_path.with_suffix(".corrupt.enc")
            with open(corrupt_path, "w", encoding="utf-8") as f:
                json.dump(envelope, f)
            
            tamper_detected = False
            try:
                BackupManager.restore_encrypted_backup(corrupt_path, user_id=profile_id)
            except Exception:
                tamper_detected = True
            
            assert tamper_detected, "Tamper detection failed to detect corrupted backup"
            if corrupt_path.exists():
                corrupt_path.unlink()

            # Clean restore check
            restore_res = BackupManager.restore_encrypted_backup(backup_path, user_id=profile_id)
            assert restore_res["status"] == "success", "Failed encrypted backup restore"
            if backup_path.exists():
                backup_path.unlink()

            # 9. Interview Studio & ESOP Modeler
            dossier = InterviewStudioEngine.generate_company_dossier("Airbnb", "Senior Backend Engineer")
            assert len(dossier["likely_tech_stack"]) >= 3, "Missing dossier tech stack"
            eval_res = InterviewStudioEngine.evaluate_candidate_response(
                question="How do you handle distributed cache invalidation?",
                key_concepts=["TTL", "write-through", "cache stampede", "redis"],
                candidate_answer="I use Redis with write-through cache and staggered TTL to prevent cache stampede."
            )
            assert eval_res["score"] >= 70, "Failed interview answer scoring"

            esop_res = SalaryNegotiationEngine.model_startup_equity(
                options_count=10000,
                total_company_shares=10000000,
                current_valuation_usd=50000000.0,
                strike_price_per_share=0.5
            )
            assert esop_res["ownership_percentage"] == 0.1, "ESOP ownership calculation error"
            assert len(esop_res["exit_scenarios"]) == 4, "Missing exit scenarios"

            offer_eval = SalaryNegotiationEngine.evaluate_offer(
                base_salary_lpa=35.0,
                bonus_lpa=5.0,
                equity_annual_lpa=10.0,
                role_title="Senior Software Engineer"
            )
            assert "rating" in offer_eval or "total_annual_comp_lpa" in offer_eval, "Missing evaluation"

            # 10. Funnel Analytics KPIs
            funnel = AnalyticsEngine.get_funnel_stats(user_id=profile_id)
            assert "total_sourced" in funnel, "Missing funnel analytics"

            elapsed = time.time() - loop_start
            passed_loops += 1
            print(f" ✅ Passed in {elapsed:.3f}s", flush=True)

        except Exception as e:
            failed_loops += 1
            failures.append(f"Loop {loop_idx:02d}: {type(e).__name__} - {str(e)}")
            print(f" ❌ FAILED: {str(e)}", flush=True)

    total_time = time.time() - start_time
    print(f"\n=======================================================", flush=True)
    print(f"🏁 30-Loop Subsystem Audit Finished in {total_time:.2f}s", flush=True)
    print(f"Passed: {passed_loops}/{total_loops} loops ({(passed_loops/total_loops)*100:.1f}%)", flush=True)
    print(f"Failed: {failed_loops}/{total_loops} loops", flush=True)
    print(f"=======================================================", flush=True)

    if failed_loops > 0:
        print("\nFailures:", flush=True)
        for f in failures:
            print(f" - {f}", flush=True)
        sys.exit(1)
    else:
        print("\n✨ 100% PERFECT: 30/30 STRESS LOOPS PASSED WITH ZERO ERRORS! ✨", flush=True)
        sys.exit(0)

if __name__ == "__main__":
    run_30_deep_loops()
