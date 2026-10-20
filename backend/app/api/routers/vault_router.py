"""
JobCopilot - Knowledge Vault Router
Handles semantic vector Q&A indexing, manual learning, and real-time screening question resolution.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.core.database import db
from app.core.models import User
from app.core.vector_vault import vault

router = APIRouter(tags=["vault"])


class VaultLearnRequest(BaseModel):
    question: str
    answer: str
    slot_type: Optional[str] = None
    slot_key: Optional[str] = None


@router.get("/vault")
async def get_vault_entries(current_user: User = Depends(get_current_user)):
    """Returns all indexed Q&A slots for the authenticated tenant."""
    entries = db.get_vault_entries(user_id=current_user.user_id)
    return {
        "count": len(entries),
        "entries": [e.dict() for e in entries]
    }


@router.post("/vault/learn")
async def learn_vault_entry(
    payload: VaultLearnRequest,
    current_user: User = Depends(get_current_user)
):
    """Manually teaches or updates a Q&A slot."""
    entry = vault.learn_answer(
        question=payload.question,
        answer_template=payload.answer,
        slot_type=payload.slot_type,
        slot_key=payload.slot_key,
        user_id=current_user.user_id,
    )
    return {"status": "success", "entry": entry.dict()}

