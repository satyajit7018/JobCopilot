"""
Application answers (prepared applications, Phase 2).

- The same wording, or one the user confirmed, fills automatically.
- A similar wording only gets a suggestion, never typed into a form.
- "Why this company?" answers are kept for that one job.
- Personal questions are optional and default to "Prefer not to say".
- Saved answers are encrypted at rest and editable, deletable and private through the API.
"""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.api.auth import create_jwt_token
from app.bot.form import answer_for
from app.core.database import db
from app.core.models import CandidateProfile, JobListing, RecruiterPreferences, User, UserRole
from app.core.vector_vault import PREFER_NOT_TO_SAY, normalize_question, vault
from app.main import app


def _uid() -> str:
    return f"usr_{uuid.uuid4().hex[:10]}"


def _profile(uid: str, **prefs) -> CandidateProfile:
    profile = CandidateProfile(
        id=uid, user_id=uid, full_name="Asha Rao", email=f"{uid}@example.test", phone="+91 9000000001",
        location="Pune", skills=["Python"], preferences=RecruiterPreferences(**prefs),
    )
    db.save_profile(profile, user_id=uid)
    return profile


def _job(uid: str, company: str = "Acme") -> JobListing:
    job = JobListing(job_id=f"job_{uuid.uuid4().hex[:8]}", user_id=uid, fingerprint=uuid.uuid4().hex, platform="Greenhouse",
                     company=company, title="SDE", url=f"https://{company.lower()}.test/job")
    db.save_job(job, user_id=uid)
    return job


def _client_for():
    uid = _uid()
    db.create_user(User(user_id=uid, email=f"{uid}@example.test", password_hash="x", role=UserRole.FREE))
    token = create_jwt_token({"sub": uid, "email": f"{uid}@example.test", "role": "FREE", "type": "access"}, timedelta(minutes=15))
    return uid, TestClient(app), {"Authorization": f"Bearer {token}"}


# --- Matching ---------------------------------------------------------------------------------


def test_same_wording_fills_and_similar_wording_is_only_a_suggestion():
    uid = _uid()
    profile = _profile(uid)
    vault.learn_answer("Do you have experience leading a team?", "Yes, a team of four for two years.", user_id=uid)

    # Case, punctuation and a "*" or "(required)" don't make it a different question.
    assert answer_for("Do you have experience leading a team? *", profile) == "Yes, a team of four for two years."
    assert answer_for("do you have experience leading a team (required)", profile) == "Yes, a team of four for two years."

    similar = "Have you led a team before?"
    match = vault.find_answer(similar, profile=profile)
    assert match.answer is None and match.source == "none"
    assert match.suggestion == "Yes, a team of four for two years."
    assert answer_for(similar, profile) is None


def test_a_confirmed_wording_fills_automatically():
    uid = _uid()
    profile = _profile(uid)
    entry = vault.learn_answer("Do you have experience leading a team?", "Yes, a team of four.", user_id=uid)
    assert answer_for("Have you led a team before?", profile) is None

    vault.add_wording(uid, entry.qa_id, "Have you led a team before?")
    assert answer_for("Have you led a team before?", profile) == "Yes, a team of four."
    # Confirming the same wording twice keeps one copy.
    again = vault.add_wording(uid, entry.qa_id, "have you led a team before")
    assert again.aliases == ["Have you led a team before?"]


def test_different_questions_keep_their_own_answers():
    # Two unrelated questions used to share one "general question" slot, so the second overwrote the first.
    uid = _uid()
    profile = _profile(uid)
    vault.learn_answer("Which timezone are you in?", "IST", user_id=uid)
    vault.learn_answer("How did you hear about us?", "A friend", user_id=uid)
    assert answer_for("Which timezone are you in?", profile) == "IST"
    assert answer_for("How did you hear about us?", profile) == "A friend"


