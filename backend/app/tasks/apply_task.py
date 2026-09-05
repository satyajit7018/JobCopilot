"""
JobCopilot - Asynchronous Application Task Runner
Handles parallel execution of Playwright job submissions via Celery / Local Runner,
with distributed trace propagation across worker tasks.
"""

import asyncio
from typing import Dict, Any, Optional
from app.tasks.celery_app import celery_app, local_task_runner, USE_CELERY
from app.bot.runner import AutonomousJobRunner
from app.core.database import db
from app.core.telemetry import telemetry, SpanContext


def run_apply_job_sync(
    user_id: str,
    job_id: str,
    submission_mode: str = "DRY_RUN",
    trace_parent: Optional[str] = None
) -> Dict[str, Any]:
    """Synchronous core runner invoked by worker with distributed trace span."""
    parent_ctx = SpanContext.from_traceparent(trace_parent) if trace_parent else None
    with telemetry.start_span(
        "task.apply",
        parent_context=parent_ctx,
        attributes={
            "user.id": user_id,
            "job.id": job_id,
            "submission_mode": submission_mode
        }
    ) as span:
        runner = AutonomousJobRunner(user_id=user_id, submission_mode=submission_mode)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(runner.apply_to_job(job_id))
            span.set_attribute("task.status", res.get("status", "SUCCESS"))
            return res
        except Exception as exc:
            span.record_exception(exc)
            raise
        finally:
            loop.close()


if celery_app and USE_CELERY:
    @celery_app.task(bind=True, name="jobcopilot.normal.run_apply_job", max_retries=3)
    def run_apply_job_celery(
        self,
        user_id: str,
        job_id: str,
        submission_mode: str = "DRY_RUN",
        trace_parent: Optional[str] = None
    ) -> Dict[str, Any]:
        return run_apply_job_sync(user_id, job_id, submission_mode, trace_parent)


def enqueue_apply_job(
    user_id: str,
    job_id: str,
    submission_mode: str = "DRY_RUN",
    trace_parent: Optional[str] = None
) -> str:
    """Dispatches application task to Celery or Local Async Task Runner with trace context propagation."""
    if not trace_parent:
        current_span = telemetry.get_current_span()
        if current_span:
            trace_parent = current_span.context.to_traceparent()

    if celery_app and USE_CELERY:
        task = run_apply_job_celery.delay(user_id, job_id, submission_mode, trace_parent)
        return str(task.id)
    else:
        return local_task_runner.enqueue(
            "run_apply_job",
            run_apply_job_sync,
            user_id,
            job_id,
            submission_mode,
            trace_parent=trace_parent
        )
