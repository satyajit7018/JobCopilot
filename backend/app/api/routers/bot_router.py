"""
JobCopilot - Autonomous Bot & HITL Router
Handles synchronous and asynchronous stealth bot applications, background worker tasks,
and human-in-the-loop (HITL) novel question resolution.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.config import DEFAULT_SUBMISSION_MODE
from app.core.models import User, ApplicationStatus, ApplyLedgerStatus, ApplyLedgerEntry
from app.core.database import db
from app.core.vector_vault import vault
from app.bot.apply_ledger import apply_ledger
from app.api.auth import get_current_user
from app.api.ws_gateway import ws_manager

router = APIRouter(tags=["bot"])


class HITLResolveRequest(BaseModel):
    event_id: str
    user_answer: str
    save_to_vault: bool = True


class ResolveHeldApplicationRequest(BaseModel):
    event_id: str
    user_answer: str
    save_to_vault: bool = True


@router.get("/hitl/pending")
async def get_pending_hitl(current_user: User = Depends(get_current_user)):
    """Returns all pending HITL questions for authenticated tenant."""
    events = db.get_pending_hitl(user_id=current_user.user_id)
    return {
        "count": len(events),
        "events": [e.dict() for e in events]
    }


@router.post("/hitl/resolve")
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


@router.post("/hitl/resolve-held")
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


@router.post("/bot/apply/{job_id}")
async def apply_to_job(
    job_id: str,
    profile_id: Optional[str] = None,
    mode: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Executes full autonomous stealth application workflow with persistent rate limiting and idempotency."""
    # Check Idempotent Apply Ledger before executing
    existing_ledger = apply_ledger.get_ledger_for_job(current_user.user_id, job_id)
    if existing_ledger:
        if existing_ledger.status == ApplyLedgerStatus.SUBMITTED:
            raise HTTPException(status_code=409, detail=f"Application already submitted on {existing_ledger.updated_at}.")
        if existing_ledger.status == ApplyLedgerStatus.IN_PROGRESS:
            raise HTTPException(status_code=409, detail="Application is currently actively executing.")

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
    if result.get("status") == "conflict":
        raise HTTPException(status_code=409, detail=result.get("message", "Application blocked by idempotency ledger."))
    if result.get("status") == "success":
        rate_limiter.record_apply(current_user.user_id)
    return result


@router.post("/jobs/apply-async/{job_id}", status_code=202)
@router.post("/bot/apply-async/{job_id}", status_code=202)
async def apply_to_job_async(
    job_id: str,
    mode: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Dispatches asynchronous application task to Celery/Redis background worker queue with idempotency checks.
    Returns HTTP 202 Accepted with a unique task_id for progress polling.
    """
    # Check Idempotent Apply Ledger
    existing_ledger = apply_ledger.get_ledger_for_job(current_user.user_id, job_id)
    if existing_ledger:
        if existing_ledger.status == ApplyLedgerStatus.SUBMITTED:
            raise HTTPException(status_code=409, detail=f"Application already submitted on {existing_ledger.updated_at}.")
        if existing_ledger.status == ApplyLedgerStatus.IN_PROGRESS:
            raise HTTPException(status_code=409, detail="Application is currently actively executing.")

    from app.core.rate_limiter import rate_limiter
    from app.core.celery_app import TaskManager

    if not rate_limiter.can_apply(current_user.user_id):
        raise HTTPException(
            status_code=429,
            detail="Daily application limit reached for your plan. Please upgrade to Pro or Elite to continue applying."
        )

    task_id = TaskManager.dispatch_apply_task(
        job_id=job_id,
        user_id=current_user.user_id,
        submission_mode=mode or DEFAULT_SUBMISSION_MODE
    )

    rate_limiter.record_apply(current_user.user_id)

    return {
        "status": "ACCEPTED",
        "task_id": task_id,
        "job_id": job_id,
        "poll_url": f"/api/tasks/{task_id}",
        "message": "Application task queued successfully. Poll poll_url for progress."
    }


@router.get("/tasks/{task_id}")
async def get_task_status_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Polls progress and completion status for an asynchronous background task."""
    from app.core.celery_app import TaskManager
    task_info = TaskManager.get_task_status(task_id, user_id=current_user.user_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found or access denied.")
    return {
        "status": "success",
        "task": task_info
    }


@router.get("/bot/ledger")
async def get_apply_ledger(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Returns paginated application audit ledger history for authenticated tenant."""
    entries = apply_ledger.list_user_ledger(user_id=current_user.user_id, limit=limit, offset=offset, status=status)
    return {
        "count": len(entries),
        "limit": limit,
        "offset": offset,
        "entries": [e.dict() for e in entries]
    }


@router.get("/bot/ledger/{job_id}")
async def get_job_ledger(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """Retrieves apply ledger entry for a specific job."""
    entry = apply_ledger.get_ledger_for_job(user_id=current_user.user_id, job_id=job_id)
    if not entry:
        raise HTTPException(status_code=404, detail="No ledger record found for this job.")
    return {
        "status": "success",
        "ledger": entry.dict()
    }


@router.get("/hitl/{event_id}/evidence")
async def get_hitl_evidence(
    event_id: str,
    current_user: User = Depends(get_current_user)
):
    """Returns visual evidence (screenshot path, DOM snapshot, field selector) for a HITL challenge."""
    evt = db.get_hitl_event(event_id, user_id=current_user.user_id)
    if not evt:
        raise HTTPException(status_code=404, detail="HITL event not found.")
    return {
        "status": "success",
        "event_id": evt.event_id,
        "input_type": evt.input_type,
        "screenshot_path": evt.screenshot_path,
        "dom_snapshot": evt.dom_snapshot,
        "field_selector": evt.field_selector
    }
