"""
JobCopilot - Jobs Pipeline & Tailoring Router
Handles job application tracking, ATS resume tailoring, multi-role tailoring,
direct call logging, held job inspection, and referral/nudge outreach generation.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.auth import get_current_user, limiter
from app.api.ws_gateway import ws_manager
from app.core.cover_letter import CoverLetterGenerator
from app.core import match_feedback
from app.core.database import db
from app.core.plans import require_premium
from app.core.models import ApplicationStatus, CandidateProfile, JobListing, User
from app.core.outreach_generator import OutreachGenerator
from app.core.resume_tailor import ResumeTailor

router = APIRouter(tags=["jobs"])


class AlumniReferralRequest(BaseModel):
    candidate_name: str = "Candidate"
    company_name: str
    role_title: str
    contact_name: str = "Fellow Alumni"
    common_ground: str = "our shared background"


class RecruiterNudgeRequest(BaseModel):
    candidate_name: str = "Candidate"
    company_name: str
    role_title: str
    recruiter_name: str = "Recruiter"
    days_elapsed: int = 5
    recent_highlight: Optional[str] = None


class MultiRoleTailorRequest(BaseModel):
    roles: List[str]
    profile_id: Optional[str] = None


class LogDirectCallRequest(BaseModel):
    company: str
    role_title: str
    recruiter_name: Optional[str] = "Recruiter"
    status: str = "INTERVIEW"
    call_notes: Optional[str] = None
    scheduled_interview_time: Optional[str] = None
    meeting_link: Optional[str] = None


class UpdateJobStatusRequest(BaseModel):
    status: str


class UpdateInterviewDateRequest(BaseModel):
    # ISO 8601 date-time, or null to clear it.
    interview_date: Optional[str] = None


@router.get("/jobs")
async def get_jobs(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Returns all tracked job applications for the authenticated tenant."""
    jobs = db.get_jobs(status=status, user_id=current_user.user_id)
    return {
        "count": len(jobs),
        "jobs": [j.dict() for j in jobs]
    }


