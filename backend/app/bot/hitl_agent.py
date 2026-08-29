"""
JobCopilot - Human-In-The-Loop (HITL) Alert Trigger & Self-Learning Resolver
Dispatches real-time alerts when low-confidence recruiter questions or CAPTCHAs
are encountered, blocks gracefully, saves answers to the Knowledge Vault, and resumes.
"""

import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.core.models import HITLEvent
from app.core.database import db
from app.core.vector_vault import vault


class HITLAgent:
    """Manages Human-In-The-Loop lifecycle for autonomous application workflows."""

    @classmethod
    async def request_human_input(
        cls,
        job_id: str,
        company: str,
        role_title: str,
        question_text: str,
        input_type: str = "text",
        options: Optional[List[str]] = None,
        ai_suggested_draft: str = "",
        ws_broadcast_callback = None
    ) -> HITLEvent:
        """Creates a pending HITL event in SQLite and broadcasts via WebSocket."""
        event_id = f"hitl_{uuid.uuid4().hex[:8]}"
        event = HITLEvent(
            event_id=event_id,
            job_id=job_id,
            company=company,
            role_title=role_title,
            question_text=question_text,
            input_type=input_type,
            options=options or [],
            ai_suggested_draft=ai_suggested_draft,
            status="PENDING",
            created_at=datetime.now().isoformat()
        )
        db.save_hitl_event(event)

        if ws_broadcast_callback:
            try:
                await ws_broadcast_callback({
                    "type": "HITL_REQUIRED",
                    "event": event.dict()
                })
            except Exception:
                pass

        return event

    @classmethod
    async def wait_for_resolution(
        cls,
        event_id: str,
        poll_interval: float = 0.5,
        max_timeout: float = 300.0
    ) -> Optional[str]:
        """Polls database until user resolves the HITL event in the UI modal."""
        elapsed = 0.0
        while elapsed < max_timeout:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT status, user_answer, question_text FROM hitl_events WHERE event_id = ?", (event_id,))
                row = cursor.fetchone()
                if row and row["status"] == "RESOLVED" and row["user_answer"]:
                    user_ans = row["user_answer"]
                    # Automatically index into Knowledge Vault permanently
                    vault.learn_answer(
                        question=row["question_text"],
                        answer_template=user_ans
                    )
                    return user_ans
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return None
