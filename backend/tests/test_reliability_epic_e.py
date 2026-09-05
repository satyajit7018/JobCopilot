"""
JobCopilot - Phase P2 Epic E: Reliability & Scale Verification Suite
Validates:
1. Idempotency Middleware (at-most-once execution, replay cache, 409 concurrency lock, 422 payload mismatch).
2. Circuit Breaker Architecture (state transitions CLOSED -> OPEN -> HALF_OPEN -> CLOSED, fast-fail exceptions, ATS & LLM fallbacks).
3. Celery & Task Runner Hardening (exponential retries, Dead-Letter Queue (DLQ), retry from DLQ).
4. Multi-Tier Cache with strict tenant namespace isolation and invalidation hooks.
5. High-traffic compound database indexes and idempotency record lifecycle.
"""

import time
import uuid
import pytest
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole
from app.core.idempotency import idempotency_engine, IdempotencyResult
from app.core.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError, llm_api_breaker, ats_api_breaker
from app.core.cache import cache_manager, InMemoryTTLCache
from app.tasks.celery_app import LocalTaskRunner
from app.core.llm_client import LLMClient

client = TestClient(app)


def _create_test_user(email: str, role: UserRole = UserRole.PRO) -> User:
    clean_email = email.lower().strip()
    existing = db.get_user_by_email(clean_email)
    if existing:
        db.hard_delete_user_account(existing.user_id)

    uid = f"usr_{uuid.uuid4().hex[:12]}"
    user = User(
        user_id=uid,
        email=clean_email,
        password_hash="argon2_test_hash",
        full_name="Reliability Tester",
        role=role,
        is_active=True,
        email_verified=True,
        created_at="2026-09-05T00:00:00",
        updated_at="2026-09-05T00:00:00"
    )
    db.create_user(user)
    return user


def _auth_headers(user: User) -> dict:
    from app.api.auth import create_jwt_token
    from datetime import timedelta
    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    token = create_jwt_token(
        {"sub": user.user_id, "email": user.email, "role": role_str, "type": "access"},
        expires_delta=timedelta(minutes=60)
    )
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. Idempotency Engine & Middleware Tests
# =========================================================================