def test_why_this_company_is_saved_for_that_job_only():
    uid = _uid()
    profile = _profile(uid)
    acme, globex = _job(uid, "Acme"), _job(uid, "Globex")
    question = "Why do you want to work at our company?"
    entry = vault.learn_answer(question, "I use Acme every day.", user_id=uid, job_id=acme.job_id)
    assert entry.scope == "job" and entry.job_id == acme.job_id

    assert answer_for(question, profile, company="Acme", job_id=acme.job_id) == "I use Acme every day."
    assert answer_for(question, profile, company="Globex", job_id=globex.job_id) is None
    assert vault.find_answer(question, profile=profile, job_id=globex.job_id).suggestion is None
    assert answer_for(question, profile) is None


def test_personal_questions_are_optional_and_default_to_prefer_not_to_say():
    uid = _uid()
    profile = _profile(uid)
    match = vault.find_answer("What is your gender?", profile=profile)
    assert (match.answer, match.source, match.optional) == (PREFER_NOT_TO_SAY, "default", True)
    # The default is for the user to see; the filler never types it on their behalf.
    assert answer_for("What is your gender?", profile) is None

    vault.learn_answer("Gender", "Woman", user_id=uid)
    assert answer_for("Please select your gender", profile) == "Woman"
    # Each personal topic keeps its own answer.
    assert vault.find_answer("Do you have a disability?", profile=profile).answer == PREFER_NOT_TO_SAY
    # Words that merely contain a topic don't count ("embrace" is not "race").
    assert vault.find_answer("How do you embrace change?", profile=profile).optional is False


def test_salary_never_comes_from_a_lookalike_answer():
    uid = _uid()
    profile = _profile(uid)
    vault.learn_answer("What salary range are you targeting this year, roughly?", "Around 30 LPA", user_id=uid)
    # Expected salary is a profile fact the user hasn't saved: not answered, not even suggested.
    match = vault.find_answer("What is your expected salary?", profile=profile)
    assert match.answer is None and match.suggestion is None


def test_answers_are_encrypted_at_rest():
    uid = _uid()
    vault.learn_answer("What's your favourite programming language?", "Rust, for its compiler.", user_id=uid)
    with db.get_connection() as conn:
        raw = conn.execute("SELECT answer_template FROM vault WHERE user_id = ?", (uid,)).fetchone()[0]
        history = [r[0] for r in conn.execute(
            "SELECT answer_template FROM vault_history WHERE qa_id IN (SELECT qa_id FROM vault WHERE user_id = ?)", (uid,))]
    assert "Rust" not in raw
    assert all("Rust" not in h for h in history)
    assert db.get_vault_entries(uid)[0].answer_template == "Rust, for its compiler."


def test_normalize_question():
    assert normalize_question("  Why  US?* (Required) ") == "why us"
    assert normalize_question("Experience with C++ / C#?") == "experience with c++ c#"


# --- Through the API -------------------------------------------------------------------------


