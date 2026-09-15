"""
JobCopilot - Apply Path Idempotency & Concurrency Test Suite
Proves idempotency holds under parallel duplicate requests:
at-most-once execution, no double-apply, and no double quota charge.
"""

import asyncio
import uuid
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import create_jwt_token
from app.core.database import db
from app.core.models import (
    ApplicationStatus,
    ApplyLedgerEntry,
    ApplyLedgerStatus,
    JobListing,
    User,
    UserRole,
)
from app.core.postgres_adapter import PostgresDatabaseAdapter
from app.main import app


@pytest.mark.asyncio
async def test_concurrent_apply_idempotency_same_key():
    """Fires 8 concurrent identical apply-async requests with the same Idempotency-Key.

    Asserts:
    1. Exactly ONE request is newly accepted (HTTP 202 without Idempotency-Replayed).
    2. The other 7 requests are deduplicated (HTTP 409 or Idempotency-Replayed).
    3. The apply_ledger contains exactly ONE row for (user, job) — NOT 8.
    4. The user's daily apply usage incremented by exactly 1, not 8.
    """
    user_id = f"usr_idem_{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@test.com"
    user = User(user_id=user_id, email=email, password_hash="test", role=UserRole.FREE)
    db.create_user(user)

    job_id = f"job_idem_{uuid.uuid4().hex[:8]}"
    job = JobListing(
        job_id=job_id,
        user_id=user_id,
        fingerprint=f"fp_{job_id}",
        platform="Greenhouse",
        company="Acme Corp",
        title="Software Engineer",
        url="https://acme.com/jobs/1",
        status=ApplicationStatus.DISCOVERED,
    )
    db.save_job(job, user_id=user_id)

    token = create_jwt_token(
        {"sub": user_id, "email": email, "role": "FREE", "type": "access"},
        timedelta(minutes=15),
    )
    idempotency_key = f"idem_key_{uuid.uuid4().hex}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": idempotency_key,
    }

    transport = ASGITransport(app=app)

    async def send_apply():
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
            return await ac.post(f"/api/jobs/apply-async/{job_id}", json={"mode": "DRY_RUN"})

    try:
        # Fire 8 concurrent identical requests
        responses = await asyncio.gather(*[send_apply() for _ in range(8)])

        newly_accepted = [
            r for r in responses
            if r.status_code == 202 and r.headers.get("Idempotency-Replayed") != "true"
        ]
        deduplicated = [
            r for r in responses
            if r.status_code == 409 or r.headers.get("Idempotency-Replayed") == "true"
        ]

        # 1 & 2: Exactly one newly accepted, remaining deduplicated
        assert len(newly_accepted) == 1, (
            f"Expected exactly 1 newly accepted apply, got {len(newly_accepted)}. "
            f"Statuses: {[r.status_code for r in responses]}"
        )
        assert len(deduplicated) == 7, (
            f"Expected exactly 7 deduplicated requests, got {len(deduplicated)}. "
            f"Statuses: {[r.status_code for r in responses]}"
        )

        # Query database via connection
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM apply_ledger WHERE user_id = ? AND job_id = ?",
                (user_id, job_id),
            )
            ledger_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT apply_count FROM user_daily_usage WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            daily_usage = row[0] if row else 0

        # 4: Verify user daily usage incremented by exactly 1 (not 8)
        assert daily_usage == 1, (
            f"Expected daily usage to be exactly 1, got {daily_usage}"
        )

        # 3: Verify apply_ledger contains exactly 1 row (not 8)
        assert ledger_count == 1, (
            f"Expected apply_ledger to contain exactly 1 row for ({user_id}, {job_id}), got {ledger_count}"
        )

    finally:
        # Cleanup
        db.hard_delete_user_account(user_id)


