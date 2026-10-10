"""Nothing invented: a resume without a phone or salary leaves those blank, and forms say so."""

from app.core.models import CandidateProfile
from app.core.resume_parser import ResumeParser
from app.core.vector_vault import vault


def test_missing_phone_and_salary_stay_blank():
    profile = ResumeParser.parse_to_profile("Nia Rao\nnia@example.test\nBackend engineer. Skills: Python, Go.")
    assert profile.phone == ""
    assert profile.preferences.expected_ctc == ""
    assert profile.preferences.current_ctc == ""


def test_blank_salary_is_never_answered_with_a_made_up_number():
    profile = CandidateProfile(full_name="N", email="n@test.com", phone="", location="Pune")
    profile.preferences.expected_ctc = ""
    profile.preferences.current_ctc = "0 LPA"
    answer = vault._resolve_template("{expected_ctc} / {current_ctc}", profile, "Acme", "Engineer", "Tech")
    assert answer == "Open to discussion / Prefer not to say"