def test_answers_page_lists_profile_facts_common_questions_and_saved_answers():
    uid, c, headers = _client_for()
    _profile(uid, confirmed=["expected_ctc"], expected_ctc="28 LPA", why_looking_for_role="Want to build products.")
    vault.seed_from_profile(db.get_profile(user_id=uid))
    job = _job(uid)
    vault.learn_answer("Why do you want to work at our company?", "Their mission.", user_id=uid, job_id=job.job_id)
    vault.learn_answer("Which timezone are you in?", "IST", user_id=uid)

    r = c.get("/api/answers", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    facts = {f["key"]: f["value"] for f in body["profile"]}
    assert facts["expected_ctc"] == "28 LPA"
    assert facts["notice_period"] is None  # never saved, so not shown as an answer
    assert facts["why_looking_for_role"] == "Want to build products."

    common = {q["key"]: q for q in body["common"]}
    assert common["gender"]["answer"] == PREFER_NOT_TO_SAY and common["gender"]["optional"] is True
    assert common["gender"]["id"] is None
    assert common["why_hire_me"]["answer"] is None

    saved = {s["question"]: s for s in body["saved"]}
    # The profile's own "why I'm looking" is edited in Profile, so it isn't listed twice.
    assert "Why are you looking for a new role?" not in saved
    assert saved["Which timezone are you in?"]["answer"] == "IST"
    assert saved["Why do you want to work at our company?"]["for_job"] == {"job_id": job.job_id, "company": "Acme", "title": "SDE"}


def test_save_edit_add_wording_and_delete_through_the_api():
    uid, c, headers = _client_for()
    _profile(uid)

    r = c.put("/api/answers", headers=headers, json={"key": "gender", "question": "Gender", "answer": "Woman"})
    assert r.status_code == 200, r.text
    common = {q["key"]: q for q in c.get("/api/answers", headers=headers).json()["common"]}
    assert common["gender"]["answer"] == "Woman" and common["gender"]["confirmed_at"]

    r = c.put("/api/answers", headers=headers, json={"question": "Which timezone are you in?", "answer": "IST"})
    answer_id = r.json()["id"]
    assert c.patch(f"/api/answers/{answer_id}", headers=headers, json={"answer": "IST (UTC+5:30)"}).status_code == 200
    r = c.post(f"/api/answers/{answer_id}/wordings", headers=headers, json={"question": "What time zone do you work in?"})
    assert r.json()["wordings"] == ["What time zone do you work in?"]
    assert answer_for("What time zone do you work in?", db.get_profile(user_id=uid)) == "IST (UTC+5:30)"

    assert c.delete(f"/api/answers/{answer_id}", headers=headers).status_code == 200
    assert c.delete(f"/api/answers/{answer_id}", headers=headers).status_code == 404
    assert answer_for("Which timezone are you in?", db.get_profile(user_id=uid)) is None


def test_answers_api_rejects_blank_unknown_and_company_answers_without_a_job():
    uid, c, headers = _client_for()
    _profile(uid)
    assert c.put("/api/answers", headers=headers, json={"question": "Q?", "answer": "   "}).status_code == 422
    assert c.put("/api/answers", headers=headers, json={"key": "salary", "question": "Q?", "answer": "A"}).status_code == 422
    r = c.put("/api/answers", headers=headers, json={"question": "Why do you want to join our team?", "answer": "A"})
    assert r.status_code == 422
    r = c.put("/api/answers", headers=headers, json={"question": "Why do you want to join our team?", "answer": "A", "job_id": "job_nope"})
    assert r.status_code == 404


def test_one_users_answers_are_invisible_to_another():
    owner, c, owner_headers = _client_for()
    _profile(owner)
    answer_id = c.put("/api/answers", headers=owner_headers, json={"question": "Which timezone are you in?", "answer": "IST"}).json()["id"]

    other, _, other_headers = _client_for()
    _profile(other)
    assert all(s["id"] != answer_id for s in c.get("/api/answers", headers=other_headers).json()["saved"])
    assert c.patch(f"/api/answers/{answer_id}", headers=other_headers, json={"answer": "x"}).status_code == 404
    assert c.post(f"/api/answers/{answer_id}/wordings", headers=other_headers, json={"question": "x"}).status_code == 404
    assert c.delete(f"/api/answers/{answer_id}", headers=other_headers).status_code == 404
    assert db.get_vault_entries(owner)[0].answer_template == "IST"


def test_held_company_question_is_saved_for_its_job():
    from app.core.models import HITLEvent

    uid, c, headers = _client_for()
    _profile(uid)
    job = _job(uid)
    event = HITLEvent(event_id=f"evt_{uuid.uuid4().hex[:8]}", user_id=uid, job_id=job.job_id, company="Acme",
                      role_title="SDE", question_text="Why do you want to work at Acme?", input_type="text")
    db.save_hitl_event(event, user_id=uid)
    r = c.post("/api/hitl/resolve", headers=headers, json={"event_id": event.event_id, "user_answer": "Their mission.", "save_to_vault": True})
    assert r.status_code == 200, r.text
    [entry] = db.get_vault_entries(uid)
    assert (entry.scope, entry.job_id) == ("job", job.job_id)
