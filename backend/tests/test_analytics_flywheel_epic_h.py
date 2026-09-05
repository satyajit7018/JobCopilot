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
from app.analytics.warehouse import AnalyticsWarehouse
from app.analytics.feedback_loop import ConversionFeedbackLoop
from app.analytics.ab_testing import ABTestingEngine
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


def test_analytics_warehouse_event_ingestion_and_isolation():
    """Validates that events are recorded and queryable with tenant isolation."""
    user_a = f"usr_a_{uuid.uuid4().hex[:6]}"
    user_b = f"usr_b_{uuid.uuid4().hex[:6]}"

    ev_a = AnalyticsWarehouse.track_event(
        user_id=user_a,
        event_type="job.discovered",
        entity_type="job",
        entity_id="job_001",
        properties={"title": "Staff Engineer", "platform": "Greenhouse"}
    )
    assert ev_a.event_id is not None

    ev_b = AnalyticsWarehouse.track_event(
        user_id=user_b,
        event_type="job.applied",
        entity_type="job",
        entity_id="job_002",
        properties={"submission_mode": "LIVE"}
    )
    assert ev_b.event_id is not None

    events_a = db.query_analytics_events(user_id=user_a)
    assert any(e.event_id == ev_a.event_id for e in events_a)
    assert not any(e.event_id == ev_b.event_id for e in events_a)


def test_cohort_analysis_and_velocity():
    """Validates funnel cohort grouping by date and velocity metrics."""
    user_id = f"usr_cohort_{uuid.uuid4().hex[:6]}"

    now = datetime.utcnow()
    # Week 1 application (Converted to Interview)
    job1 = JobListing(
        job_id="job_c1",
        company="Stripe",
        title="Backend Engineer",
        platform="Greenhouse",
        url="https://stripe.com/jobs/c1",
        fingerprint="fp_c1",
        status=ApplicationStatus.INTERVIEW,
        applied_at=(now - timedelta(days=14)).isoformat(),
        created_at=(now - timedelta(days=14)).isoformat(),
        interview_date=(now - timedelta(days=10)).isoformat(),
        match_score=0.92
    )
    # Week 1 application (Rejected)
    job2 = JobListing(
        job_id="job_c2",
        company="Uber",
        title="Infrastructure Engineer",
        platform="Greenhouse",
        url="https://uber.com/jobs/c2",
        fingerprint="fp_c2",
        status=ApplicationStatus.REJECTED,
        applied_at=(now - timedelta(days=12)).isoformat(),
        created_at=(now - timedelta(days=12)).isoformat(),
        match_score=0.85
    )
    # Week 2 application (Converted to Offer)
    job3 = JobListing(
        job_id="job_c3",
        company="Figma",
        title="Senior Platform Engineer",
        platform="Lever",
        url="https://figma.com/jobs/c3",
        fingerprint="fp_c3",
        status=ApplicationStatus.OFFER,
        applied_at=(now - timedelta(days=5)).isoformat(),
        created_at=(now - timedelta(days=5)).isoformat(),
        interview_date=(now - timedelta(days=2)).isoformat(),
        match_score=0.95
    )

    db.save_job(job1, user_id=user_id)
    db.save_job(job2, user_id=user_id)
    db.save_job(job3, user_id=user_id)

    cohorts = AnalyticsWarehouse.get_funnel_cohorts(user_id=user_id, interval="weekly")
    assert len(cohorts) >= 1
    total_apps = sum(c["total_applied"] for c in cohorts)
    assert total_apps == 3
    total_interviews = sum(c["interviews_count"] for c in cohorts)
    assert total_interviews == 2  # job1 + job3 (offer implies interview)

    platforms = AnalyticsWarehouse.get_platform_conversion_analytics(user_id=user_id)
    assert "Greenhouse" in platforms
    assert "Lever" in platforms
    assert platforms["Lever"]["callback_rate_percent"] == 100.0

    velocity = AnalyticsWarehouse.get_velocity_benchmarks(user_id=user_id)
    assert velocity["total_tracked_responses"] >= 2
    assert velocity["median_days_to_first_response"] is not None


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


