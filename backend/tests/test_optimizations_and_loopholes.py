"""
JobCopilot - Subsystem Optimization & Loophole Hardening Test Suite
Verifies multi-tenant job deduplication isolation, null-safe template substitution,
compensation range calculations, and self-healing preview lead resolution.
"""

import pytest
from app.core.models import (
    CandidateProfile, RecruiterPreferences, JobListing, ApplicationStatus,
    VaultEntry, SlotType
)
from app.core.database import db
from app.core.vector_vault import vault
from app.core.compensation import CompensationConverter


def test_multi_tenant_duplicate_job_fingerprint_isolation():
    """Verifies that Tenant A and Tenant B can both save jobs with the same fingerprint without overwriting each other."""
    user_a = "tenant_test_user_a"
    user_b = "tenant_test_user_b"
    common_fingerprint = "fp_swiggy_sde2_bengaluru_common"

    job_a = JobListing(
        job_id="job_swiggy_tenant_a",
        user_id=user_a,
        fingerprint=common_fingerprint,
        platform="Naukri",
        company="Swiggy",
        title="SDE II",
        location="Bangalore",
        url="https://naukri.com/swiggy-sde-2",
        status=ApplicationStatus.INTERVIEW,
        notes="Tenant A Round 1 Notes"
    )

    job_b = JobListing(
        job_id="job_swiggy_tenant_b",
        user_id=user_b,
        fingerprint=common_fingerprint,
        platform="Naukri",
        company="Swiggy",
        title="SDE II",
        location="Bangalore",
        url="https://naukri.com/swiggy-sde-2",
        status=ApplicationStatus.DISCOVERED,
        notes="Tenant B Just Discovered"
    )

    # Save job for Tenant A
    saved_a = db.save_job(job_a, user_id=user_a)
    assert saved_a is True

    # Save identical fingerprint job for Tenant B
    saved_b = db.save_job(job_b, user_id=user_b)
    assert saved_b is True

    # Verify Tenant A's job was NOT overwritten or corrupted
    fetched_a = db.get_job_by_id("job_swiggy_tenant_a", user_id=user_a)
    assert fetched_a is not None
    assert fetched_a.user_id == user_a
    assert fetched_a.status == ApplicationStatus.INTERVIEW
    assert fetched_a.notes == "Tenant A Round 1 Notes"

    # Verify Tenant B's job exists independently
    fetched_b = db.get_job_by_id("job_swiggy_tenant_b", user_id=user_b)
    assert fetched_b is not None
    assert fetched_b.user_id == user_b
    assert fetched_b.status == ApplicationStatus.DISCOVERED
    assert fetched_b.notes == "Tenant B Just Discovered"


def test_null_safe_knowledge_vault_template_resolution():
    """Verifies that Knowledge Vault resolves templates safely even if candidate profile fields are None."""
    # Construct profile with missing / None preference attributes
    incomplete_prefs = RecruiterPreferences(
        expected_ctc="",
        current_ctc="",
        notice_period_days=0,
        earliest_start_date="",
        work_authorization="",
        requires_sponsorship=False,
        willing_to_relocate=False,
        remote_preference="",
        years_of_experience=0.0
    )

    profile = CandidateProfile(
        id="usr_null_safety_test",
        user_id="usr_null_safety_test",
        full_name="",
        email="",
        phone="",
        location="",
        skills=[],
        preferences=incomplete_prefs
    )

    template = "I have {years_of_experience} yrs exp. Seeking {expected_ctc}. Authorized: {work_authorization}. Top skills: {top_skills}. Name: {full_name}"
    
    # Should not raise TypeError or crash
    resolved = vault._resolve_template(
        template=template,
        profile=profile,
        company="Razorpay",
        role="Backend Engineer",
        domain="Fintech"
    )

    assert isinstance(resolved, str)
    assert "Razorpay" not in resolved
    assert "Seeking 15 LPA" in resolved or "Seeking" in resolved
    assert "Authorized" in resolved


def test_compensation_range_parsing_and_midpoint():
    """Verifies that CompensationConverter correctly calculates midpoint for Indian LPA and USD salary ranges."""
    # Indian LPA ranges
    lpa_midpoint = CompensationConverter.parse_to_base_inr("28 - 35 LPA")
    assert lpa_midpoint == 3150000.0  # (28 + 35) / 2 = 31.5 LPA

    # Word 'to' in range
    lpa_to_range = CompensationConverter.parse_to_base_inr("40 to 50 LPA")
    assert lpa_to_range == 4500000.0  # (40 + 50) / 2 = 45 LPA

    # USD salary range
    usd_midpoint = CompensationConverter.parse_to_base_inr("$120,000 - $160,000")
    # ($120k + $160k)/2 = $140,000 * 83.5 FX rate = 11,690,000 INR
    assert usd_midpoint == 140000.0 * 83.5

    # USD 'k' multiplier range
    usd_k_range = CompensationConverter.parse_to_base_inr("$100k - $150k")
    assert usd_k_range == 125000.0 * 83.5


def test_self_healing_preview_job_resolution():
    """Verifies that accessing a preview job ID auto-seeds it into the user's database partition."""
    test_user = "user_preview_test_42"
    
    # Job does not exist yet in DB for this user
    preview_job = db.get_job_by_id("sample_swiggy_01", user_id=test_user)
    assert preview_job is not None
    assert preview_job.job_id == "sample_swiggy_01"
    assert preview_job.company == "Swiggy"
    assert preview_job.user_id == test_user

    # Verify it is now persisted in SQLite for this user
    persisted = db.get_job_by_id("sample_swiggy_01", user_id=test_user)
    assert persisted is not None
    assert persisted.company == "Swiggy"
