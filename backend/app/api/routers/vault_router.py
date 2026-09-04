"""
JobCopilot - Knowledge Vault Router
Handles semantic vector Q&A indexing, manual learning, and real-time screening question resolution.
"""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.models import User
from app.core.database import db
from app.core.vector_vault import vault
from app.api.auth import get_current_user

router = APIRouter(tags=["vault"])


class VaultLearnRequest(BaseModel):
    question: str
    answer: str
    slot_type: Optional[str] = None
    slot_key: Optional[str] = None


class VaultTestMatchRequest(BaseModel):
    question: str
    company: str = "Stripe"
    role: str = "Senior Software Engineer"
    profile_id: Optional[str] = None


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
        slot_key=payload.slot_key
    )
    entry.user_id = current_user.user_id
    db.save_vault_entry(entry, user_id=current_user.user_id)
    return {"status": "success", "entry": entry.dict()}


@router.post("/vault/test-match")
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


class VaultSemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/vault/semantic-search")
async def semantic_search_vault(
    payload: VaultSemanticSearchRequest,
    current_user: User = Depends(get_current_user)
):
    """Ranks and returns vault entries by dense semantic vector similarity."""
    results = vault.search_semantic(
        query=payload.query,
        user_id=current_user.user_id,
        top_k=payload.top_k
    )
    formatted = []
    for entry, score in results:
        formatted.append({
            "qa_id": entry.qa_id,
            "question_pattern": entry.question_pattern,
            "answer_template": entry.answer_template,
            "slot_key": entry.slot_key,
            "slot_type": entry.slot_type.value if hasattr(entry.slot_type, "value") else str(entry.slot_type),
            "similarity_score": round(score, 4)
        })
    return {
        "status": "success",
        "query": payload.query,
        "count": len(formatted),
        "results": formatted
    }
