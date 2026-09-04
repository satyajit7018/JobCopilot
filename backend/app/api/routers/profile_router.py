"""
JobCopilot - Candidate Profile & Questionnaire Router
Handles resume uploading/parsing, candidate profile management, and recruiter questionnaire configuration.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel

from app.core.config import RESUMES_DIR
from app.core.models import User, CandidateProfile
from app.core.database import db
from app.core.resume_parser import ResumeParser
from app.core.questionnaire import QuestionnaireEngine
from app.core.vector_vault import vault
from app.api.auth import get_current_user

router = APIRouter(tags=["profile"])


class QuestionnaireSubmitRequest(BaseModel):
    profile_id: Optional[str] = None
    answers: Dict[str, Any]


@router.post("/upload-resume")
async def upload_resume(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
    profile_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Uploads and parses a resume (PDF, DOCX, or text) and auto-prefills questionnaire."""
    user_id = current_user.user_id
    target_profile_id = profile_id or user_id

    if file:
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Resume file exceeds maximum allowed size (10MB).")
        safe_filename = Path(file.filename or "resume.pdf").name
        file_path = RESUMES_DIR / f"{user_id}_{safe_filename}"
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        profile = await ResumeParser.parse_to_profile_async(str(file_path), profile_id=target_profile_id, user_id=user_id)
    elif raw_text:
        profile = await ResumeParser.parse_to_profile_async(raw_text, profile_id=target_profile_id, user_id=user_id)
    else:
        raise HTTPException(status_code=400, detail="No resume file or raw text provided.")

    profile.id = target_profile_id
    profile.user_id = user_id
    db.save_profile(profile, user_id=user_id)
    vault.seed_from_profile(profile)

    prefilled_data = QuestionnaireEngine.prefill_from_profile(profile)
    questions_schema = QuestionnaireEngine.get_questions_schema()

    return {
        "status": "success",
        "profile": profile.dict(),
        "prefilled_questionnaire": prefilled_data,
        "questions_schema": questions_schema
    }


@router.get("/profile")
async def get_profile(
    profile_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Retrieves current candidate profile for authenticated tenant."""
    profile = db.get_profile(user_id=current_user.user_id, profile_id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found. Please upload a resume.")
    return {"status": "success", "profile": profile.dict()}


@router.get("/questionnaire")
async def get_questionnaire(
    profile_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Retrieves the recruiter questions schema and prefilled answers."""
    profile = db.get_profile(user_id=current_user.user_id, profile_id=profile_id)
    schema = QuestionnaireEngine.get_questions_schema()
    prefilled = QuestionnaireEngine.prefill_from_profile(profile) if profile else {}
    return {
        "questions_schema": schema,
        "prefilled": prefilled
    }


@router.post("/questionnaire")
async def submit_questionnaire(
    payload: QuestionnaireSubmitRequest,
    current_user: User = Depends(get_current_user)
):
    """Applies user-confirmed answers to profile and Knowledge Vault."""
    user_id = current_user.user_id
    target_id = payload.profile_id or user_id
    profile = db.get_profile(user_id=user_id, profile_id=target_id)
    if not profile:
        profile = CandidateProfile(
            id=target_id,
            user_id=user_id,
            full_name=payload.answers.get("full_name", current_user.full_name or "Candidate"),
            email=payload.answers.get("email", current_user.email),
            phone=payload.answers.get("phone", "+1-000-000-0000"),
            location=payload.answers.get("location", "Remote")
        )

    updated_profile = QuestionnaireEngine.apply_answers_to_profile(profile, payload.answers)
    updated_profile.id = target_id
    updated_profile.user_id = user_id
    db.save_profile(updated_profile, user_id=user_id)
    vault.seed_from_profile(updated_profile)

    return {
        "status": "success",
        "message": "Recruiter preferences saved and Knowledge Vault seeded successfully!",
        "profile": updated_profile.dict()
    }