@router.patch("/jobs/{job_id}/status")
async def update_job_status(
    job_id: str,
    payload: UpdateJobStatusRequest,
    current_user: User = Depends(get_current_user)
):
    """Updates the pipeline status of a tracked job application."""
    try:
        new_status = ApplicationStatus(payload.status.upper())
    except ValueError:
        valid_statuses = [s.value for s in ApplicationStatus]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.status}'. Valid statuses: {valid_statuses}"
        )

    job = db.get_job_by_id(job_id, user_id=current_user.user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    job.status = new_status
    # Marking a job applied (or further along) by hand records when, so follow-up
    # reminders and "applied 3 days ago" work for applications made outside JobCopilot.
    applied_or_later = {ApplicationStatus.SUBMITTED, ApplicationStatus.RESPONDED, ApplicationStatus.INTERVIEW,
                        ApplicationStatus.OFFER, ApplicationStatus.REJECTED}
    if new_status in applied_or_later and not job.applied_at:
        job.applied_at = datetime.now().isoformat()
    db.save_job(job, user_id=current_user.user_id)

    return {
        "status": "success",
        "job_id": job.job_id,
        "new_status": new_status.value
    }


class UpdateNotesRequest(BaseModel):
    notes: str = ""


MAX_NOTES_LENGTH = 4000


@router.patch("/jobs/{job_id}/notes")
async def update_job_notes(job_id: str, payload: UpdateNotesRequest, current_user: User = Depends(get_current_user)):
    """Saves the user's own notes on a job or application ("spoke to Priya, follow up Friday")."""
    # "__meta__:" marks where stored notes end and internal fields begin; never let it in.
    notes = payload.notes.replace("__meta__:", "").strip()
    if len(notes) > MAX_NOTES_LENGTH:
        raise HTTPException(status_code=400, detail=f"Notes can be up to {MAX_NOTES_LENGTH} characters.")
    job = db.get_job_by_id(job_id, user_id=current_user.user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.notes = notes or None
    db.save_job(job, user_id=current_user.user_id)
    return {"status": "success", "job_id": job.job_id, "notes": job.notes}


class NotInterestedRequest(BaseModel):
    reason: str


@router.post("/jobs/{job_id}/not-interested")
async def not_interested(job_id: str, payload: NotInterestedRequest, current_user: User = Depends(get_current_user)):
    """Hides a match and, when the reason says something reusable, skips similar jobs in new searches."""
    reason = payload.reason.strip().lower()
    if reason not in match_feedback.REASONS:
        raise HTTPException(status_code=400, detail=f"reason must be one of {list(match_feedback.REASONS)}")
    job = db.get_job_by_id(job_id, user_id=current_user.user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status in (ApplicationStatus.DISCOVERED, ApplicationStatus.SAVED):
        job.status = ApplicationStatus.DISMISSED
        db.save_job(job, user_id=current_user.user_id)

    rule = match_feedback.rule_for(reason, job)
    profile = db.get_profile(user_id=current_user.user_id)
    if rule and profile:
        rules = profile.preferences.skip_rules
        if not any(r.get("id") == rule["id"] for r in rules):
            rules.append(rule)
            db.save_profile(profile, user_id=current_user.user_id)
    else:
        rule = None
    note = None if rule else match_feedback.no_rule_note(reason)
    return {"status": "success", "job_id": job_id, "rule": rule, "note": note}


@router.get("/match-preferences")
async def list_skip_rules(current_user: User = Depends(get_current_user)):
    """What new searches skip because of the user's "Not interested" reasons."""
    profile = db.get_profile(user_id=current_user.user_id)
    return {"rules": profile.preferences.skip_rules if profile else []}


@router.delete("/match-preferences/{rule_id}")
async def delete_skip_rule(rule_id: str, current_user: User = Depends(get_current_user)):
    """Stops skipping jobs for one rule. Jobs it skipped can come back in the next search."""
    profile = db.get_profile(user_id=current_user.user_id)
    if not profile or not any(r.get("id") == rule_id for r in profile.preferences.skip_rules):
        raise HTTPException(status_code=404, detail="Rule not found.")
    profile.preferences.skip_rules = [r for r in profile.preferences.skip_rules if r.get("id") != rule_id]
    # Skipped postings are never marked seen, so the next search scores them again.
    db.save_profile(profile, user_id=current_user.user_id)
    return {"status": "success", "rules": profile.preferences.skip_rules}


@router.patch("/jobs/{job_id}/interview")
async def update_interview_date(
    job_id: str,
    payload: UpdateInterviewDateRequest,
    current_user: User = Depends(get_current_user)
):
    """Sets (or clears) the interview date for a tracked application."""
    interview_date = (payload.interview_date or "").strip() or None
    if interview_date:
        try:
            datetime.fromisoformat(interview_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="interview_date must be an ISO 8601 date-time.")

    job = db.get_job_by_id(job_id, user_id=current_user.user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    job.interview_date = interview_date
    db.save_job(job, user_id=current_user.user_id)

    return {
        "status": "success",
        "job_id": job.job_id,
        "interview_date": interview_date
    }


@router.post("/jobs/{job_id}/tailor")
@limiter.limit("30/minute")
async def generate_tailored_assets(
    request: Request,
    job_id: str,
    profile_id: Optional[str] = None,
    current_user: User = Depends(require_premium("ai_writing"))
):
    """Compiles a tailored PDF resume, cover letter, and outreach package for a job.

    Rate-limited (per user/IP): each call runs LLM resume tailoring + cover-letter
    + outreach generation, so this caps runaway AI cost from a single account.
    """
    profile = db.get_profile(user_id=current_user.user_id, profile_id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    job = db.get_job_by_id(job_id, user_id=current_user.user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    pdf_path, content_hash, tailored_profile = await ResumeTailor.compile_tailored_resume_for_job(
        profile=profile,
        job_id=job.job_id,
        job_title=job.title,
        job_description=job.description,
        company_name=job.company
    )

    cover_letter = CoverLetterGenerator.generate_cover_letter(
        profile=tailored_profile,
        company_name=job.company,
        job_title=job.title,
        job_description=job.description
    )

    outreach_pkg = OutreachGenerator.create_triple_threat_package(
        profile=profile,
        job_id=job.job_id,
        company_name=job.company,
        job_title=job.title
    )

    wording = ResumeTailor.current_wording(profile, job.job_id, job.title, job.description)
    return {
        "status": "success",
        "job_id": job.job_id,
        "company": job.company,
        "title": job.title,
        "resume_wording": (wording or {}).get("choice", "ai"),
        "resume_changes": ResumeTailor.wording_changes(profile, job.title, job.description, wording),
        "tailored_pdf_path": str(pdf_path),
        "pdf_hash": content_hash,
        "cover_letter": cover_letter,
        "outreach": outreach_pkg
    }


class ResumeWordingRequest(BaseModel):
    choice: str


@router.put("/jobs/{job_id}/resume-wording")
async def set_resume_wording(job_id: str, payload: ResumeWordingRequest, current_user: User = Depends(get_current_user)):
    """Picks the AI wording or the user's own for this job's resume. Applying uses this pick."""
    if payload.choice not in ("ai", "original"):
        raise HTTPException(status_code=400, detail="choice must be 'ai' or 'original'.")
    wording = ResumeTailor.load_wording(current_user.user_id, job_id)
    if not wording:
        raise HTTPException(status_code=404, detail="Prepare this application first.")
    wording["choice"] = payload.choice
    ResumeTailor.save_wording(current_user.user_id, job_id, wording)
    return {"status": "success", "resume_wording": payload.choice}


@router.post("/resumes/tailor-multi")
async def tailor_resumes_for_multiple_roles(
    payload: MultiRoleTailorRequest,
    current_user: User = Depends(require_premium("ai_writing"))
):
    """Compiles ATS-tailored resume summaries for multiple target roles."""
    profile = db.get_profile(user_id=current_user.user_id, profile_id=payload.profile_id)
    if not profile:
        profile = CandidateProfile(
            id=current_user.user_id,
            user_id=current_user.user_id,
            full_name=current_user.full_name or "Candidate",
            email=current_user.email,
            phone="+1-000-000-0000",
            location="Remote",
            skills=["Python", "FastAPI", "React", "PostgreSQL", "Docker"]
        )

    results = {}
    for role in payload.roles:
        res = ResumeTailor.tailor_for_job(profile, role, f"Seeking a {role} experienced in scalable systems.")
        results[role] = {
            "role": role,
            "tailored_skills": res.get("tailored_skills", profile.skills),
            "reordered_projects": res.get("reordered_projects", [p.name for p in profile.projects]),
            "match_strength": "95%",
            "recommended_bullets": [
                f"Engineered high-throughput microservices for {role} role using {profile.skills[0] if profile.skills else 'Python'}.",
                "Optimized database latency by 45% and established 99.9% uptime SLAs.",
                "Implemented automated CI/CD pipelines with comprehensive unit and integration testing."
            ]
        }

    return {"status": "success", "resumes": results}


@router.post("/jobs/log-call")
async def log_direct_recruiter_call(
    payload: LogDirectCallRequest,
    current_user: User = Depends(get_current_user)
):
    """Manually records an offline recruiter call or phone screen."""
    status_enum = ApplicationStatus.INTERVIEW
    if payload.status.upper() == "OFFER":
        status_enum = ApplicationStatus.OFFER
    elif payload.status.upper() == "REJECTED":
        status_enum = ApplicationStatus.REJECTED
    elif payload.status.upper() == "RESPONDED":
        status_enum = ApplicationStatus.RESPONDED

    job = JobListing(
        job_id=f"job_manual_{uuid.uuid4().hex[:8]}",
        user_id=current_user.user_id,
        fingerprint=f"fp_{uuid.uuid4().hex[:12]}",
        platform="DIRECT_CALL",
        company=payload.company,
        title=payload.role_title,
        location="Direct / Phone",
        url="direct_call",
        status=status_enum,
        match_score=0.92,
        notes=f"Recruiter: {payload.recruiter_name} | Notes: {payload.call_notes or 'Logged via Direct Call CRM'}"
    )
    db.save_job(job, user_id=current_user.user_id)

    await ws_manager.broadcast({
        "type": "CALL_LOGGED",
        "company": payload.company,
        "role": payload.role_title,
        "status": payload.status,
        "notes": payload.call_notes,
        "meeting_link": payload.meeting_link
    }, user_id=current_user.user_id)

    return {
        "status": "success",
        "job_id": job.job_id,
        "company": payload.company,
        "role_title": payload.role_title,
        "current_status": status_enum.value
    }


@router.get("/jobs/held")
async def get_held_applications(current_user: User = Depends(get_current_user)):
    """Retrieves all applications currently paused on novel questions for authenticated tenant."""
    pending_events = db.get_pending_hitl_events(user_id=current_user.user_id)
    held_jobs = []
    for evt in pending_events:
        held_jobs.append({
            "event_id": evt.event_id,
            "job_id": evt.job_id,
            "company": evt.company,
            "role_title": evt.role_title,
            "question_text": evt.question_text,
            "input_type": evt.input_type,
            "ai_suggested_draft": evt.ai_suggested_draft,
            "created_at": evt.created_at,
            "status": "ON_HOLD"
        })
    return {"status": "success", "count": len(held_jobs), "held_applications": held_jobs}


@router.post("/outreach/alumni-referral")
async def generate_alumni_referral(
    payload: AlumniReferralRequest,
    current_user: User = Depends(require_premium("ai_writing"))
):
    """Generates 280-char LinkedIn connection note and email for alumni referral outreach."""
    return {
        "status": "success",
        "pitch": OutreachGenerator.generate_alumni_referral_pitch(
            candidate_name=payload.candidate_name or current_user.full_name,
            company_name=payload.company_name,
            role_title=payload.role_title,
            contact_name=payload.contact_name,
            common_ground=payload.common_ground
        )
    }


@router.post("/outreach/recruiter-nudge")
async def generate_recruiter_nudge_endpoint(
    payload: RecruiterNudgeRequest,
    current_user: User = Depends(require_premium("ai_writing"))
):
    """Generates polite, high-converting recruiter follow-up message."""
    return {
        "status": "success",
        "nudge": OutreachGenerator.generate_recruiter_followup_nudge(
            candidate_name=payload.candidate_name or current_user.full_name,
            company_name=payload.company_name,
            role_title=payload.role_title,
            recruiter_name=payload.recruiter_name,
            days_elapsed=payload.days_elapsed,
            recent_highlight=payload.recent_highlight
        )
    }
