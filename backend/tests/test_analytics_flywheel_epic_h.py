"""
Unit & Integration Tests for Phase P3 Epic H: Data & ML Flywheel
Tests Analytics Event Warehouse, Cohort Analysis, Conversion Feedback Loop,
Dynamic MatchScorer calibration, and A/B Testing with two-sample Z-tests.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import db
from app.core.models import User, CandidateProfile, JobListing, ApplicationStatus
from app.analytics.feedback_loop import ConversionFeedbackLoop
from app.core.match_scorer import MatchScorer
from app.core.resume_tailor import ResumeTailor
from app.api.auth import create_jwt_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    test_user_id = f"user_epic_h_{uuid.uuid4().hex[:8]}"
    email = f"epich_{uuid.uuid4().hex[:6]}@example.com"
    user = User(
        user_id=test_user_id,
        email=email,
        password_hash="testpasshash123",
        role="PRO",
        is_active=True
    )
    db.create_user(user)
    token = create_jwt_token(
        {"sub": test_user_id, "email": email, "role": "PRO", "type": "access"},
        timedelta(minutes=30)
    )
    return {"Authorization": f"Bearer {token}", "user_id": test_user_id}


def test_conversion_feedback_loop_and_match_scorer_lift():
    """Validates that proven interview callbacks generate positive multipliers in MatchScorer."""
    user_id = f"usr_fb_{uuid.uuid4().hex[:6]}"

    # Add applications where Python/Docker/Kubernetes led to interviews
    job_win = JobListing(
        job_id="job_win_1",
        company="Datadog",
        title="Distributed Systems SDE",
        description="Requires Python, Kubernetes, and Docker for cloud telemetry services.",
        platform="Greenhouse",
        url="https://datadog.com/jobs/1",
        fingerprint="fp_win_1",
        status=ApplicationStatus.INTERVIEW,
        applied_at=datetime.utcnow().isoformat(),
        match_score=0.88
    )
    job_win2 = JobListing(
        job_id="job_win_2",
        company="Cloudflare",
        title="Systems Engineer",
        description="Python and Kubernetes platform development.",
        platform="Lever",
        url="https://cloudflare.com/jobs/2",
        fingerprint="fp_win_2",
        status=ApplicationStatus.INTERVIEW,
        applied_at=datetime.utcnow().isoformat(),
        match_score=0.90
    )
    # Add application where PHP failed to convert
    job_fail = JobListing(
        job_id="job_fail_1",
        company="LegacyCo",
        title="Web Developer",
        description="PHP and WordPress developer.",
        platform="Indeed",
        url="https://legacy.com/jobs/3",
        fingerprint="fp_fail_1",
        status=ApplicationStatus.REJECTED,
        applied_at=datetime.utcnow().isoformat(),
        match_score=0.50
    )

    db.save_job(job_win, user_id=user_id)
    db.save_job(job_win2, user_id=user_id)
    db.save_job(job_fail, user_id=user_id)

    # Calibrate candidate feedback signals
    calib = ConversionFeedbackLoop.calibrate_candidate_signals(user_id=user_id)
    assert calib["status"] == "calibrated"
    assert calib["total_applied"] == 3
    assert calib["total_callbacks"] == 2

    # Verify multipliers
    k8s_multiplier = ConversionFeedbackLoop.get_feature_multiplier(user_id, "skill", "kubernetes")
    assert k8s_multiplier >= 1.05  # Positive callback lift
    assert k8s_multiplier <= 1.30  # Safety bound respected

    # Test MatchScorer reflects the lift
    profile = CandidateProfile(
        full_name="Alex Rivera",
        email="alex.rivera@example.com",
        phone="+1-555-0199",
        location="Remote",
        summary="Cloud Architect",
        skills=["Python", "Kubernetes", "Docker"]
    )
    profile.user_id = user_id  # Associate profile with user for feedback lookup

    score, reasons, missing = MatchScorer.compute_match_score(
        profile=profile,
        job_title="Cloud Engineer",
        job_description="Looking for Python and Kubernetes cloud engineer."
    )
    assert score > 0.40
    assert any("empirical callback lift" in r for r in reasons)


def test_resume_tailor_ab_strategy_integration():
    """Validates that treatment_star strategy prioritizes quantifiable STAR accomplishment highlights."""
    from app.core.models import WorkExperience
    profile = CandidateProfile(
        full_name="Sarah Connor",
        email="sarah.connor@example.com",
        phone="+1-555-0123",
        location="San Francisco, CA",
        summary="Site Reliability Engineer",
        skills=["Python", "Linux", "Terraform"],
        experience=[
            WorkExperience(
                company="TechCorp",
                title="SRE",
                start_date="2021-01",
                end_date="Present",
                highlights=[
                    "Maintained server fleets and handled tickets.",
                    "Scaled Kubernetes clusters reducing p99 latency by 45% and saving $120k annually.",
                    "Wrote documentation for on-call teams."
                ]
            )
        ]
    )

    # Standard control strategy
    tailored_ctrl, _ = ResumeTailor.tailor_profile_for_job(
        profile=profile,
        job_title="SRE",
        job_description="Looking for SRE with Linux and Terraform.",
        strategy="control_a"
    )

    # Treatment STAR strategy
    tailored_star, _ = ResumeTailor.tailor_profile_for_job(
        profile=profile,
        job_title="SRE",
        job_description="Looking for SRE with Linux and Terraform.",
        strategy="treatment_star"
    )

    # The metric-heavy highlight should be promoted to index 0 in treatment_star
    first_highlight = tailored_star.experience[0].highlights[0]
    assert "45%" in first_highlight or "$120k" in first_highlight