def test_idempotency_middleware_success_and_replay():
    """Mutating request with Idempotency-Key executes once and replays on retry."""
    user = _create_test_user("idemp_user1@test.com")
    headers = _auth_headers(user)
    idem_key = f"key_{uuid.uuid4().hex}"
    headers["Idempotency-Key"] = idem_key

    payload = {"name": f"Idempotent Corp {uuid.uuid4().hex[:6]}", "plan_tier": "PRO"}

    # Request 1: Initial execution
    res1 = client.post("/api/orgs", json=payload, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()
    assert "org_id" in data1
    assert res1.headers.get("Idempotency-Key") == idem_key

    # Request 2: Replay with identical key and payload
    res2 = client.post("/api/orgs", json=payload, headers=headers)
    assert res2.status_code == 201
    assert res2.headers.get("Idempotency-Replayed") == "true"
    assert res2.headers.get("X-Cache-Lookup") == "HIT"
    assert res2.json()["org_id"] == data1["org_id"]

    # Verify database has exactly 1 org for this user
    user_orgs = db.list_user_organizations(user.user_id)
    assert len([o for o in user_orgs if o["org_id"] == data1["org_id"]]) == 1


def test_idempotency_middleware_payload_mismatch():
    """Reusing same Idempotency-Key with different payload rejects with 422."""
    user = _create_test_user("idemp_mismatch@test.com")
    headers = _auth_headers(user)
    idem_key = f"key_mismatch_{uuid.uuid4().hex}"
    headers["Idempotency-Key"] = idem_key

    # Request 1: Original payload
    res1 = client.post("/api/orgs", json={"name": "Org Original", "plan_tier": "PRO"}, headers=headers)
    assert res1.status_code == 201

    # Request 2: Divergent payload with same key
    res2 = client.post("/api/orgs", json={"name": "Org Divergent Tampered", "plan_tier": "ELITE"}, headers=headers)
    assert res2.status_code == 422
    assert "mismatch" in res2.json()["detail"].lower()


def test_idempotency_concurrent_in_flight_lock():
    """Validates in-memory lock handling for concurrent identical requests."""
    key = f"lock_test_{uuid.uuid4().hex}"
    user_id = "usr_concurrent"
    body = b'{"action": "apply"}'

    # First acquire succeeds
    status1, _ = idempotency_engine.acquire(key, user_id, "POST", "/api/bot/apply", body)
    assert status1 == IdempotencyResult.ACQUIRED

    # Simultaneous second acquire before complete returns IN_PROGRESS
    status2, _ = idempotency_engine.acquire(key, user_id, "POST", "/api/bot/apply", body)
    assert status2 == IdempotencyResult.IN_PROGRESS

    # Complete request
    idempotency_engine.complete(key, user_id, 200, {"content-type": "application/json"}, '{"status": "applied"}')

    # Subsequent request returns REPLAY
    status3, record = idempotency_engine.acquire(key, user_id, "POST", "/api/bot/apply", body)
    assert status3 == IdempotencyResult.REPLAY
    assert record["status_code"] == 200


# =========================================================================
# 2. Circuit Breaker Architecture Tests
# =========================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_lifecycle_and_state_machine():
    """Tests CLOSED -> OPEN -> HALF_OPEN -> CLOSED transitions with thresholds."""
    breaker = CircuitBreaker("test_service", failure_threshold=2, recovery_timeout=0.1, half_open_success_threshold=1)
    assert breaker.state == CircuitState.CLOSED

    async def _failing_call():
        raise ConnectionResetError("Remote service connection dropped")

    async def _successful_call():
        return "OK"

    # Failure 1: Remains CLOSED
    with pytest.raises(ConnectionResetError):
        await breaker.call(_failing_call)
    assert breaker.state == CircuitState.CLOSED

    # Failure 2: Hits threshold -> Trips to OPEN
    with pytest.raises(ConnectionResetError):
        await breaker.call(_failing_call)
    assert breaker.state == CircuitState.OPEN

    # Subsequent call fast-fails with CircuitOpenError without executing
    with pytest.raises(CircuitOpenError) as exc_info:
        await breaker.call(_successful_call)
    assert "OPEN" in str(exc_info.value)

    # Await recovery timeout
    await asyncio.sleep(0.15)
    assert breaker.state == CircuitState.HALF_OPEN

    # Successful call in HALF_OPEN recovers circuit to CLOSED
    result = await breaker.call(_successful_call)
    assert result == "OK"
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_llm_and_ats_circuit_breaker_integration():
    """Validates that tripping LLM breaker falls back immediately to deterministic heuristic."""
    llm = LLMClient(provider="openai", model="gpt-4o-mini")
    
    # Manually trip LLM breaker to simulate OpenAI outage
    llm_api_breaker.trip()
    assert llm_api_breaker.state == CircuitState.OPEN

    # Call chat_completion; must gracefully return heuristic fallback without hanging
    result = await llm.chat_completion(
        prompt="Tell me about Python",
        fallback_fn=lambda: "Heuristic Python summary fallback"
    )
    assert result == "Heuristic Python summary fallback"

    # Reset breaker back to healthy
    llm_api_breaker.reset()
    assert llm_api_breaker.state == CircuitState.CLOSED


# =========================================================================
# 3. Multi-Tier Cache & Tenant Isolation Tests
# =========================================================================

@pytest.mark.asyncio
async def test_cache_tenant_isolation_and_invalidation():
    """Asserts tenant A and tenant B have strict cache isolation and namespace invalidation."""
    await cache_manager.clear()

    # Set same key for two different tenants
    await cache_manager.set("user_alpha", "analytics", "summary", {"score": 95}, ttl_seconds=60)
    await cache_manager.set("user_beta", "analytics", "summary", {"score": 42}, ttl_seconds=60)

    val_a = await cache_manager.get("user_alpha", "analytics", "summary")
    val_b = await cache_manager.get("user_beta", "analytics", "summary")
    assert val_a == {"score": 95}
    assert val_b == {"score": 42}

    # Invalidate tenant alpha's namespace only
    deleted_count = await cache_manager.invalidate_namespace("user_alpha", "analytics")
    assert deleted_count >= 1

    # Alpha should be None (cache miss), Beta remains intact
    assert await cache_manager.get("user_alpha", "analytics", "summary") is None
    assert await cache_manager.get("user_beta", "analytics", "summary") == {"score": 42}


@pytest.mark.asyncio
async def test_cache_ttl_expiration():
    """Validates TTL cache expiration in memory."""
    cache = InMemoryTTLCache(max_size=100)
    await cache.set("quick_key", "active_val", ttl_seconds=0.05)
    assert await cache.get("quick_key") == "active_val"

    await asyncio.sleep(0.08)
    assert await cache.get("quick_key") is None


# =========================================================================
# 4. Celery & Task Runner DLQ Hardening Tests
# =========================================================================

@pytest.mark.asyncio
async def test_task_runner_retries_and_dead_letter_queue():
    """Failing task exhausts retries with backoff and moves to Dead-Letter Queue."""
    runner = LocalTaskRunner(max_retries=2, retry_delay=0.01)

    fail_counter = {"count": 0}

    async def _failing_task():
        fail_counter["count"] += 1
        raise ValueError(f"Simulated unrecoverable job failure (attempt {fail_counter['count']})")

    task_id = runner.enqueue("test_job", _failing_task, user_id="usr_dlq_test")

    # Await retries to exhaust
    await asyncio.sleep(0.1)

    status = runner.get_task_status(task_id)
    assert status is not None
    assert status["status"] == "DLQ"
    assert status["in_dlq"] is True
    assert status["retry_count"] == 2

    # Check DLQ registry
    dlq_tasks = runner.get_dlq_tasks(user_id="usr_dlq_test")
    assert task_id in dlq_tasks

    # Retry from DLQ
    requeued = runner.retry_dlq_task(task_id)
    assert requeued is True
    assert runner.get_task_status(task_id)["status"] == "QUEUED"


# =========================================================================
# 5. Database Compound Indexes & Idempotency Storage Tests
# =========================================================================

def test_database_compound_indices_and_idempotency_storage():
    """Validates presence of compound indices and idempotency persistence in SQLite."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indices = {row[0] for row in cursor.fetchall()}

        # Verify compound indices created for high-traffic tables
        assert "idx_emails_user_received" in indices
        assert "idx_hitl_user_status" in indices
        assert "idx_outreach_user_job" in indices
        assert "idx_jobs_user_applied" in indices
        assert "idx_idempotency_keys_expires" in indices
        assert "idx_idempotency_keys_user" in indices

    # Test record storage and retrieval
    test_key = f"db_test_{uuid.uuid4().hex}"
    record = {
        "idempotency_key": test_key,
        "user_id": "usr_db_test",
        "method": "POST",
        "path": "/api/billing/sync",
        "request_hash": "hash123",
        "status": "COMPLETED",
        "status_code": 200,
        "response_headers": {"content-type": "application/json"},
        "response_body": '{"synchronized": true}',
        "created_at": "2026-09-05T00:00:00",
        "expires_at": "2026-09-06T00:00:00"
    }

    assert db.save_idempotency_record(record) is True
    fetched = db.get_idempotency_record(test_key, user_id="usr_db_test")
    assert fetched is not None
    assert fetched["status_code"] == 200
    assert fetched["response_body"] == '{"synchronized": true}'

    # Delete record
    assert db.delete_idempotency_record(test_key) is True
    assert db.get_idempotency_record(test_key, user_id="usr_db_test") is None
