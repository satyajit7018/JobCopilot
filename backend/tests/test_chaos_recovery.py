"""
Chaos Engineering and Failure Recovery Tests for JobCopilot Task Workers
Simulates worker failures, transient network partitions, retry backoff exhaustion,
Dead-Letter Queue (DLQ) evacuation, and manual/automated re-enqueue recovery.
"""

import pytest
import asyncio
from app.tasks.celery_app import LocalTaskRunner


@pytest.mark.asyncio
async def test_worker_transient_failure_and_retry_recovery():
    """Simulates transient worker failure that recovers after 2 retries."""
    runner = LocalTaskRunner(max_retries=3, retry_delay=0.01)
    attempt_counter = 0

    def unreliable_task():
        nonlocal attempt_counter
        attempt_counter += 1
        if attempt_counter < 3:
            raise ConnectionResetError("Transient network partition simulating worker failure")
        return {"status": "SUCCESS", "attempts": attempt_counter}

    task_id = runner.enqueue("unreliable_task", unreliable_task, user_id="tenant_alpha")
    assert task_id in runner.tasks

    # Wait for retries to complete
    await asyncio.sleep(0.1)

    task_state = runner.get_task_status(task_id, user_id="tenant_alpha")
    assert task_state is not None
    assert task_state["status"] == "COMPLETED"
    assert task_state["retry_count"] == 2
    assert task_state["result"]["status"] == "SUCCESS"
    assert task_state["in_dlq"] is False


@pytest.mark.asyncio
async def test_worker_fatal_failure_exhaustion_moves_to_dlq():
    """Simulates persistent worker crash that exhausts all retries and transitions to DLQ."""
    runner = LocalTaskRunner(max_retries=2, retry_delay=0.01)

    def crashing_task():
        raise RuntimeError("Fatal process fault simulating unrecoverable task failure")

    task_id = runner.enqueue("crashing_task", crashing_task, user_id="tenant_beta")
    await asyncio.sleep(0.1)

    task_state = runner.get_task_status(task_id, user_id="tenant_beta")
    assert task_state is not None
    assert task_state["status"] == "DLQ"
    assert task_state["in_dlq"] is True
    assert task_state["retry_count"] == 2

    # Verify task exists in Dead-Letter Queue
    dlq_tasks = runner.get_dlq_tasks(user_id="tenant_beta")
    assert task_id in dlq_tasks
    assert "Fatal process fault" in dlq_tasks[task_id]["error"]


@pytest.mark.asyncio
async def test_dlq_retry_and_recovery_mechanism():
    """Simulates operator or automated workflow re-enqueuing a dead-lettered task."""
    runner = LocalTaskRunner(max_retries=1, retry_delay=0.01)

    def failing_task():
        raise ValueError("Simulated fault")

    task_id = runner.enqueue("failing_task", failing_task, user_id="tenant_gamma")
    await asyncio.sleep(0.05)

    assert task_id in runner.dlq

    # Recover task from DLQ
    re_enqueued = runner.retry_dlq_task(task_id)
    assert re_enqueued is True
    assert task_id not in runner.dlq

    # Verify state reset for re-execution
    task_state = runner.get_task_status(task_id, user_id="tenant_gamma")
    assert task_state["status"] == "QUEUED"
    assert task_state["retry_count"] == 0
    assert task_state["in_dlq"] is False

    # Purge DLQ
    runner.dlq["dummy_id"] = {"error": "stale"}
    purged_count = runner.clear_dlq()
    assert purged_count == 1
    assert len(runner.dlq) == 0


@pytest.mark.asyncio
async def test_dlq_tenant_isolation():
    """Validates that tenants cannot inspect each other's Dead-Letter Queue records."""
    runner = LocalTaskRunner(max_retries=1, retry_delay=0.01)

    runner.dlq["task_alpha"] = {"user_id": "user_1", "error": "err1"}
    runner.dlq["task_beta"] = {"user_id": "user_2", "error": "err2"}

    # User 1 only sees their DLQ tasks
    user1_dlq = runner.get_dlq_tasks(user_id="user_1")
    assert "task_alpha" in user1_dlq
    assert "task_beta" not in user1_dlq

    # User 2 only sees their DLQ tasks
    user2_dlq = runner.get_dlq_tasks(user_id="user_2")
    assert "task_beta" in user2_dlq
    assert "task_alpha" not in user2_dlq

    # Admin sees all DLQ tasks
    admin_dlq = runner.get_dlq_tasks(user_id="admin")
    assert "task_alpha" in admin_dlq
    assert "task_beta" in admin_dlq
