"""
JobCopilot - Feedback sent from the app.

Stored per user (deleted with the account) and read by admins on the Admin page.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.auth import get_current_user, limiter, require_admin
from app.core.database import db
from app.core.models import User

router = APIRouter(tags=["support"])


class FeedbackRequest(BaseModel):
    message: str = Field(min_length=3, max_length=4000)
    page: Optional[str] = Field(default=None, max_length=200)


@router.post("/feedback", status_code=201)
@limiter.limit("5/minute")
async def send_feedback(request: Request, payload: FeedbackRequest, current_user: User = Depends(get_current_user)):
    page = (payload.page or "").split("?")[0] or None
    feedback_id = db.save_feedback(current_user.user_id, payload.message.strip(), page)
    return {"status": "received", "feedback_id": feedback_id}


@router.get("/admin/feedback")
async def list_feedback(limit: int = 50, offset: int = 0, admin_user: User = Depends(require_admin)):
    limit = max(1, min(limit, 200))
    return {"feedback": db.list_feedback(limit=limit, offset=max(0, offset))}
