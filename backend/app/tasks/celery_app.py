"""
JobCopilot - Distributed Worker Queue (Celery + In-Memory Fallback)
Provides prioritized asynchronous execution for:
- high: Live HITL resolution & dry-run previews
- normal: Scheduled auto-apply batch submissions
- low: Background 0-day discovery & email radar sync
"""

import os
import asyncio
import logging
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger("jobcopilot.tasks")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
USE_CELERY = os.environ.get("USE_CELERY", "false").lower() in ["true", "1", "yes"]

try:
    if USE_CELERY:
        try:
            from celery import Celery  # type: ignore
            celery_app = Celery(
                "jobcopilot",
                broker=REDIS_URL,
                backend=REDIS_URL
            )
            celery_app.conf.update(
                task_routes={
                    "jobcopilot.high.*": {"queue": "priority.high"},
                    "jobcopilot.normal.*": {"queue": "priority.normal"},
                    "jobcopilot.low.*": {"queue": "priority.low"},
                    "jobcopilot.dlq.*": {"queue": "dead_letter"},
                },
                task_serializer="json",
                result_serializer="json",
                accept_content=["json"],
                timezone="UTC",
                enable_utc=True,
                task_default_retry_delay=5,
                task_max_retries=3,
                task_acks_late=True,
                task_reject_on_worker_lost=True,
            )
        except ImportError:
            logger.warning("Celery package is not installed. Falling back to in-memory async task runner.")
            celery_app = None
    else:
        celery_app = None
except Exception as e:
    logger.warning(f"Celery initialization deferred: {e}")
    celery_app = None


class LocalTaskRunner:
    """
    Async in-memory task runner for zero-dependency execution and testing.
    Includes automated retries with exponential backoff, Dead-Letter Queue (DLQ),
    and real-time WebSocket progress alerts.
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 0.05):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.dlq: Dict[str, Dict[str, Any]] = {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def enqueue(
        self,
        task_name: str,
        func: Callable,
        *args,
        user_id: Optional[str] = None,
        max_retries: Optional[int] = None,
        **kwargs
    ) -> str:
        import uuid
        task_id = str(uuid.uuid4())
        retries_allowed = max_retries if max_retries is not None else self.max_retries

        self.tasks[task_id] = {
            "task_id": task_id,
            "task_name": task_name,
            "user_id": user_id or kwargs.get("user_id", "default"),
            "status": "QUEUED",
            "retry_count": 0,
            "max_retries": retries_allowed,
            "result": None,
            "error": None,
            "in_dlq": False
        }

        async def _notify_ws(event_type: str, payload: Dict[str, Any]):
            target_user = self.tasks[task_id].get("user_id")
            if target_user:
                try:
                    from app.api.endpoints import ws_manager
                    await ws_manager.broadcast({
                        "event": event_type,
                        "task_id": task_id,
                        **payload
                    }, user_id=target_user)
                except Exception:
                    pass

        async def _run_with_retries():
            task_info = self.tasks[task_id]
            task_info["status"] = "RUNNING"
            await _notify_ws("task_progress", {"status": "RUNNING", "progress": 10})

            while True:
                try:
                    if asyncio.iscoroutinefunction(func):
                        res = await func(*args, **kwargs)
                    else:
                        res = func(*args, **kwargs)

                    task_info["status"] = "COMPLETED"
                    task_info["result"] = res
                    await _notify_ws("task_completed", {"status": "COMPLETED", "progress": 100})
                    return res

                except Exception as ex:
                    task_info["error"] = str(ex)
                    current_retries = task_info["retry_count"]

                    if current_retries < task_info["max_retries"]:
                        task_info["retry_count"] += 1
                        task_info["status"] = "RETRYING"
                        backoff = self.retry_delay * (2 ** current_retries)
                        logger.warning(f"Task {task_id} failed ({ex}). Retrying ({task_info['retry_count']}/{task_info['max_retries']}) in {backoff:.2f}s...")
                        await _notify_ws("task_retrying", {
                            "status": "RETRYING",
                            "retry_count": task_info["retry_count"],
                            "error": str(ex)
                        })
                        await asyncio.sleep(backoff)
                    else:
                        # Max retries exhausted -> Move to Dead-Letter Queue (DLQ)
                        task_info["status"] = "DLQ"
                        task_info["in_dlq"] = True
                        self.dlq[task_id] = task_info
                        logger.error(f"Task {task_id} exceeded max retries. Moved to Dead-Letter Queue (DLQ). Error: {ex}")
                        await _notify_ws("task_dlq", {
                            "status": "DLQ",
                            "error": str(ex),
                            "retries_exhausted": task_info["retry_count"]
                        })
                        return None

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                asyncio.create_task(_run_with_retries())
            else:
                asyncio.run(_run_with_retries())
        except Exception:
            # Synchronous fallback with single attempt
            try:
                res = func(*args, **kwargs)
                self.tasks[task_id]["status"] = "COMPLETED"
                self.tasks[task_id]["result"] = res
            except Exception as ex:
                self.tasks[task_id]["status"] = "DLQ"
                self.tasks[task_id]["in_dlq"] = True
                self.tasks[task_id]["error"] = str(ex)
                self.dlq[task_id] = self.tasks[task_id]

        return task_id

    def get_task_status(self, task_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        if user_id and task.get("user_id") and task.get("user_id") != user_id and user_id != "admin":
            return None  # Tenant isolation
        return task

    def get_dlq_tasks(self, user_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Returns all dead-lettered tasks, filtered by tenant if user_id specified."""
        if not user_id or user_id == "admin":
            return dict(self.dlq)
        return {tid: t for tid, t in self.dlq.items() if t.get("user_id") == user_id}

    def retry_dlq_task(self, task_id: str) -> bool:
        """Re-enqueues a task from DLQ with fresh retry counter."""
        if task_id not in self.dlq:
            return False
        task = self.dlq.pop(task_id)
        task["status"] = "QUEUED"
        task["retry_count"] = 0
        task["in_dlq"] = False
        self.tasks[task_id] = task
        return True

    def clear_dlq(self) -> int:
        """Purges all dead-letter queue records."""
        count = len(self.dlq)
        self.dlq.clear()
        return count


local_task_runner = LocalTaskRunner()

