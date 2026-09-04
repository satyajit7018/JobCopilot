"""
JobCopilot - Mock Interview Studio & Calendar Availability Router
Handles company technical dossiers, STAR mock interview question generation,
response evaluation, reverse interview strategies, interviewer recon, and calendar scheduling.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.models import User
from app.core.database import db
from app.api.auth import get_current_user
from app.api.ws_gateway import ws_manager

router = APIRouter(tags=["interview"])


class InterviewEvalRequest(BaseModel):
    question: str
    answer: Optional[str] = None
    candidate_answer: Optional[str] = None
    key_concepts: Optional[List[str]] = None


class InterviewInvitationTriggerRequest(BaseModel):
    company: str
    role_title: str
    job_id: Optional[str] = None
    meeting_url: Optional[str] = None


class InterviewerReconRequest(BaseModel):
    interviewer_name: str
    interviewer_role: str = "Engineering Manager"
    background_text: str = ""


@router.get("/interview/dossier")
async def get_company_dossier(
    company: str,
    role: str = "Senior Software Engineer",
    current_user: User = Depends(get_current_user)
):
    """Generates technical architecture dossier and interview rounds for target company."""
    from app.core.interview_studio import InterviewStudioEngine
    return {
        "status": "success",
        "dossier": InterviewStudioEngine.generate_company_dossier(company, role)
    }


@router.get("/interview/questions")
async def get_mock_questions(
    role: str = "Senior Software Engineer",
    profile_id: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Generates role-specific mock technical, system design, and STAR leadership questions."""
    from app.core.interview_studio import InterviewStudioEngine
    profile = db.get_profile(user_id=current_user.user_id, profile_id=profile_id)
    skills = profile.skills if profile else ["Python", "Distributed Systems"]
    return {
        "status": "success",
        "questions": InterviewStudioEngine.generate_mock_questions(role, skills=skills, category=category)
    }


@router.post("/interview/evaluate")
async def evaluate_interview_answer(
    payload: InterviewEvalRequest,
    current_user: User = Depends(get_current_user)
):
    """Evaluates candidate response with multi-dimensional STAR scoring."""
    from app.core.interview_studio import InterviewStudioEngine
    ans = payload.candidate_answer or payload.answer or ""
    return {
        "status": "success",
        "evaluation": InterviewStudioEngine.evaluate_interview_response(
            question=payload.question,
            candidate_answer=ans,
            key_concepts=payload.key_concepts
        )
    }


@router.post("/interview/notify-invitation")
async def trigger_interview_invitation_notification(
    payload: InterviewInvitationTriggerRequest,
    current_user: User = Depends(get_current_user)
):
    """Triggers an interview invitation alert and provides role-customized mock interview questions."""
    from app.core.interview_studio import InterviewStudioEngine

    dossier = InterviewStudioEngine.generate_company_dossier(payload.company, payload.role_title)
    questions = InterviewStudioEngine.generate_mock_questions(role_title=payload.role_title, category=None)
    track = InterviewStudioEngine.infer_role_track(payload.role_title)

    await ws_manager.broadcast({
        "type": "INTERVIEW_INVITATION_RECEIVED",
        "company": payload.company,
        "role_title": payload.role_title,
        "job_id": payload.job_id,
        "role_track": track,
        "meeting_url": payload.meeting_url,
        "dossier": dossier,
        "suggested_questions": questions
    })

    return {
        "status": "success",
        "message": f"Interview invitation alert generated for {payload.company} - {payload.role_title}",
        "role_track": track,
        "dossier": dossier,
        "questions_count": len(questions)
    }


@router.get("/interview/reverse-questions")
async def get_reverse_interview_questions(
    role: str = "Senior Software Engineer",
    company: str = "Target Company",
    current_user: User = Depends(get_current_user)
):
    """Generates strategic questions to ask the hiring manager."""
    from app.core.interview_studio import InterviewStudioEngine
    return {
        "status": "success",
        "company": company,
        "role": role,
        "questions": InterviewStudioEngine.generate_reverse_interview_questions(role_title=role, company_name=company)
    }


@router.post("/interview/interviewer-recon")
async def analyze_interviewer_recon(
    payload: InterviewerReconRequest,
    current_user: User = Depends(get_current_user)
):
    """Infers interviewer persona, technical biases, and strategic preparation advice."""
    from app.core.interview_studio import InterviewStudioEngine
    return {
        "status": "success",
        "recon": InterviewStudioEngine.analyze_interviewer_profile(
            interviewer_name=payload.interviewer_name,
            interviewer_role=payload.interviewer_role,
            background_text=payload.background_text
        )
    }


@router.get("/interview/engineering-intel")
async def get_company_engineering_intel_endpoint(
    company: str,
    current_user: User = Depends(get_current_user)
):
    """Fetches company public engineering blog initiatives."""
    from app.core.interview_studio import InterviewStudioEngine
    return {
        "status": "success",
        "intel": InterviewStudioEngine.get_company_engineering_intel(company_name=company)
    }


@router.get("/calendar/availability")
async def get_calendar_availability(
    timezone: str = "IST",
    days: int = 4,
    current_user: User = Depends(get_current_user)
):
    """Calculates non-conflicting interview scheduling windows."""
    from app.core.calendar_sync import CalendarAvailabilityEngine
    slots = CalendarAvailabilityEngine.get_open_slots(timezone_str=timezone, days_ahead=days)
    email_text = CalendarAvailabilityEngine.format_availability_email_text(slots)
    return {
        "status": "success",
        "timezone": timezone,
        "slots": slots,
        "email_snippet": email_text
    }
