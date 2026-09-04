"""
JobCopilot - Recruiter Email Inbound & Sync Router
Handles webhook ingestion, inbound recruiter email parsing, communications history,
and automated follow-up drafts.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from app.core.models import User
from app.core.database import db
from app.api.auth import get_current_user
from app.api.ws_gateway import ws_manager

router = APIRouter(tags=["email"])


class InboundEmailPayload(BaseModel):
    sender: str
    recipient: str = "candidate@jobcopilot.local"
    subject: str
    body_html: str
    body_text: Optional[str] = None


@router.post("/email/inbound-webhook")
async def receive_inbound_email_webhook(request: Request):
    """
    Public webhook receiver for external email providers (Postmark, SendGrid, Mailgun).
    Verifies HMAC-SHA256 signature and attributes incoming email to tenant via subaddress.
    """
    from app.email.inbound_provider import InboundEmailProvider
    from app.email.sync import EmailSyncEngine

    body_bytes = await request.body()
    sig_header = (
        request.headers.get("X-JobCopilot-Signature")
        or request.headers.get("X-Postmark-Signature")
        or request.headers.get("X-SendGrid-Signature")
    )

    if not InboundEmailProvider.verify_webhook_signature(body_bytes, sig_header):
        raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    try:
        import json
        payload_json = json.loads(body_bytes.decode('utf-8'))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    parsed = InboundEmailProvider.parse_webhook_payload(payload_json)
    tenant_user_id = parsed["user_id"]
    if not tenant_user_id or tenant_user_id == "default":
        recipient_user = db.get_user_by_email(parsed["recipient"])
        if recipient_user:
            tenant_user_id = recipient_user.user_id

    result = await EmailSyncEngine.process_inbound_email(
        sender=parsed["sender"],
        recipient=parsed["recipient"],
        subject=parsed["subject"],
        body_html=parsed["body_html"],
        body_text=parsed["body_text"],
        user_id=tenant_user_id,
        ws_broadcast_callback=ws_manager.broadcast
    )
    return {"status": "success", "user_id": tenant_user_id, "result": result}


@router.post("/email/inbound")
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


@router.get("/email/messages")
async def list_email_messages(current_user: User = Depends(get_current_user)):
    """Returns all parsed recruiter communications for authenticated tenant."""
    emails = db.get_emails(user_id=current_user.user_id)
    return {"count": len(emails), "messages": [e.dict() for e in emails]}


@router.post("/email/followup/{job_id}")
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