@pytest.mark.asyncio
async def test_concurrent_apply_idempotency_different_keys():
    """Fires 8 concurrent apply-async requests with DIFFERENT Idempotency-Keys to the same job.

    Asserts:
    1. Exactly ONE request acquires the lock and is accepted (HTTP 202).
    2. The other 7 requests are rejected with HTTP 409 Conflict.
    3. The apply_ledger contains exactly ONE row for (user, job) — NOT 8.
    4. The user's daily apply usage incremented by exactly 1, not 8 (only winner is charged).
    """
    user_id = f"usr_diff_{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@test.com"
    user = User(user_id=user_id, email=email, password_hash="test", role=UserRole.FREE)
    db.create_user(user)

    job_id = f"job_diff_{uuid.uuid4().hex[:8]}"
    job = JobListing(
        job_id=job_id,
        user_id=user_id,
        fingerprint=f"fp_{job_id}",
        platform="Greenhouse",
        company="Beta Works",
        title="Backend Engineer",
        url="https://betaworks.com/jobs/2",
        status=ApplicationStatus.DISCOVERED,
    )
    db.save_job(job, user_id=user_id)

    token = create_jwt_token(
        {"sub": user_id, "email": email, "role": "FREE", "type": "access"},
        timedelta(minutes=15),
    )
    transport = ASGITransport(app=app)

    async def send_apply_with_key(i: int):
        distinct_headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"diff_key_{i}_{uuid.uuid4().hex}",
        }
        async with AsyncClient(transport=transport, base_url="http://test", headers=distinct_headers) as ac:
            return await ac.post(f"/api/jobs/apply-async/{job_id}", json={"mode": "DRY_RUN"})

    try:
        # Fire 8 concurrent requests with distinct idempotency keys
        responses = await asyncio.gather(*[send_apply_with_key(i) for i in range(8)])

        accepted = [r for r in responses if r.status_code == 202]
        conflicts = [r for r in responses if r.status_code == 409]

        # Exactly 1 request wins the atomic lock
        assert len(accepted) == 1, (
            f"Expected exactly 1 accepted apply across distinct keys, got {len(accepted)}. "
            f"Statuses: {[r.status_code for r in responses]}"
        )
        assert len(conflicts) == 7, (
            f"Expected exactly 7 conflict (409) responses across distinct keys, got {len(conflicts)}. "
            f"Statuses: {[r.status_code for r in responses]}"
        )

        # Query database via connection
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM apply_ledger WHERE user_id = ? AND job_id = ?",
                (user_id, job_id),
            )
            ledger_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT apply_count FROM user_daily_usage WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            daily_usage = row[0] if row else 0

        # Only the winner was charged
        assert daily_usage == 1, (
            f"Expected daily usage to be exactly 1, got {daily_usage}"
        )

        # Exactly one ledger row exists
        assert ledger_count == 1, (
            f"Expected apply_ledger to contain exactly 1 row for ({user_id}, {job_id}), got {ledger_count}"
        )

    finally:
        # Cleanup
        db.hard_delete_user_account(user_id)


def test_database_insert_ledger_if_absent_direct():
    """Unit test for SQLite db.insert_ledger_if_absent: inserts on clean, ignores on duplicate."""
    user_id = f"usr_dir_{uuid.uuid4().hex[:8]}"
    job_id = f"job_dir_{uuid.uuid4().hex[:8]}"
    entry1 = ApplyLedgerEntry(
        ledger_id=f"led_1_{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        job_id=job_id,
        job_fingerprint="fp_dir",
        status=ApplyLedgerStatus.INITIATED,
    )
    assert db.insert_ledger_if_absent(entry1, user_id=user_id) is True

    entry2 = ApplyLedgerEntry(
        ledger_id=f"led_2_{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        job_id=job_id,
        job_fingerprint="fp_dir",
        status=ApplyLedgerStatus.INITIATED,
    )
    assert db.insert_ledger_if_absent(entry2, user_id=user_id) is False

    db.hard_delete_user_account(user_id)


def test_postgres_adapter_insert_ledger_if_absent_unit(monkeypatch):
    """Unit test for PostgresDatabaseAdapter.insert_ledger_if_absent with mock connection."""
    adapter = PostgresDatabaseAdapter("postgresql://user:pass@localhost/db")
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    monkeypatch.setattr(adapter, "get_connection", lambda: mock_conn)
    monkeypatch.setattr(adapter, "release_connection", lambda conn: None)

    entry = ApplyLedgerEntry(
        ledger_id="led_pg_test",
        user_id="usr_pg_test",
        job_id="job_pg_test",
        job_fingerprint="fp_pg_test",
        status=ApplyLedgerStatus.INITIATED,
    )

    mock_cursor.rowcount = 1
    assert adapter.insert_ledger_if_absent(entry, user_id="usr_pg_test") is True

    mock_cursor.rowcount = 0
    assert adapter.insert_ledger_if_absent(entry, user_id="usr_pg_test") is False

    # Also exercise get and list methods for coverage
    sample_row = (
        "led_pg_test", "usr_pg_test", "job_pg_test", "fp_pg_test", "INITIATED",
        1, 3, None, None, "CONF1", None, "idem1", "2026-09-01T00:00:00", "2026-09-01T00:00:00"
    )
    mock_cursor.fetchone.return_value = sample_row
    assert adapter.get_apply_ledger_entry("led_pg_test", "usr_pg_test") is not None
    assert adapter.get_active_ledger_by_fingerprint("fp_pg_test", "usr_pg_test") is not None
    assert adapter.get_ledger_for_job("job_pg_test", "usr_pg_test") is not None

    mock_cursor.fetchall.return_value = [sample_row]
    assert len(adapter.list_user_apply_ledger("usr_pg_test")) == 1

    # Exercise save_apply_ledger_entry
    assert adapter.save_apply_ledger_entry(entry, user_id="usr_pg_test") is True


