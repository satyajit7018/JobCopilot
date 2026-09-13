"""
Unit tests for PR D: Match-Reason Coherence & Seniority Calibration (Issue #4).
Ensures:
1. Senior roles with words like 'internal' in description are not misclassified as 'Intern'.
2. Empty/uncalibrated profiles do not produce contradictory '0.0 yrs fits Intern requirements'
   reasons or 99% scores for senior engineering roles.
3. Empty profiles receive provisional capped scores with calibration guidance.
"""

from app.core.match_scorer import MatchScorer
from app.core.models import CandidateProfile, RecruiterPreferences


class TestMatchReasonCoherence:

    def test_senior_role_with_internal_tools_not_classified_as_intern(self):
        """Word 'internal' in job description must not trigger 'Intern' seniority."""
        title = "Senior Backend Engineer"
        jd = "Join our team to build high-scale internal developer tools, infrastructure, and distributed systems."
        seniority = MatchScorer.infer_job_seniority(title, jd)
        assert seniority == "Senior"

    def test_intern_role_properly_classified(self):
        """Actual intern titles must be classified as 'Intern'."""
        assert MatchScorer.infer_job_seniority("Software Engineering Intern", "Summer internship program") == "Intern"
        assert MatchScorer.infer_job_seniority("Backend Developer", "3-month internship for university students") == "Intern"

    def test_empty_profile_for_senior_role_yields_provisional_score(self):
        """Empty profile must receive provisional score <= 0.35 without intern contradictions."""
        empty_profile = CandidateProfile(
            full_name="New User",
            email="newuser@example.com",
            phone="+1-555-0100",
            location="Remote",
            skills=[],
            preferences=RecruiterPreferences(years_of_experience=0.0)
        )

        title = "Senior Distributed Systems Architect"
        jd = "Leading internal architecture migrations using Go, Kubernetes, and Kafka with 8+ years experience."

        score, reasons, _ = MatchScorer.compute_match_score(empty_profile, title, jd)

        # 1. Score must be capped as provisional (not 0.99)
        assert score <= 0.35, f"Expected provisional score <= 0.35, got {score}"

        # 2. Must not contain 'fits Intern requirements'
        for r in reasons:
            assert "fits Intern requirements" not in r
            assert "0.0 yrs" not in r

        # 3. Must contain calibration notice
        assert any("provisional" in r.lower() or "calibrate" in r.lower() for r in reasons)

    def test_empty_profile_semantic_scorer_does_not_boost(self):
        """compute_match_score_semantic must not falsely boost empty profile to 99%."""
        empty_profile = CandidateProfile(
            full_name="New User",
            email="newuser@example.com",
            phone="+1-555-0100",
            location="Remote",
            skills=[],
            preferences=RecruiterPreferences(years_of_experience=0.0)
        )

        title = "Senior Full Stack Engineer"
        jd = "Architecting internal platforms with React and Python."

        score_sem, reasons, _ = MatchScorer.compute_match_score_semantic(empty_profile, title, jd)
        assert score_sem <= 0.35
        for r in reasons:
            assert "fits Intern requirements" not in r

    def test_calibrated_profile_receives_accurate_seniority_reason(self):
        """Calibrated profile with matching YOE receives proper non-intern seniority reason."""
        calibrated_profile = CandidateProfile(
            full_name="Senior Dev",
            email="senior@example.com",
            phone="+1-555-0100",
            location="Remote",
            skills=["Python", "Go", "Docker", "Kubernetes"],
            preferences=RecruiterPreferences(
                years_of_experience=6.0,
                remote_preference="Remote"
            )
        )

        title = "Senior Infrastructure Engineer"
        jd = "We need Python and Docker expertise for internal cloud infrastructure."

        score, reasons, _ = MatchScorer.compute_match_score(calibrated_profile, title, jd)
        assert score >= 0.50
        assert any("fits Senior requirements" in r for r in reasons)
        assert not any("Intern" in r for r in reasons)