def test_ab_testing_deterministic_assignment_and_significance():
    """Validates deterministic variant routing, conversion recording, and statistical Z-test."""
    user_id = f"usr_ab_{uuid.uuid4().hex[:6]}"

    experiment = ABTestingEngine.create_experiment(
        user_id=user_id,
        name="Tailoring Strategy Test",
        description="Comparing standard keyword vs STAR narrative bullets"
    )
    exp_id = experiment.experiment_id

    # Test deterministic assignment: same entity always gets the same variant
    entity_1 = "job_apply_101"
    variant_call_1 = ABTestingEngine.assign_variant(exp_id, user_id, entity_1)
    variant_call_2 = ABTestingEngine.assign_variant(exp_id, user_id, entity_1)
    assert variant_call_1 == variant_call_2
    assert variant_call_1 in ("control_a", "variant_b")

    # Populate 15 samples per variant to enable statistical evaluation
    # Control: 15 samples, 2 conversions (13.3%)
    for i in range(15):
        eid = f"control_entity_{i}"
        db.assign_ab_variant(exp_id, user_id, eid, "control_a")
        if i < 2:
            ABTestingEngine.record_conversion(exp_id, user_id, eid)

    # Treatment: 15 samples, 10 conversions (66.7%)
    for i in range(15):
        eid = f"variant_entity_{i}"
        db.assign_ab_variant(exp_id, user_id, eid, "variant_b")
        if i < 10:
            ABTestingEngine.record_conversion(exp_id, user_id, eid)

    evaluation = ABTestingEngine.evaluate_experiment(exp_id, user_id)
    assert evaluation["total_samples"] == 31
    assert evaluation["significance_tested"] is True
    assert evaluation["is_statistically_significant"] is True
    assert evaluation["p_value"] < 0.05
    assert evaluation["winner"] == "variant_b"
    assert evaluation["z_score"] is not None


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


def test_analytics_rest_api_endpoints(client, auth_headers):
    """Validates full REST API endpoints for analytics events, cohorts, conversions, and experiments."""
    headers = {"Authorization": auth_headers["Authorization"]}

    # 1. Post telemetry event
    res_ev = client.post(
        "/api/analytics/events",
        json={"event_type": "resume.tailored", "entity_type": "job", "entity_id": "job_999", "properties": {"version": 2}},
        headers=headers
    )
    assert res_ev.status_code == 200
    assert res_ev.json()["status"] == "success"

    # 2. List events
    res_list = client.get("/api/analytics/events", headers=headers)
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1

    # 3. Get cohorts
    res_cohorts = client.get("/api/analytics/cohorts?interval=weekly", headers=headers)
    assert res_cohorts.status_code == 200
    assert "cohorts" in res_cohorts.json()

    # 4. Get conversions & velocity
    res_conv = client.get("/api/analytics/conversions", headers=headers)
    assert res_conv.status_code == 200
    data_conv = res_conv.json()
    assert "insights" in data_conv
    assert "platforms" in data_conv
    assert "velocity_benchmarks" in data_conv

    # 5. Create A/B experiment
    res_exp = client.post(
        "/api/analytics/experiments",
        json={"name": "Outreach Subject Line Test", "description": "Testing friendly vs executive"},
        headers=headers
    )
    assert res_exp.status_code == 200
    exp_id = res_exp.json()["experiment"]["experiment_id"]

    # 6. List A/B experiments
    res_exp_list = client.get("/api/analytics/experiments", headers=headers)
    assert res_exp_list.status_code == 200
    assert any(e["experiment_id"] == exp_id for e in res_exp_list.json()["experiments"])

    # 7. Evaluate A/B experiment
    res_eval = client.post(f"/api/analytics/experiments/{exp_id}/evaluate", headers=headers)
    assert res_eval.status_code == 200
    assert res_eval.json()["status"] == "success"
