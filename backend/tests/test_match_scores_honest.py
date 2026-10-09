"""
Match scores must be earned. Discovery used to give 99% to postings that shared a
single skill keyword, to non-engineering roles ("ai" matched inside "maintain"),
and to every location whenever the default preference mentioned "remote".
"""

from app.core.match_scorer import MatchScorer
from app.core.models import CandidateProfile, RecruiterPreferences, WorkExperience

BACKEND_JD = (
    "We are hiring a backend engineer to build payment APIs in Python and Go. "
    "You will work with FastAPI, PostgreSQL, Redis, Kafka, Docker and Kubernetes on AWS."
)


def _profile(location="Pune, India", remote="Remote / Hybrid / On-site", relocate=True, title="Software Engineer"):
    return CandidateProfile(
        full_name="Asha Rao",
        email="asha@example.test",
        phone="0",
        location=location,
        summary="Backend engineer, 5 years of Python and Go.",
        skills=["Python", "Go", "FastAPI", "PostgreSQL", "Redis", "Docker", "Kubernetes", "AWS"],
        experience=[WorkExperience(company="Example Payments", title=title, start_date="2021", end_date="Present")],
        preferences=RecruiterPreferences(years_of_experience=5.0, remote_preference=remote, willing_to_relocate=relocate),
    )


def score(profile, title, jd=BACKEND_JD, location="Pune, India"):
    return MatchScorer.compute_match_score(profile, title, jd, location)[0]


def test_strong_local_backend_role_scores_high():
    assert score(_profile(), "Senior Backend Engineer", location="Pune, India") >= 0.85


def test_one_shared_keyword_is_not_a_strong_match():
    jd = "Join our observability team. Experience with Go is a plus."
    assert score(_profile(), "Software Engineer, Observability", jd=jd, location="Pune, India") < 0.6


def test_non_engineering_role_scores_low():
    jd = "Train our models in Japanese. Python familiarity helps. We maintain high standards."
    assert score(_profile(), "[Contract] Language Training Specialist - Japanese", jd=jd, location="Tokyo, Japan") <= 0.2


def test_support_and_manager_titles_rank_below_the_real_role():
    real = score(_profile(), "Backend Engineer")
    assert score(_profile(), "Database Support Engineer") < real - 0.15
    assert score(_profile(), "Manager, Software Engineering - Platform") < real - 0.15
    # ...unless the candidate already manages engineers.
    manager = _profile(title="Engineering Manager")
    assert score(manager, "Engineering Manager, Platform") > score(_profile(), "Engineering Manager, Platform")


def test_go_as_an_english_word_is_not_a_skill_match():
    jd = "We go above and beyond for customers. Python and FastAPI on AWS."
    _, _, missing = MatchScorer.compute_match_score(_profile(location="Remote"), "Backend Engineer", jd, "Remote")
    skills = MatchScorer._job_skills("Backend Engineer", jd)
    assert "Go" not in skills and "Golang" not in skills
    assert "Go" not in missing


def test_spelling_variants_count_once():
    jd = "Golang and Go services, Postgres (PostgreSQL), React.js / React."
    keys = [MatchScorer._canonical_skill(s) for s in MatchScorer._job_skills("Engineer", jd)]
    assert len(keys) == len(set(keys))


def test_location_is_not_free_points():
    p = _profile()
    local = score(p, "Backend Engineer", location="Pune, India")
    same_country = score(p, "Backend Engineer", location="Bangalore, India")
    abroad = score(p, "Backend Engineer", location="San Francisco, CA")
    remote_india = score(p, "Backend Engineer", location="Remote (India)")
    remote_us_only = score(p, "Backend Engineer", location="Remote - United States")
    assert local >= same_country > abroad
    assert remote_india > remote_us_only
    # "us" must not match inside "Australia".
    assert MatchScorer._regions("sydney, australia") == set()


def test_remote_only_candidate_is_not_matched_to_far_offices():
    p = _profile(remote="Remote", relocate=False)
    assert score(p, "Backend Engineer", location="Remote") - score(p, "Backend Engineer", location="Berlin, Germany") >= 0.12
