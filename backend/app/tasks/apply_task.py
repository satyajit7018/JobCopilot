"""
JobCopilot - Asynchronous Application Task Runner
Handles parallel execution of Playwright job submissions via Celery / Local Runner,
with distributed trace propagation across worker tasks.
"""

import asyncio
from typing import Any, Dict, Optional

from app.bot.runner import AutonomousJobRunner
from app.core.telemetry import SpanContext, telemetry
from app.tasks.celery_app import USE_CELERY, celery_app, local_task_runner


async def run_apply_job_async(
    user_id: str,
    job_id: str,
    submission_mode: str = "DRY_RUN",
    trace_parent: Optional[str] = None,
    ledger_id: Optional[str] = None
) -> Dict[str, Any]:
    """Runs one application with the real runner API (audit P1-1).

    Used directly by the in-process runner, which already owns an event loop.
    """
    import functools

    from app.api.ws_gateway import ws_manager

    parent_ctx = SpanContext.from_traceparent(trace_parent) if trace_parent else None
    with telemetry.start_span(
        "task.apply",
        parent_context=parent_ctx,
        attributes={"user.id": user_id, "job.id": job_id, "submission_mode": submission_mode}
    ) as span:
        runner = AutonomousJobRunner(mode=submission_mode)
        res = await runner.execute_application(
            job_id=job_id,
            user_id=user_id,
            ws_broadcast_callback=functools.partial(ws_manager.broadcast, user_id=user_id),
            ledger_id=ledger_id,
        )
        span.set_attribute("task.status", res.get("status", "unknown"))
        return res


def run_apply_job_sync(
    user_id: str,
    job_id: str,
    submission_mode: str = "DRY_RUN",
    trace_parent: Optional[str] = None,
    ledger_id: Optional[str] = None
) -> Dict[str, Any]:
    """Celery worker entry point: worker processes have no running loop, so start one."""
    return asyncio.run(run_apply_job_async(user_id, job_id, submission_mode, trace_parent, ledger_id))


if celery_app and USE_CELERY:
    # No automatic retries: re-running a live application can submit twice. Failures are
    # recorded in the apply ledger and retried deliberately by the user.
    @celery_app.task(bind=True, name="jobcopilot.normal.run_apply_job", max_retries=0)
    def run_apply_job_celery(
        self,
        user_id: str,
        job_id: str,
        submission_mode: str = "DRY_RUN",
        trace_parent: Optional[str] = None,
        ledger_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return run_apply_job_sync(user_id, job_id, submission_mode, trace_parent, ledger_id)


def enqueue_apply_job(
    user_id: str,
    job_id: str,
    submission_mode: str = "DRY_RUN",
    trace_parent: Optional[str] = None,
    ledger_id: Optional[str] = None
) -> str:
    """Dispatches the application to Celery or the in-process runner. Returns the task id."""
    if not trace_parent:
        current_span = telemetry.get_current_span()
        if current_span:
            trace_parent = current_span.context.to_traceparent()

    if celery_app and USE_CELERY:
        task = run_apply_job_celery.delay(user_id, job_id, submission_mode, trace_parent, ledger_id)
        return str(task.id)
    return local_task_runner.enqueue(
        "run_apply_job",
        run_apply_job_async,
        user_id,
        job_id,
        submission_mode,
        user_id=user_id,       # consumed by enqueue for tenant ownership, not passed to the task
        max_retries=0,         # never auto-retry a job application
        trace_parent=trace_parent,
        ledger_id=ledger_id
    )
