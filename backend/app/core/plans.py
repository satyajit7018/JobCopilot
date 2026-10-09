"""
JobCopilot - Free and Premium plans.

Free: job search, match reviews and tracking applications by hand.
Premium: everything JobCopilot does for you automatically or writes for you.
Premium is stored as the PRO role (ELITE is a legacy paid tier and counts too);
admins always have it.
"""

from typing import Callable

from fastapi import Depends, HTTPException

from app.api.auth import enum_value, get_current_user
from app.core.models import User

PREMIUM_ROLES = {"PRO", "ELITE", "ADMIN"}

# What each gated feature is called in the "Premium required" message.
PREMIUM_FEATURES = {
    "auto_apply": "Automatic applying",
    "ai_writing": "AI-tailored resumes, cover letters and emails",
    "email_tracking": "Inbox tracking",
    "interview_prep": "Interview prep",
}


def is_premium(user: User) -> bool:
    return enum_value(user.role) in PREMIUM_ROLES


def require_premium(feature: str) -> Callable[..., User]:
    """FastAPI dependency: 402 Payment Required unless the user is on Premium."""
    label = PREMIUM_FEATURES[feature]

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not is_premium(current_user):
            raise HTTPException(status_code=402, detail=f"{label} is part of Premium. Upgrade to use it.")
        return current_user

    return dependency
