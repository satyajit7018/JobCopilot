"""
JobCopilot - Atomic Form State Checkpointing & Resume Engine
Persists progress and filled inputs at every page transition, enabling
fault-tolerant auto-recovery without re-filling forms.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from app.core.models import JobCheckpoint
from app.core.database import db


class CheckpointManager:
    """Manages atomic application form state snapshots in SQLite."""

    @classmethod
    def save_step(
        cls,
        job_id: str,
        current_step: int,
        total_steps: int,
        filled_inputs: Dict[str, Any],
        last_url: str,
        screenshot_path: Optional[str] = None
    ) -> JobCheckpoint:
        """Saves current form state and filled inputs."""
        checkpoint = JobCheckpoint(
            job_id=job_id,
            current_step=current_step,
            total_steps=total_steps,
            filled_inputs=filled_inputs,
            last_url=last_url,
            screenshot_path=screenshot_path,
            updated_at=datetime.now().isoformat()
        )
        db.save_checkpoint(checkpoint)
        return checkpoint

    @classmethod
    def get_step(cls, job_id: str) -> Optional[JobCheckpoint]:
        """Retrieves last saved form checkpoint for a job."""
        return db.get_checkpoint(job_id)

    @classmethod
    def clear(cls, job_id: str):
        """Cleans up checkpoint after successful submission."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM job_checkpoints WHERE job_id = ?", (job_id,))
            conn.commit()
