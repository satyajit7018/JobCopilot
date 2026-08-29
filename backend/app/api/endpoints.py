"""
JobCopilot - API Endpoints
REST and WebSocket handlers for Onboarding, Questionnaire, Knowledge Vault,
Job Pipeline, Real-Time HITL Alerts, Dynamic Tailored Resumes, and Triple-Threat Outreach.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.config import RESUMES_DIR, DEFAULT_SUBMISSION_MODE
from app.core.models import CandidateProfile, VaultEntry, JobListing, HITLEvent, ApplicationStatus
from app.core.database import db
from app.core.resume_parser import ResumeParser
from app.core.questionnaire import QuestionnaireEngine
from app.core.compensation import CompensationConverter
from app.core.vector_vault import vault
from app.core.credential_vault import cred_vault
from app.core.resume_tailor import ResumeTailor
from app.core.cover_letter import CoverLetterGenerator
from app.core.outreach_generator import OutreachGenerator
from app.discovery.orchestrator import discovery_orchestrator

router = APIRouter(prefix="/api")


# --- WebSocket Connection Manager for Real-Time Bot Logs & HITL Events ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


ws_manager = ConnectionManager()


# --- Models for Request Payloads ---
class QuestionnaireSubmitRequest(BaseModel):
    profile_id: str = "default_user"
    answers: Dict[str, Any]


class VaultLearnRequest(BaseModel):
    question: str
    answer: str
    slot_type: Optional[str] = None
    slot_key: Optional[str] = None


class HITLResolveRequest(BaseModel):
    event_id: str
    user_answer: str
    save_to_vault: bool = True


# --- Endpoints ---

@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0", "storage": "sqlite_wal"}


@router.post("/upload-resume")
async def upload_resume(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
    profile_id: str = Form("default_user")
):
    """Uploads and parses a resume (PDF, DOCX, or text) and auto-prefills questionnaire."""
    if file:
        file_path = RESUMES_DIR / f"{profile_id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        profile = ResumeParser.parse_to_profile(str(file_path), profile_id=profile_id)
    elif raw_text:
        profile = ResumeParser.parse_to_profile(raw_text, profile_id=profile_id)
    else:
        raise HTTPException(status_code=400, detail="No resume file or raw text provided.")

    # Save to SQLite and seed the Knowledge Vault
    db.save_profile(profile)
    vault.seed_from_profile(profile)

    # Generate 70% prefilled questionnaire
    prefilled_data = QuestionnaireEngine.prefill_from_profile(profile)
    questions_schema = QuestionnaireEngine.get_questions_schema()

    return {
        "status": "success",
        "profile": profile.dict(),
        "prefilled_questionnaire": prefilled_data,
        "questions_schema": questions_schema
    }


@router.get("/profile")
async def get_profile(profile_id: str = "default_user"):
    """Retrieves current candidate profile."""
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found. Please upload a resume.")
    return {"status": "success", "profile": profile.dict()}


@router.get("/questionnaire")
async def get_questionnaire(profile_id: str = "default_user"):
    """Retrieves the 8 baseline recruiter questions schema and prefilled answers."""
    profile = db.get_profile(profile_id)
    schema = QuestionnaireEngine.get_questions_schema()
    prefilled = QuestionnaireEngine.prefill_from_profile(profile) if profile else {}
    return {
        "questions_schema": schema,
        "prefilled": prefilled
    }


@router.post("/questionnaire")
async def submit_questionnaire(payload: QuestionnaireSubmitRequest):
    """Applies user-confirmed answers to profile and Knowledge Vault."""
    profile = db.get_profile(payload.profile_id)
    if not profile:
        profile = CandidateProfile(
            id=payload.profile_id,
            full_name=payload.answers.get("full_name", "Candidate Name"),
            email=payload.answers.get("email", "candidate@example.com"),
            phone=payload.answers.get("phone", "+91 0000000000"),
            location=payload.answers.get("location", "Remote / India")
        )

    updated_profile = QuestionnaireEngine.apply_answers_to_profile(profile, payload.answers)
    db.save_profile(updated_profile)
    vault.seed_from_profile(updated_profile)

    return {
        "status": "success",
        "message": "Recruiter preferences saved and Knowledge Vault seeded successfully!",
        "profile": updated_profile.dict()
    }


@router.get("/vault")
async def get_vault_entries():
    """Returns all indexed Q&A slots with usage counts and last used timestamps."""
    entries = db.get_all_vault_entries()
    return {
        "count": len(entries),
        "entries": [e.dict() for e in entries]
    }


@router.post("/vault/learn")
async def learn_vault_entry(payload: VaultLearnRequest):
    """Manually teaches or updates a Q&A slot."""
    entry = vault.learn_answer(
        question=payload.question,
        answer_template=payload.answer,
        slot_type=payload.slot_type,
        slot_key=payload.slot_key
    )
    return {"status": "success", "entry": entry.dict()}


# --- 0-Day Discovery Endpoints ---

@router.post("/discovery/run")
async def run_discovery(profile_id: str = "default_user"):
    """Triggers an async 0-day job discovery cycle across ATS APIs and VC boards."""
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found.")

    await ws_manager.broadcast({"type": "BOT_LOG", "message": "Starting 0-day multi-source job discovery cycle..."})
    
    result = await discovery_orchestrator.run_discovery_cycle(profile)
    
    await ws_manager.broadcast({
        "type": "DISCOVERY_COMPLETED",
        "total_sourced": result.get("total_sourced", 0),
        "matched_and_saved": result.get("matched_and_saved", 0)
    })

    return result


@router.get("/discovery/status")
async def get_discovery_status():
    """Returns current discovery metrics."""
    return {
        "is_running": discovery_orchestrator.is_running,
        "last_run_at": discovery_orchestrator.last_run_at,
        "total_discovered": discovery_orchestrator.total_discovered,
        "total_matched": discovery_orchestrator.total_matched
    }


@router.get("/jobs")
async def get_jobs(status: Optional[str] = None):
    """Returns all tracked job applications, optionally filtered by status."""
    jobs = db.get_jobs(status=status)
    return {
        "count": len(jobs),
        "jobs": [j.dict() for j in jobs]
    }


# --- Tailored Resume & Triple-Threat Outreach Generation Endpoint ---

@router.post("/jobs/{job_id}/tailor")
async def generate_tailored_assets(job_id: str, profile_id: str = "default_user"):
    """Compiles a bespoke tailored PDF resume, cover letter, and triple-threat outreach for a job."""
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    # Find job in database
    jobs = db.get_jobs()
    job = next((j for j in jobs if j.job_id == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # 1. Compile Tailored PDF Resume
    pdf_path, content_hash, tailored_profile = await ResumeTailor.compile_tailored_resume_for_job(
        profile=profile,
        job_id=job.job_id,
        job_title=job.title,
        job_description=job.description,
        company_name=job.company
    )

    # 2. Generate Anti-AI Cover Letter
    cover_letter = CoverLetterGenerator.generate_cover_letter(
        profile=tailored_profile,
        company_name=job.company,
        job_title=job.title,
        job_description=job.description
    )

    # 3. Generate Triple-Threat Outreach Package
    outreach_pkg = OutreachGenerator.create_triple_threat_package(
        profile=profile,
        job_id=job.job_id,
        company_name=job.company,
        job_title=job.title
    )

    return {
        "status": "success",
        "job_id": job.job_id,
        "company": job.company,
        "title": job.title,
        "tailored_pdf_path": str(pdf_path),
        "pdf_hash": content_hash,
        "cover_letter": cover_letter,
        "outreach": outreach_pkg
    }


@router.get("/hitl/pending")
async def get_pending_hitl():
    """Returns all pending HITL questions requiring human input."""
    events = db.get_pending_hitl_events()
    return {
        "count": len(events),
        "events": [e.dict() for e in events]
    }


@router.post("/hitl/resolve")
async def resolve_hitl(payload: HITLResolveRequest):
    """Atomically resolves a pending HITL question and permanently saves it to the vault."""
    success = db.resolve_hitl_event(payload.event_id, payload.user_answer)
    if not success:
        raise HTTPException(status_code=400, detail="Event already resolved or not found.")

    if payload.save_to_vault:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT question_text FROM hitl_events WHERE event_id = ?", (payload.event_id,))
            row = cursor.fetchone()
            if row:
                vault.learn_answer(row["question_text"], payload.user_answer)

    await ws_manager.broadcast({
        "type": "HITL_RESOLVED",
        "event_id": payload.event_id,
        "user_answer": payload.user_answer
    })

    return {"status": "success", "message": "HITL event resolved and indexed permanently."}


# --- Autonomous Bot Execution Endpoint ---

@router.post("/bot/apply/{job_id}")
async def apply_to_job(job_id: str, profile_id: str = "default_user", mode: Optional[str] = None):
    """Executes full autonomous stealth application workflow for a specific job."""
    from app.bot.runner import AutonomousJobRunner
    runner = AutonomousJobRunner(mode=mode or DEFAULT_SUBMISSION_MODE)
    result = await runner.execute_application(
        job_id=job_id,
        profile_id=profile_id,
        ws_broadcast_callback=ws_manager.broadcast
    )
    return result
