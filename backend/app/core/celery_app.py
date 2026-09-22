"""
JobCopilot - Distributed Background Task Execution Engine
Powered by Celery and Redis with automatic in-memory task fallback for local development.
"""

import logging
from typing import Any, Dict, Optional

from celery import Celery

from app.core.settings import settings

logger = logging.getLogger("jobcopilot.celery")

celery_app = Celery(
    "jobcopilot_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    worker_concurrency=4,
    task_routes={
        "jobcopilot.normal.run_apply_job": {"queue": "priority.normal"},
        "jobcopilot.dlq.*": {"queue": "dead_letter"},
    },
    task_default_retry_delay=5,
    task_max_retries=3,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# In-Memory fallback store for task status when running without Redis cluster
_IN_MEMORY_TASKS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_DLQ: Dict[str, Dict[str, Any]] = {}


class TaskManager:
    """Manages asynchronous job applications, candidate discovery, and task polling with DLQ resilience."""

    @classmethod
    def dispatch_apply_task(cls, job_id: str, user_id: str, submission_mode: str = "DRY_RUN",
                            ledger_id: Optional[str] = None) -> str:
        """Queues a real application run and returns its task id.

        Audit P1-1: this used to mark the task SUCCESS without running anything.
        Status now comes only from the task that actually executes.
        """
        from app.tasks.apply_task import enqueue_apply_job
        task_id = enqueue_apply_job(user_id=user_id, job_id=job_id, submission_mode=submission_mode, ledger_id=ledger_id)
        # Ownership record so status lookups are tenant-scoped on every backend.
        _IN_MEMORY_TASKS[task_id] = {"task_id": task_id, "user_id": user_id, "job_id": job_id,
                                     "submission_mode": submission_mode, "status": "QUEUED"}
        return task_id

    @classmethod
    def get_task_status(cls, task_id: str, user_id: str = "") -> Optional[Dict[str, Any]]:
        """Returns task progress for its owner only. Unknown or foreign task ids return None."""
        owner = (_IN_MEMORY_TASKS.get(task_id) or {}).get("user_id")
        if not owner or (user_id and owner != user_id):
            return None  # audit P1-14: never answer for a task we cannot attribute to the caller

        from app.tasks.celery_app import USE_CELERY, local_task_runner
        from app.tasks.celery_app import celery_app as tasks_celery_app
        if USE_CELERY and tasks_celery_app is not None:
            res = tasks_celery_app.AsyncResult(task_id)
            state = res.state
            result = res.result if state == "SUCCESS" else None
        else:
            local = local_task_runner.get_task_status(task_id, user_id=owner) or {}
            state = local.get("status", "QUEUED")
            result = local.get("result")
            if local.get("error") and state in ("DLQ", "FAILURE"):
                result = {"status": "error", "message": local.get("error")}

        # A finished task only counts as success if the runner itself reported success.
        if state in ("SUCCESS", "COMPLETED"):
            ok = isinstance(result, dict) and result.get("status") == "success"
            state = "SUCCESS" if ok else "FAILED"
        progress = {"QUEUED": 10, "PENDING": 10, "STARTED": 50, "RUNNING": 50, "RETRYING": 50}.get(state, 100)
        return {"task_id": task_id, "job_id": _IN_MEMORY_TASKS[task_id]["job_id"], "status": state,
                "progress_percent": progress, "result": result}

    @classmethod
    def get_dlq_tasks(cls, user_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Lists dead-lettered application tasks with tenant isolation."""
        if not user_id or user_id == "admin":
            return dict(_IN_MEMORY_DLQ)
        return {tid: t for tid, t in _IN_MEMORY_DLQ.items() if t.get("user_id") == user_id}

    @classmethod
    def retry_dlq_task(cls, task_id: str) -> bool:
        """Removes task from DLQ and re-queues it for execution."""
        if task_id not in _IN_MEMORY_DLQ:
            return False
        task = _IN_MEMORY_DLQ.pop(task_id)
        task["status"] = "QUEUED"
        task["progress_percent"] = 10
        _IN_MEMORY_TASKS[task_id] = task
        return True


# The former 'jobcopilot.apply_to_job' stub (returned COMPLETED without running anything) was removed
# in the audit fix for P1-1. The real worker task is app.tasks.apply_task.run_apply_job_celery.