@pytest.mark.asyncio
async def test_apply_async_edge_cases():
    """Validates 404 (job not found), rate limit, tasks polling, and existing ledger 409 responses."""
    user_id = f"usr_edge_{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@test.com"
    user = User(user_id=user_id, email=email, password_hash="test", role=UserRole.FREE)
    db.create_user(user)

    token = create_jwt_token(
        {"sub": user_id, "email": email, "role": "FREE", "type": "access"},
        timedelta(minutes=15),
    )
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
            # 1. Job not found -> 404
            res_404 = await ac.post("/api/jobs/apply-async/nonexistent_job", json={"mode": "DRY_RUN"})
            assert res_404.status_code == 404

            # 2. Existing ledger with SUBMITTED -> 409
            job_id = f"job_edge_{uuid.uuid4().hex[:8]}"
            entry = ApplyLedgerEntry(
                ledger_id=f"led_{uuid.uuid4().hex[:8]}",
                user_id=user_id,
                job_id=job_id,
                job_fingerprint=f"fp_{job_id}",
                status=ApplyLedgerStatus.SUBMITTED,
            )
            db.save_apply_ledger_entry(entry, user_id=user_id)
            res_409_sub = await ac.post(f"/api/jobs/apply-async/{job_id}", json={"mode": "DRY_RUN"})
            assert res_409_sub.status_code == 409
            assert "already submitted" in res_409_sub.json()["detail"].lower()

            # 3. Existing ledger with IN_PROGRESS -> 409
            job_id_prog = f"job_prog_{uuid.uuid4().hex[:8]}"
            entry_prog = ApplyLedgerEntry(
                ledger_id=f"led_{uuid.uuid4().hex[:8]}",
                user_id=user_id,
                job_id=job_id_prog,
                job_fingerprint=f"fp_{job_id_prog}",
                status=ApplyLedgerStatus.IN_PROGRESS,
            )
            db.save_apply_ledger_entry(entry_prog, user_id=user_id)
            res_409_prog = await ac.post(f"/api/jobs/apply-async/{job_id_prog}", json={"mode": "DRY_RUN"})
            assert res_409_prog.status_code == 409
            assert "actively executing" in res_409_prog.json()["detail"].lower()

            # 4. Valid apply and tasks status polling
            valid_job_id = f"job_valid_{uuid.uuid4().hex[:8]}"
            valid_job = JobListing(
                job_id=valid_job_id,
                user_id=user_id,
                fingerprint=f"fp_{valid_job_id}",
                platform="Greenhouse",
                company="Valid Co",
                title="Engineer",
                url="https://valid.com",
                status=ApplicationStatus.DISCOVERED,
            )
            db.save_job(valid_job, user_id=user_id)

            res_apply = await ac.post(f"/api/jobs/apply-async/{valid_job_id}", json={"mode": "DRY_RUN"})
            assert res_apply.status_code == 202
            task_id = res_apply.json()["task_id"]

            res_task = await ac.get(f"/api/tasks/{task_id}")
            assert res_task.status_code == 200
            assert res_task.json()["status"] == "success"

            # 5. Ledger list and item query endpoints
            res_ledger_list = await ac.get("/api/bot/ledger")
            assert res_ledger_list.status_code == 200

            res_job_ledger = await ac.get(f"/api/bot/ledger/{valid_job_id}")
            assert res_job_ledger.status_code == 200
    finally:
        db.hard_delete_user_account(user_id)
