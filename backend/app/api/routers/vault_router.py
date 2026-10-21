"""
JobCopilot - Knowledge Vault Router
The user's saved answers to application questions: the "Application answers" page, plus
manual learning.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.core.database import db
from app.core.models import SlotType, User, VaultEntry
from app.core.vector_vault import (
    COMPANY_SPECIFIC_KEYS,
    PERSONAL_KEYS,
    PREFER_NOT_TO_SAY,
    SEEDED_REASON_QUESTION,
    normalize_question,
    vault,
)

router = APIRouter(tags=["vault"])


class VaultLearnRequest(BaseModel):
    question: str
    answer: str
    slot_type: Optional[str] = None
    slot_key: Optional[str] = None


@router.get("/vault")
async def get_vault_entries(current_user: User = Depends(get_current_user)):
    """Returns all indexed Q&A slots for the authenticated tenant."""
    entries = db.get_vault_entries(user_id=current_user.user_id)
    return {
        "count": len(entries),
        "entries": [e.dict() for e in entries]
    }


@router.post("/vault/learn")
async def learn_vault_entry(
    payload: VaultLearnRequest,
    current_user: User = Depends(get_current_user)
):
    """Manually teaches or updates a Q&A slot."""
    entry = vault.learn_answer(
        question=payload.question,
        answer_template=payload.answer,
        slot_type=payload.slot_type,
        slot_key=payload.slot_key,
        user_id=current_user.user_id,
    )
    return {"status": "success", "entry": entry.dict()}


# --- Application answers page ---------------------------------------------------------------

# Facts that live in Profile. The answers page shows them and links there; it never keeps a copy.
PROFILE_FACTS = (
    ("expected_ctc", "Expected salary"),
    ("current_ctc", "Current salary"),
    ("notice_period", "Notice period"),
    ("work_authorization", "Work authorisation"),
    ("sponsorship_answer", "Needs visa sponsorship"),
    ("relocation_answer", "Willing to relocate"),
    ("remote_preference", "Work mode"),
    ("years_of_experience", "Years of experience"),
)

# Questions most forms ask that the profile doesn't cover.
COMMON_QUESTIONS: List[Dict[str, Any]] = [
    {"key": "why_hire_me", "question": "Why should we hire you?", "kind": "text"},
    {"key": "technical_achievement", "question": "Tell us about a project you built that you're proud of.", "kind": "text"},
    {"key": "gender", "question": "Gender", "kind": "personal",
     "options": [PREFER_NOT_TO_SAY, "Woman", "Man", "Non-binary"]},
    {"key": "race_ethnicity", "question": "Race or ethnicity", "kind": "personal", "options": [PREFER_NOT_TO_SAY]},
    {"key": "veteran_status", "question": "Veteran status", "kind": "personal",
     "options": [PREFER_NOT_TO_SAY, "I am not a veteran", "I am a veteran"]},
    {"key": "disability_status", "question": "Disability", "kind": "personal",
     "options": [PREFER_NOT_TO_SAY, "No, I don't have a disability", "Yes, I have a disability"]},
]
COMMON_BY_KEY = {q["key"]: q for q in COMMON_QUESTIONS}


def _is_profile_copy(entry: VaultEntry) -> bool:
    """The "why I'm looking" answer copied from Profile, where the user edits it."""
    return entry.slot_key == "why_looking_for_role" and entry.question_pattern == SEEDED_REASON_QUESTION


def _saved_answer(entry: VaultEntry, jobs: Dict[str, Any]) -> Dict[str, Any]:
    job = jobs.get(entry.job_id or "")
    return {
        "id": entry.qa_id,
        "question": entry.question_pattern,
        "answer": entry.answer_template,
        "for_job": {"job_id": job.job_id, "company": job.company, "title": job.title} if job else None,
        "wordings": entry.aliases,
        "confirmed_at": entry.confirmed_at,
        "last_used_at": entry.last_used_at,
    }


class SaveAnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=5000)
    # One of the common questions, so different wordings of it land on the same answer.
    key: Optional[str] = None
    job_id: Optional[str] = None


class EditAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)


class AddWordingRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@router.get("/answers")
async def get_application_answers(current_user: User = Depends(get_current_user)):
    """Everything the app can put on an application form, grouped for the answers page."""
    user_id = current_user.user_id
    profile = db.get_profile(user_id=user_id)
    known = vault._profile_values(profile) if profile else {}
    profile_facts = [{"key": key, "label": label, "value": known.get(key)} for key, label in PROFILE_FACTS]
    reason = (profile.preferences.why_looking_for_role or "").strip() if profile else ""
    profile_facts.append({"key": "why_looking_for_role", "label": "Why you're looking", "value": reason or None})

    entries = [e for e in vault._own_entries(user_id) if not _is_profile_copy(e)]
    # A personal topic has one answer. A written one is the common question's only in its own wording.
    by_key = {
        e.slot_key: e for e in entries
        if e.slot_key in COMMON_BY_KEY and (e.slot_key in PERSONAL_KEYS
                                            or normalize_question(e.question_pattern) == normalize_question(COMMON_BY_KEY[e.slot_key]["question"]))
    }
    common = []
    for q in COMMON_QUESTIONS:
        entry = by_key.get(q["key"])
        personal = q["kind"] == "personal"
        common.append({
            **q,
            "id": entry.qa_id if entry else None,
            "answer": entry.answer_template if entry else (PREFER_NOT_TO_SAY if personal else None),
            "optional": personal,
            "confirmed_at": entry.confirmed_at if entry else None,
        })

    others = [e for e in entries if e.qa_id not in {c["id"] for c in common}]
    jobs = {}
    for job_id in {e.job_id for e in others if e.job_id}:
        job = db.get_job_by_id(job_id, user_id=user_id)
        if job:
            jobs[job_id] = job
    others.sort(key=lambda e: e.confirmed_at or e.last_used_at or e.created_at, reverse=True)
    return {
        "profile": profile_facts,
        "common": common,
        "saved": [_saved_answer(e, jobs) for e in others],
    }


@router.put("/answers")
async def save_application_answer(payload: SaveAnswerRequest, current_user: User = Depends(get_current_user)):
    """Saves the user's answer to a question, replacing their earlier answer to it."""
    question, answer = payload.question.strip(), payload.answer.strip()
    if not question or not answer:
        raise HTTPException(status_code=422, detail="Enter a question and an answer.")
    slot_type = slot_key = None
    if payload.key:
        if payload.key not in COMMON_BY_KEY:
            raise HTTPException(status_code=422, detail="Unknown question.")
        slot_key = payload.key
        slot_type = SlotType.SELECTION if payload.key in PERSONAL_KEYS else SlotType.PARAMETRIC_ESSAY
    else:
        _, detected = vault.matcher.detect_slot_type(question)
        if detected in COMPANY_SPECIFIC_KEYS and not payload.job_id:
            raise HTTPException(status_code=422, detail="This answer is about one company, so it's saved from that job's page.")
    if payload.job_id and not db.get_job_by_id(payload.job_id, user_id=current_user.user_id):
        raise HTTPException(status_code=404, detail="Job not found.")
    entry = vault.learn_answer(question, answer, slot_type=slot_type, slot_key=slot_key,
                               user_id=current_user.user_id, job_id=payload.job_id)
    return {"id": entry.qa_id, "confirmed_at": entry.confirmed_at}


