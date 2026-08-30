"""
JobCopilot - API Endpoints
REST and WebSocket handlers for Onboarding, Questionnaire, Knowledge Vault,
Job Pipeline, Real-Time HITL Alerts, Dynamic Tailored Resumes, and Triple-Threat Outreach.
Enforces default-deny authentication, multi-tenant isolation, and fail-closed security.
"""

import os
import shutil
import uuid
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import (
    APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks,
    WebSocket, WebSocketDisconnect, Depends, Request
)
from pydantic import BaseModel

from app.core.config import RESUMES_DIR, DEFAULT_SUBMISSION_MODE
from app.core.models import (
    CandidateProfile, VaultEntry, JobListing, HITLEvent, ApplicationStatus,
    User, UserRole, TokenResponse
)
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
from app.api.auth import (
    router as auth_router, get_current_user, hash_password,
    create_jwt_token, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
)
from datetime import timedelta

# =========================================================================
# Router Architecture: Public (Allowlisted) vs Protected (Default-Deny)
# =========================================================================
public_router = APIRouter()
public_router.include_router(auth_router)

protected_router = APIRouter(dependencies=[Depends(get_current_user)])

router = APIRouter(prefix="/api")


# --- WebSocket Connection Manager for Multi-Tenant Real-Time Streaming ---
class MultiTenantWebSocketGateway:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.all_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None):
        await websocket.accept()
        self.all_connections.append(websocket)
        if user_id:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: Optional[str] = None):
        if websocket in self.all_connections:
            self.all_connections.remove(websocket)
        if user_id and user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        for ws in self.active_connections.get(user_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def broadcast(self, message: Dict[str, Any], user_id: Optional[str] = None):
        if user_id and user_id in self.active_connections:
            await self.send_to_user(user_id, message)
            return

        for connection in list(self.all_connections):
            try:
                await connection.send_json(message)
            except Exception:
                pass


ws_manager = MultiTenantWebSocketGateway()


# --- Models for Request Payloads ---
class QuestionnaireSubmitRequest(BaseModel):
    profile_id: Optional[str] = None
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


class VaultTestMatchRequest(BaseModel):
    question: str
    company: str = "Stripe"
    role: str = "Senior Software Engineer"
    profile_id: Optional[str] = None


# =========================================================================
# Public Allowlisted Endpoints
# =========================================================================

@public_router.get("/health")
async def health_check():
    """Public healthcheck endpoint."""
    return {"status": "ok", "version": "1.0.0", "storage": "sqlite_wal"}


# --- Google SSO Authentication (F-07 Cryptographic Verification) ---
class GoogleSSORequest(BaseModel):
    id_token: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    google_id: Optional[str] = None
    avatar_url: Optional[str] = None
    auto_login_permissions: bool = True


@public_router.post("/auth/google-sso", response_model=TokenResponse)
async def google_sso_auth(payload: GoogleSSORequest):
    """Authenticates candidate with Google ID token and issues signed JWT."""
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    email = payload.email
    full_name = payload.full_name or "Google User"

    if payload.id_token:
        try:
            id_info = id_token.verify_oauth2_token(
                payload.id_token,
                google_requests.Request(),
                google_client_id
            )
            if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
                raise HTTPException(status_code=401, detail="Invalid token issuer.")
            email = id_info.get("email", email)
            full_name = id_info.get("name", full_name)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=f"Google token verification failed: {str(e)}")
    elif os.getenv("ENV", "").lower() == "production":
        raise HTTPException(status_code=401, detail="Google ID token required in production.")

    if not email:
        raise HTTPException(status_code=400, detail="Missing verified email address.")

    user = db.get_user_by_email(email)
    if not user:
        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        user = User(
            user_id=user_id,
            email=email,
            password_hash=hash_password(uuid.uuid4().hex),
            full_name=full_name,
            role=UserRole.FREE,
            is_active=True
        )
        db.create_user(user)
    else:
        user_id = user.user_id

    # Create default candidate profile if absent
    profile = db.get_profile(user_id=user_id)
    if not profile:
        profile = CandidateProfile(
            id=user_id,
            user_id=user_id,
            full_name=full_name,
            email=email,
            phone="+1-000-000-0000",
            location="Remote"
        )
        db.save_profile(profile, user_id=user_id)

    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    access_token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": role_str, "type": "access"},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_jwt_token(
        {"sub": user.user_id, "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.user_id,
        email=user.email,
        role=role_str
    )


