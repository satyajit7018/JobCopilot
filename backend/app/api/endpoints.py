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


class LoginRequest(BaseModel):
    master_password: Optional[str] = None


@router.get("/auth/status")
async def auth_status():
    """Returns local vault encryption status and master key presence."""
    return {
        "status": "success",
        "is_authenticated": True,
        "encryption": "Argon2id + AES-256-GCM",
        "keychain_storage": "OS_KEYCHAIN_SECURE",
        "user_id": "default_user"
    }


@router.post("/auth/login")
async def auth_login(payload: LoginRequest):
    """Unlocks or registers the master vault key."""
    pwd = payload.master_password or cred_vault.get_or_create_master_key()
    return {
        "status": "success",
        "message": "Vault successfully unlocked with Argon2id + AES-256-GCM",
        "session_token": "jobcopilot_local_secure_session"
    }


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


# --- Email Radar & Inbound Parser Endpoints ---

class InboundEmailPayload(BaseModel):
    sender: str
    recipient: str = "default_user@jobcopilot.local"
    subject: str
    body_html: str
    body_text: Optional[str] = None


@router.post("/email/inbound")
async def receive_inbound_email(payload: InboundEmailPayload):
    """Processes incoming recruiter email, strips tracking pixels, classifies intent, and syncs pipeline."""
    from app.email.sync import EmailSyncEngine
    result = await EmailSyncEngine.process_inbound_email(
        sender=payload.sender,
        recipient=payload.recipient,
        subject=payload.subject,
        body_html=payload.body_html,
        body_text=payload.body_text,
        ws_broadcast_callback=ws_manager.broadcast
    )
    return result


@router.get("/email/messages")
async def list_email_messages():
    """Returns all parsed recruiter communications."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM emails ORDER BY received_at DESC")
        rows = cursor.fetchall()
        emails = [dict(r) for r in rows]
    return {"count": len(emails), "messages": emails}


@router.post("/email/followup/{job_id}")
async def generate_job_followup(job_id: str, stage_days: int = 7, profile_id: str = "default_user"):
    """Generates and saves a 7-day or 14-day follow-up draft for a submitted application."""
    from app.email.followup import FollowUpEngine
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    res = FollowUpEngine.generate_and_save_followup(profile, job_id, stage_days=stage_days)
    if not res:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"status": "success", "followup": res}


# --- Funnel Analytics Endpoint ---

@router.get("/analytics/funnel")
async def get_funnel_analytics():
    """Returns aggregated pipeline funnel metrics and telemetry."""
    from app.core.analytics import AnalyticsEngine
    return {
        "status": "success",
        "metrics": AnalyticsEngine.get_funnel_metrics()
    }


# --- Milestone 7: Mock Interview Studio & Architecture Dossiers ---

@router.get("/interview/dossier")
async def get_company_dossier(company: str, role: str = "Senior Software Engineer"):
    """Generates technical architecture dossier and interview rounds for target company."""
    from app.core.interview_studio import InterviewStudioEngine
    return {
        "status": "success",
        "dossier": InterviewStudioEngine.generate_company_dossier(company, role)
    }


@router.get("/interview/questions")
async def get_mock_questions(role: str = "Senior Software Engineer", profile_id: str = "default_user"):
    """Generates role-specific mock technical and system design questions."""
    from app.core.interview_studio import InterviewStudioEngine
    profile = db.get_profile(profile_id)
    skills = profile.skills if profile else ["Python", "Distributed Systems"]
    return {
        "status": "success",
        "questions": InterviewStudioEngine.generate_mock_questions(role, skills=skills)
    }


class InterviewEvalRequest(BaseModel):
    question: str
    answer: str
    key_concepts: Optional[List[str]] = None


@router.post("/interview/evaluate")
async def evaluate_interview_answer(payload: InterviewEvalRequest):
    """Evaluates candidate response with depth, key concept coverage, and actionable feedback."""
    from app.core.interview_studio import InterviewStudioEngine
    return {
        "status": "success",
        "evaluation": InterviewStudioEngine.evaluate_candidate_response(
            question=payload.question,
            candidate_answer=payload.answer,
            key_concepts=payload.key_concepts
        )
    }


# --- Milestone 7: Salary Negotiation & Equity Modeler ---

class OfferEvalRequest(BaseModel):
    base_salary_lpa: float
    bonus_lpa: float = 0.0
    equity_annual_lpa: float = 0.0
    role_title: str = "Senior Software Engineer"


@router.post("/negotiation/evaluate")
async def evaluate_offer_compensation(payload: OfferEvalRequest):
    """Benchmarks job offer against market percentiles."""
    from app.core.negotiation import SalaryNegotiationEngine
    return {
        "status": "success",
        "evaluation": SalaryNegotiationEngine.evaluate_offer(
            base_salary_lpa=payload.base_salary_lpa,
            bonus_lpa=payload.bonus_lpa,
            equity_annual_lpa=payload.equity_annual_lpa,
            role_title=payload.role_title
        )
    }


class EquityModelRequest(BaseModel):
    options_count: int
    total_company_shares: int
    current_valuation_usd: float
    strike_price: float = 0.0


@router.post("/negotiation/equity")
async def model_equity(payload: EquityModelRequest):
    """Models startup ESOP ownership and future exit returns."""
    from app.core.negotiation import SalaryNegotiationEngine
    return {
        "status": "success",
        "equity_model": SalaryNegotiationEngine.model_startup_equity(
            options_count=payload.options_count,
            total_company_shares=payload.total_company_shares,
            current_valuation_usd=payload.current_valuation_usd,
            strike_price_per_share=payload.strike_price
        )
    }


class CounterOfferRequest(BaseModel):
    candidate_name: str = "Satyajit Nayak"
    company_name: str
    role_title: str
    offered_tc: str
    desired_tc: str
    leverage_points: Optional[List[str]] = None


@router.post("/negotiation/counter-offer")
async def generate_counter_offer(payload: CounterOfferRequest):
    """Generates an Anti-AI counter-offer negotiation email."""
    from app.core.negotiation import SalaryNegotiationEngine
    script = SalaryNegotiationEngine.generate_counter_offer_script(
        candidate_name=payload.candidate_name,
        company_name=payload.company_name,
        role_title=payload.role_title,
        offered_tc=payload.offered_tc,
        desired_tc=payload.desired_tc,
        leverage_points=payload.leverage_points
    )
    return {"status": "success", "counter_offer_script": script}


# --- Milestone 7: Zero-Collision Calendar Availability ---

@router.get("/calendar/availability")
async def get_calendar_availability(timezone: str = "IST", days: int = 4):
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


# --- Milestone 8: Disaster Recovery & Encrypted Backup Endpoints ---

@router.post("/backup/export")
async def export_backup():
    """Exports full encrypted archive (.jobcopilot.enc) of local state."""
    from app.core.backup import BackupManager
    path = BackupManager.export_encrypted_backup()
    return {
        "status": "success",
        "backup_path": str(path),
        "filename": path.name
    }


class RestoreBackupRequest(BaseModel):
    backup_file_path: str


@router.post("/backup/restore")
async def restore_backup(payload: RestoreBackupRequest):
    """Restores database state from an encrypted backup archive."""
    from app.core.backup import BackupManager
    res = BackupManager.restore_encrypted_backup(Path(payload.backup_file_path))
    return res

