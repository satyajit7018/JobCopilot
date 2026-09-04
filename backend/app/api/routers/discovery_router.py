"""
JobCopilot - 0-Day Job Discovery Router
Handles autonomous multi-source job discovery triggers and live status querying.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from app.core.models import User
from app.core.database import db
from app.discovery.orchestrator import discovery_orchestrator
from app.api.auth import get_current_user
from app.api.ws_gateway import ws_manager

router = APIRouter(tags=["discovery"])


@router.post("/discovery/run")
async def run_discovery(
    profile_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Triggers an async 0-day job discovery cycle across ATS APIs and VC boards."""
    profile = db.get_profile(user_id=current_user.user_id, profile_id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found.")

    await ws_manager.broadcast({"type": "BOT_LOG", "message": "Starting 0-day multi-source job discovery cycle..."}, user_id=current_user.user_id)

    result = await discovery_orchestrator.run_discovery_cycle(profile, user_id=current_user.user_id)

    await ws_manager.broadcast({
        "type": "DISCOVERY_COMPLETED",
        "total_sourced": result.get("total_sourced", 0),
        "matched_and_saved": result.get("matched_and_saved", 0)
    }, user_id=current_user.user_id)

    return result


@router.get("/discovery/status")
async def get_discovery_status(current_user: User = Depends(get_current_user)):
    """Returns current discovery metrics."""
    return {
        "is_running": discovery_orchestrator.is_running,
        "last_run_at": discovery_orchestrator.last_run_at,
        "total_discovered": discovery_orchestrator.total_discovered,
        "total_matched": discovery_orchestrator.total_matched
    }