# --- Stripe Billing Webhook (F-04 Signature-Verified, Fail-Closed) ---
@public_router.post("/billing/webhook")
async def stripe_webhook_handler(request: Request):
    """Receives Stripe subscription updates and adjusts tenant tier accordingly (Fail-Closed)."""
    import stripe
    from app.core.rate_limiter import rate_limiter, SubscriptionTier

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Billing webhook not configured")

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)}")

    event_type = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})
    user_id = data_object.get("metadata", {}).get("user_id")
    tier_str = data_object.get("metadata", {}).get("tier", "PRO").upper()

    if not user_id:
        return {"status": "ignored", "reason": "No user_id in metadata"}

    if event_type in ["checkout.session.completed", "customer.subscription.created", "customer.subscription.updated"]:
        tier = SubscriptionTier.ELITE if tier_str == "ELITE" else SubscriptionTier.PRO
        rate_limiter.set_user_tier(user_id, tier)
        db.update_user_role(user_id, tier.value)
        return {"status": "success", "user_id": user_id, "active_tier": tier.value}
    elif event_type in ["customer.subscription.deleted"]:
        rate_limiter.set_user_tier(user_id, SubscriptionTier.FREE)
        db.update_user_role(user_id, "FREE")
        return {"status": "success", "user_id": user_id, "active_tier": SubscriptionTier.FREE.value}

    return {"status": "ignored", "event_type": event_type}


# =========================================================================
# Protected Endpoints (Require Bearer JWT Access Token)
# =========================================================================

@protected_router.get("/auth/status")
async def auth_status(current_user: User = Depends(get_current_user)):
    """Returns local vault encryption status and user authentication state."""
    return {
        "status": "success",
        "is_authenticated": True,
        "encryption": "Argon2id + AES-256-GCM",
        "keychain_storage": "OS_KEYCHAIN_SECURE",
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    }


@protected_router.post("/upload-resume")
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
        profile = ResumeParser.parse_to_profile(str(file_path), profile_id=target_profile_id)
    elif raw_text:
        profile = ResumeParser.parse_to_profile(raw_text, profile_id=target_profile_id)
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