@router.patch("/answers/{answer_id}")
async def edit_application_answer(answer_id: str, payload: EditAnswerRequest, current_user: User = Depends(get_current_user)):
    answer = payload.answer.strip()
    if not answer:
        raise HTTPException(status_code=422, detail="Enter an answer, or delete it.")
    entry = vault.update_answer(current_user.user_id, answer_id, answer)
    if not entry:
        raise HTTPException(status_code=404, detail="Answer not found.")
    return {"id": entry.qa_id, "confirmed_at": entry.confirmed_at}


@router.post("/answers/{answer_id}/wordings")
async def add_answer_wording(answer_id: str, payload: AddWordingRequest, current_user: User = Depends(get_current_user)):
    """Confirms another wording means the same question, so it fills automatically from now on."""
    entry = vault.add_wording(current_user.user_id, answer_id, payload.question)
    if not entry:
        raise HTTPException(status_code=404, detail="Answer not found.")
    return {"id": entry.qa_id, "wordings": entry.aliases}


@router.delete("/answers/{answer_id}")
async def delete_application_answer(answer_id: str, current_user: User = Depends(get_current_user)):
    if not vault.delete_answer(current_user.user_id, answer_id):
        raise HTTPException(status_code=404, detail="Answer not found.")
    return {"deleted": True}
