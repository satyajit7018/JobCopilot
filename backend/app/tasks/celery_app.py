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
                },
                task_serializer="json",
                result_serializer="json",
                accept_content=["json"],
                timezone="UTC",
                enable_utc=True,
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
    """Async in-memory task runner for zero-dependency execution and testing."""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def enqueue(self, task_name: str, func: Callable, *args, **kwargs) -> str:
        import uuid
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "task_id": task_id,
            "task_name": task_name,
            "status": "QUEUED",
            "result": None,
            "error": None
        }

        async def _run():
            self.tasks[task_id]["status"] = "RUNNING"
            try:
                if asyncio.iscoroutinefunction(func):
                    res = await func(*args, **kwargs)
                else:
                    res = func(*args, **kwargs)
                self.tasks[task_id]["status"] = "COMPLETED"
                self.tasks[task_id]["result"] = res
            except Exception as ex:
                self.tasks[task_id]["status"] = "FAILED"
                self.tasks[task_id]["error"] = str(ex)

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                asyncio.create_task(_run())
            else:
                asyncio.run(_run())
        except Exception:
            # Fallback sync
            try:
                res = func(*args, **kwargs)
                self.tasks[task_id]["status"] = "COMPLETED"
                self.tasks[task_id]["result"] = res
            except Exception as ex:
                self.tasks[task_id]["status"] = "FAILED"
                self.tasks[task_id]["error"] = str(ex)

        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(task_id)


local_task_runner = LocalTaskRunner()
