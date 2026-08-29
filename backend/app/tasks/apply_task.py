"""
JobCopilot - Asynchronous Application Task Runner
Handles parallel execution of Playwright job submissions via Celery / Local Runner.
"""

import asyncio
from typing import Dict, Any, Optional
from app.tasks.celery_app import celery_app, local_task_runner, USE_CELERY
from app.bot.runner import AutonomousJobRunner
from app.core.database import db


def run_apply_job_sync(user_id: str, job_id: str, submission_mode: str = "DRY_RUN") -> Dict[str, Any]:
    """Synchronous core runner invoked by worker."""
    runner = AutonomousJobRunner(user_id=user_id, submission_mode=submission_mode)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        res = loop.run_until_complete(runner.apply_to_job(job_id))
        return res
    finally:
        loop.close()


if celery_app and USE_CELERY:
    @celery_app.task(bind=True, name="jobcopilot.normal.run_apply_job", max_retries=3)
    def run_apply_job_celery(self, user_id: str, job_id: str, submission_mode: str = "DRY_RUN") -> Dict[str, Any]:
        return run_apply_job_sync(user_id, job_id, submission_mode)


def enqueue_apply_job(user_id: str, job_id: str, submission_mode: str = "DRY_RUN") -> str:
    """Dispatches application task to Celery or Local Async Task Runner."""
    if celery_app and USE_CELERY:
        task = run_apply_job_celery.delay(user_id, job_id, submission_mode)
        return str(task.id)
    else:
        return local_task_runner.enqueue(
            "run_apply_job",
            run_apply_job_sync,
            user_id,
            job_id,
            submission_mode
        )