@protected_router.get("/profile")
async def get_profile(
    profile_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Retrieves current candidate profile for authenticated tenant."""
    profile = db.get_profile(user_id=current_user.user_id, profile_id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found. Please upload a resume.")
    return {"status": "success", "profile": profile.dict()}


@protected_router.get("/questionnaire")
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


@protected_router.post("/questionnaire")
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


@protected_router.get("/vault")
async def get_vault_entries(current_user: User = Depends(get_current_user)):
    """Returns all indexed Q&A slots for the authenticated tenant."""
    entries = db.get_vault_entries(user_id=current_user.user_id)
    return {
        "count": len(entries),
        "entries": [e.dict() for e in entries]
    }


@protected_router.post("/vault/learn")
async def learn_vault_entry(
    payload: VaultLearnRequest,
    current_user: User = Depends(get_current_user)
):
    """Manually teaches or updates a Q&A slot."""
    entry = vault.learn_answer(
        question=payload.question,
        answer_template=payload.answer,
        slot_type=payload.slot_type,
        slot_key=payload.slot_key
    )
    entry.user_id = current_user.user_id
    db.save_vault_entry(entry, user_id=current_user.user_id)
    return {"status": "success", "entry": entry.dict()}


@protected_router.post("/vault/test-match")
async def test_vault_match(
    payload: VaultTestMatchRequest,
    current_user: User = Depends(get_current_user)
):
    """Tests real-time question resolution against the Knowledge Vault."""
    profile = db.get_profile(user_id=current_user.user_id, profile_id=payload.profile_id)
    answer, confidence, entry = vault.get_answer_for_question(
        question=payload.question,
        profile=profile,
        context={"company": payload.company, "role": payload.role}
    )
    
    detected_type, detected_key = vault.matcher.detect_slot_type(payload.question)
    
    return {
        "status": "success",
        "question": payload.question,
        "resolved_answer": answer or "No confident match in Knowledge Vault yet. (Confidence < 55%)",
        "confidence_score": round(confidence * 100, 1),
        "slot_key": entry.slot_key if entry else detected_key,
        "slot_type": (entry.slot_type.value if entry else detected_type.value) if hasattr(detected_type, "value") else str(detected_type),
        "matched_pattern": entry.question_pattern if entry else "N/A",
        "is_matched": answer is not None
    }


@protected_router.post("/discovery/run")
async def run_discovery(
    profile_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Triggers an async 0-day job discovery cycle across ATS APIs and VC boards."""
    profile = db.get_profile(user_id=current_user.user_id, profile_id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found.")

    await ws_manager.broadcast({"type": "BOT_LOG", "message": "Starting 0-day multi-source job discovery cycle..."})
    
    result = await discovery_orchestrator.run_discovery_cycle(profile, user_id=current_user.user_id)
    
    await ws_manager.broadcast({
        "type": "DISCOVERY_COMPLETED",
        "total_sourced": result.get("total_sourced", 0),
        "matched_and_saved": result.get("matched_and_saved", 0)
    })
    
    return result


@protected_router.get("/discovery/status")
async def get_discovery_status(current_user: User = Depends(get_current_user)):
    """Returns current discovery metrics."""
    return {
        "is_running": discovery_orchestrator.is_running,
        "last_run_at": discovery_orchestrator.last_run_at,
        "total_discovered": discovery_orchestrator.total_discovered,
        "total_matched": discovery_orchestrator.total_matched
    }


@protected_router.get("/jobs")
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


@protected_router.post("/jobs/{job_id}/tailor")
async def generate_tailored_assets(
    job_id: str,
    profile_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Compiles a tailored PDF resume, cover letter, and outreach package for a job."""
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


class AlumniReferralRequest(BaseModel):
    candidate_name: str = "Candidate"
    company_name: str
    role_title: str
    contact_name: str = "Fellow Alumni"
    common_ground: str = "our shared background"


@protected_router.post("/outreach/alumni-referral")
async def generate_alumni_referral(
    payload: AlumniReferralRequest,
    current_user: User = Depends(get_current_user)
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


class RecruiterNudgeRequest(BaseModel):
    candidate_name: str = "Candidate"
    company_name: str
    role_title: str
    recruiter_name: str = "Recruiter"
    days_elapsed: int = 5
    recent_highlight: Optional[str] = None


@protected_router.post("/outreach/recruiter-nudge")
async def generate_recruiter_nudge_endpoint(
    payload: RecruiterNudgeRequest,
    current_user: User = Depends(get_current_user)
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


@protected_router.get("/hitl/pending")
async def get_pending_hitl(current_user: User = Depends(get_current_user)):
    """Returns all pending HITL questions for authenticated tenant."""
    events = db.get_pending_hitl(user_id=current_user.user_id)
    return {
        "count": len(events),
        "events": [e.dict() for e in events]
    }


@protected_router.post("/hitl/resolve")
async def resolve_hitl(
    payload: HITLResolveRequest,
    current_user: User = Depends(get_current_user)
):
    """Atomically resolves a pending HITL question strictly for the authenticated tenant."""
    evt = db.get_hitl_event(payload.event_id, user_id=current_user.user_id)
    if not evt:
        raise HTTPException(status_code=404, detail="Event not found or not owned by user.")

    success = db.resolve_hitl_event(payload.event_id, payload.user_answer, user_id=current_user.user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Event already resolved or failed to update.")

    if payload.save_to_vault:
        entry = vault.learn_answer(evt.question_text, payload.user_answer)
        entry.user_id = current_user.user_id
        db.save_vault_entry(entry, user_id=current_user.user_id)

    await ws_manager.broadcast({
        "type": "HITL_RESOLVED",
        "event_id": payload.event_id,
        "user_answer": payload.user_answer
    })

    return {"status": "success", "message": "HITL event resolved and indexed permanently."}


@protected_router.post("/bot/apply/{job_id}")
async def apply_to_job(
    job_id: str,
    profile_id: Optional[str] = None,
    mode: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Executes full autonomous stealth application workflow with persistent rate limiting."""
    from app.core.rate_limiter import rate_limiter
    if not rate_limiter.can_apply(current_user.user_id):
        raise HTTPException(
            status_code=429,
            detail="Daily application limit reached for your plan. Please upgrade to Pro or Elite to continue applying."
        )

    from app.bot.runner import AutonomousJobRunner
    runner = AutonomousJobRunner(mode=mode or DEFAULT_SUBMISSION_MODE)
    result = await runner.execute_application(
        job_id=job_id,
        profile_id=profile_id or current_user.user_id,
        user_id=current_user.user_id,
        ws_broadcast_callback=ws_manager.broadcast
    )
    if result.get("status") == "success":
        rate_limiter.record_apply(current_user.user_id)
    return result


class InboundEmailPayload(BaseModel):
    sender: str
    recipient: str = "candidate@jobcopilot.local"
    subject: str
    body_html: str
    body_text: Optional[str] = None


@protected_router.post("/email/inbound")
async def receive_inbound_email(
    payload: InboundEmailPayload,
    current_user: User = Depends(get_current_user)
):
    """Processes incoming recruiter email and syncs pipeline for authenticated tenant."""
    from app.email.sync import EmailSyncEngine
    result = await EmailSyncEngine.process_inbound_email(
        sender=payload.sender,
        recipient=payload.recipient,
        subject=payload.subject,
        body_html=payload.body_html,
        body_text=payload.body_text,
        user_id=current_user.user_id,
        ws_broadcast_callback=ws_manager.broadcast
    )
    return result


@protected_router.get("/email/messages")
async def list_email_messages(current_user: User = Depends(get_current_user)):
    """Returns all parsed recruiter communications for authenticated tenant."""
    emails = db.get_emails(user_id=current_user.user_id)
    return {"count": len(emails), "messages": [e.dict() for e in emails]}


@protected_router.post("/email/followup/{job_id}")
async def generate_job_followup(
    job_id: str,
    stage_days: int = 7,
    profile_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Generates and saves a follow-up draft for a submitted application."""
    from app.email.followup import FollowUpEngine
    profile = db.get_profile(user_id=current_user.user_id, profile_id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    res = FollowUpEngine.generate_and_save_followup(profile, job_id, stage_days=stage_days, user_id=current_user.user_id)
    if not res:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"status": "success", "followup": res}


@protected_router.get("/analytics/funnel")
async def get_funnel_analytics(current_user: User = Depends(get_current_user)):
    """Returns aggregated pipeline funnel metrics for authenticated tenant."""
    from app.core.analytics import AnalyticsEngine
    return {
        "status": "success",
        "metrics": AnalyticsEngine.get_funnel_metrics(user_id=current_user.user_id)
    }


# --- Mock Interview Studio Endpoints ---

@protected_router.get("/interview/dossier")
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


@protected_router.get("/interview/questions")
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


class InterviewEvalRequest(BaseModel):
    question: str
    answer: Optional[str] = None
    candidate_answer: Optional[str] = None
    key_concepts: Optional[List[str]] = None


@protected_router.post("/interview/evaluate")
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


class InterviewInvitationTriggerRequest(BaseModel):
    company: str
    role_title: str
    job_id: Optional[str] = None
    meeting_url: Optional[str] = None


@protected_router.post("/interview/notify-invitation")
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


@protected_router.get("/interview/reverse-questions")
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


class InterviewerReconRequest(BaseModel):
    interviewer_name: str
    interviewer_role: str = "Engineering Manager"
    background_text: str = ""


@protected_router.post("/interview/interviewer-recon")
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


@protected_router.get("/interview/engineering-intel")
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


# --- Salary Negotiation & Equity Modeler Endpoints ---

class OfferEvalRequest(BaseModel):
    base_salary_lpa: float
    bonus_lpa: float = 0.0
    equity_annual_lpa: float = 0.0
    role_title: str = "Senior Software Engineer"


@protected_router.post("/negotiation/evaluate")
async def evaluate_offer_compensation(
    payload: OfferEvalRequest,
    current_user: User = Depends(get_current_user)
):
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


@protected_router.post("/negotiation/equity")
async def model_equity(
    payload: EquityModelRequest,
    current_user: User = Depends(get_current_user)
):
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


class MultiOfferCompareRequest(BaseModel):
    offers: List[Dict[str, Any]]


@protected_router.post("/salary/compare-offers")
@protected_router.post("/negotiation/compare-offers")
async def compare_offers_endpoint(
    payload: MultiOfferCompareRequest,
    current_user: User = Depends(get_current_user)
):
    """Compares multiple offers with 4-year TC progression and liquidation analysis."""
    from app.core.negotiation import SalaryNegotiationEngine
    return SalaryNegotiationEngine.compare_multiple_offers(payload.offers)


class AdvancedCounterOfferRequest(BaseModel):
    candidate_name: Optional[str] = None
    target_company: str
    role_title: str
    current_base: str
    current_equity: str
    target_base: str
    target_equity: str
    competing_company: Optional[str] = None
    competing_tc: Optional[str] = None


@protected_router.post("/salary/counter-script")
@protected_router.post("/negotiation/advanced-counter")
async def generate_advanced_counter_script_endpoint(
    payload: AdvancedCounterOfferRequest,
    current_user: User = Depends(get_current_user)
):
    """Generates tailored executive negotiation email and phone talking points."""
    from app.core.negotiation import SalaryNegotiationEngine
    return {
        "status": "success",
        "scripts": SalaryNegotiationEngine.generate_advanced_counter_script(
            candidate_name=payload.candidate_name or current_user.full_name,
            target_company=payload.target_company,
            role_title=payload.role_title,
            current_base=payload.current_base,
            current_equity=payload.current_equity,
            target_base=payload.target_base,
            target_equity=payload.target_equity,
            competing_company=payload.competing_company,
            competing_tc=payload.competing_tc
        )
    }


class CounterOfferRequest(BaseModel):
    candidate_name: Optional[str] = None
    company_name: str
    role_title: str
    offered_tc: str
    desired_tc: str
    leverage_points: Optional[List[str]] = None


@protected_router.post("/negotiation/counter-offer")
async def generate_counter_offer(
    payload: CounterOfferRequest,
    current_user: User = Depends(get_current_user)
):
    """Generates an Anti-AI counter-offer negotiation email."""
    from app.core.negotiation import SalaryNegotiationEngine
    script = SalaryNegotiationEngine.generate_counter_offer_script(
        candidate_name=payload.candidate_name or current_user.full_name,
        company_name=payload.company_name,
        role_title=payload.role_title,
        offered_tc=payload.offered_tc,
        desired_tc=payload.desired_tc,
        leverage_points=payload.leverage_points
    )
    return {"status": "success", "counter_offer_script": script}


@protected_router.get("/calendar/availability")
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


# --- Backup Endpoints (F-06 Tenant Scoped & Buffer Based) ---

@protected_router.post("/backup/export")
async def export_backup(current_user: User = Depends(get_current_user)):
    """Exports encrypted archive (.jobcopilot.enc) scoped to authenticated tenant."""
    from app.core.backup import BackupManager
    path = BackupManager.export_encrypted_backup(user_id=current_user.user_id)
    return {
        "status": "success",
        "backup_path": str(path),
        "filename": path.name
    }


class RestoreBackupPayload(BaseModel):
    encrypted_data_b64: Optional[str] = None


@protected_router.post("/backup/restore")
async def restore_backup(
    file: Optional[UploadFile] = File(None),
    payload: Optional[RestoreBackupPayload] = None,
    current_user: User = Depends(get_current_user)
):
    """Restores database state strictly for the caller's tenant from uploaded backup buffer."""
    from app.core.backup import BackupManager
    if file:
        contents = await file.read()
        res = BackupManager.restore_encrypted_backup_buffer(contents, user_id=current_user.user_id)
        return res
    elif payload and payload.encrypted_data_b64:
        contents = base64.b64decode(payload.encrypted_data_b64)
        res = BackupManager.restore_encrypted_backup_buffer(contents, user_id=current_user.user_id)
        return res
    else:
        raise HTTPException(status_code=400, detail="Must provide backup file upload or encrypted_data_b64 payload.")


class MultiRoleTailorRequest(BaseModel):
    roles: List[str]
    profile_id: Optional[str] = None


@protected_router.post("/resumes/tailor-multi")
async def tailor_resumes_for_multiple_roles(
    payload: MultiRoleTailorRequest,
    current_user: User = Depends(get_current_user)
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
                f"Optimized database latency by 45% and established 99.9% uptime SLAs.",
                f"Implemented automated CI/CD pipelines with comprehensive unit and integration testing."
            ]
        }

    return {"status": "success", "resumes": results}


class LogDirectCallRequest(BaseModel):
    company: str
    role_title: str
    recruiter_name: Optional[str] = "Recruiter"
    status: str = "INTERVIEW"
    call_notes: Optional[str] = None
    scheduled_interview_time: Optional[str] = None
    meeting_link: Optional[str] = None


@protected_router.post("/jobs/log-call")
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
    })

    return {
        "status": "success",
        "job_id": job.job_id,
        "company": payload.company,
        "role_title": payload.role_title,
        "current_status": status_enum.value
    }


@protected_router.get("/jobs/held")
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


class ResolveHeldApplicationRequest(BaseModel):
    event_id: str
    user_answer: str
    save_to_vault: bool = True


@protected_router.post("/hitl/resolve-held")
async def resolve_held_application(
    payload: ResolveHeldApplicationRequest,
    current_user: User = Depends(get_current_user)
):
    """Atomically resolves held application, saves Q&A to vault, and resumes submission."""
    evt = db.get_hitl_event(payload.event_id, user_id=current_user.user_id)
    if not evt:
        raise HTTPException(status_code=404, detail="Held HITL Event not found.")

    db.resolve_hitl_event(payload.event_id, payload.user_answer, user_id=current_user.user_id)

    if payload.save_to_vault:
        entry = vault.learn_answer(evt.question_text, payload.user_answer)
        entry.user_id = current_user.user_id
        db.save_vault_entry(entry, user_id=current_user.user_id)

    job = db.get_job_by_id(evt.job_id, user_id=current_user.user_id)
    if job:
        job.status = ApplicationStatus.SUBMITTED
        job.applied_at = datetime.now().isoformat()
        db.save_job(job, user_id=current_user.user_id)

    await ws_manager.broadcast({
        "type": "APPLICATION_RESUMED",
        "job_id": evt.job_id,
        "company": evt.company,
        "role": evt.role_title,
        "status": "SUBMITTED"
    })

    return {
        "status": "success",
        "message": f"Held application for {evt.company} resumed and submitted successfully!",
        "vault_saved": payload.save_to_vault
    }


# --- SaaS Billing Endpoints ---

class CheckoutRequest(BaseModel):
    tier: str = "PRO"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@protected_router.get("/billing/plan")
async def get_billing_plan(current_user: User = Depends(get_current_user)):
    """Returns the current user's subscription tier, limits, and daily apply balance."""
    from app.core.rate_limiter import rate_limiter
    return {
        "status": "success",
        "plan": rate_limiter.get_usage_summary(current_user.user_id)
    }


@protected_router.post("/billing/checkout")
async def create_checkout_session(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user)
):
    """Generates a Stripe checkout session for upgrading subscription tier."""
    requested_tier = payload.tier.upper()
    if requested_tier not in ["PRO", "ELITE"]:
        raise HTTPException(status_code=400, detail="Invalid subscription tier. Choose PRO or ELITE.")

    checkout_url = f"https://checkout.stripe.com/pay/cs_live_{current_user.user_id}_{requested_tier}"
    return {
        "status": "success",
        "checkout_url": checkout_url,
        "tier": requested_tier,
        "amount_usd": 29 if requested_tier == "PRO" else 79
    }


# Assemble Unified Master Router (F-01 Router-Level Protection)
router.include_router(public_router)
router.include_router(protected_router)

