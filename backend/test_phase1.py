#!/usr/bin/env python3
"""
JobCopilot - Phase 1 Verification Test Suite
Tests Resume Parsing, Vector Vault, Match Scorer, Priority Ranker, Dedup, and Encryption.
"""

import os
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.models import CandidateProfile, RecruiterPreferences, SlotType
from app.core.resume_parser import ResumeParser
from app.core.vector_vault import vault
from app.core.slot_matcher import SlotMatcher
from app.core.match_scorer import MatchScorer
from app.core.priority_ranker import PriorityRanker
from app.core.deduplicator import JobDeduplicator
from app.core.compensation import CompensationConverter
from app.core.credential_vault import cred_vault
from app.core.database import db

def run_tests():
    print("=================================================================")
    print("🧪 RUNNING JOBCOPILOT PHASE 1 VERIFICATION TEST SUITE")
    print("=================================================================\n")

    # 1. Test Resume Parser
    print("[TEST 1/6] Testing Universal Resume Parser...")
    sample_resume = """
    Satyajit Nayak
    scorpionsatyajit@gmail.com | +91 7008053476 | https://linkedin.com/in/satyajit-nayak
    Vellore Institute of Technology (VIT), 2025
    Technical Skills: Python, FastAPI, Docker, PyTorch, Machine Learning, Computer Vision, Qdrant, Redis
    Projects: Multimodal Medical Imaging AI System with 96.19% classification accuracy using ResNet50.
    Certifications: AWS Certified Solutions Architect – Associate
    """
    profile = ResumeParser.parse_to_profile(sample_resume, profile_id="test_user_1")
    assert profile.full_name == "Satyajit Nayak", f"Failed: name={profile.full_name}"
    assert profile.email == "scorpionsatyajit@gmail.com", f"Failed: email={profile.email}"
    assert "Python" in profile.skills and "PyTorch" in profile.skills, "Failed: skills missing"
    assert len(profile.certifications) > 0, "Failed: certifications missing"
    db.save_profile(profile)
    print("  ✅ Resume Parser passed! Structured profile generated and saved.")

    # 2. Test Knowledge Vault & Semantic Slot Retrieval
    print("\n[TEST 2/6] Testing Knowledge Vault & Semantic Slot Retrieval...")
    # Test salary retrieval
    ans_salary, score_sal, entry_sal = vault.query_answer("What is your expected salary / CTC?", profile=profile)
    assert ans_salary is not None, "Failed: salary query returned None"
    assert "15 LPA" in ans_salary, f"Failed: expected 15 LPA in answer, got {ans_salary}"
    print(f"  ✅ Salary query matched with score {score_sal:.2f}: \"{ans_salary}\"")

    # Test why join company retrieval with dynamic parameter injection
    ans_why, score_why, entry_why = vault.query_answer(
        "Why do you want to work at our company?", 
        profile=profile, 
        company="Razorpay", 
        domain="FinTech & Payments"
    )
    assert "Razorpay" in ans_why and "FinTech & Payments" in ans_why, f"Failed: dynamic variables not replaced in {ans_why}"
    print(f"  ✅ Dynamic templating matched with score {score_why:.2f}: \"{ans_why[:80]}...\"")

    # 3. Test Deduplicator
    print("\n[TEST 3/6] Testing Cross-Platform Job Deduplication...")
    fp1 = JobDeduplicator.generate_fingerprint("SuperKalam (YC W23)", "AI Applied Engineer", "Bangalore")
    fp2 = JobDeduplicator.generate_fingerprint("SuperKalam", "AI Applied Engineer", "Bangalore")
    assert fp1 == fp2, f"Failed: fingerprint mismatch ({fp1} != {fp2})"
    print(f"  ✅ Deduplication passed! Both platform variants produced hash: {fp1}")

    # 4. Test Match Scorer & Priority Ranker
    print("\n[TEST 4/6] Testing Match Scorer & Priority Ranker...")
    ai_jd = "Looking for an AI / Machine Learning Engineer with experience in Python, PyTorch, FastAPI, and Docker."
    chef_jd = "Looking for a Head Chef with Italian culinary experience."

    ai_match = MatchScorer.compute_match_score(profile, "AI Engineer", ai_jd)
    chef_match = MatchScorer.compute_match_score(profile, "Head Chef", chef_jd)
    
    assert ai_match >= 0.65, f"Failed: AI match score {ai_match} too low"
    assert chef_match <= 0.35, f"Failed: Chef match score {chef_match} too high"

    ai_priority = PriorityRanker.calculate_priority_score(ai_match, "Y Combinator", "SuperKalam", freshness_days=1)
    print(f"  ✅ Match Scorer passed! AI Role Match: {ai_match*100:.1f}% (Priority: {ai_priority}/100) vs Chef Match: {chef_match*100:.1f}%")

    # 5. Test Multi-Currency Compensation Converter
    print("\n[TEST 5/6] Testing Multi-Currency Compensation Converter...")
    base_inr = CompensationConverter.parse_ctc("15 LPA")
    usd_annual = CompensationConverter.format_for_ats(base_inr, target_currency="USD", unit="ANNUAL")
    usd_hourly = CompensationConverter.format_for_ats(base_inr, target_currency="USD", unit="HOURLY")
    inr_monthly = CompensationConverter.format_for_ats(base_inr, target_currency="INR", unit="MONTHLY")
    
    assert "$" in usd_annual and "/hr" in usd_hourly and "₹" in inr_monthly, "Failed: currency formatting"
    print(f"  ✅ Compensation Converter passed! 15 LPA = {usd_annual} | {usd_hourly} | {inr_monthly}")

    # 6. Test AES-256 Credential Vault
    print("\n[TEST 6/6] Testing AES-256 Encrypted Credential Vault...")
    test_secrets = {"github_token": "ghp_secure_token_12345", "wellfound_session": "sess_cookie_9988"}
    cred_vault.save_secrets(test_secrets, master_password="test_secret_master_password")
    loaded = cred_vault.load_secrets(master_password="test_secret_master_password")
    assert loaded.get("github_token") == "ghp_secure_token_12345", "Failed: credential decrypted mismatch"
    print("  ✅ AES-256 Credential Vault passed! Encrypted payload verified.")

    print("\n=================================================================")
    print("🎉 ALL PHASE 1 CORE MODULES PASSED VERIFICATION TEST!")
    print("=================================================================\n")

if __name__ == "__main__":
    run_tests()
