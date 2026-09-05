"""
JobCopilot - Distributed Idempotency Engine
Provides at-most-once execution semantics for mutating API requests (POST, PUT, PATCH, DELETE).
Tracks SHA-256 payload signatures, manages in-flight execution locks, and replays cached responses.
"""

import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

from app.core.database import get_db

logger = logging.getLogger("jobcopilot.idempotency")


class IdempotencyResult:
    ACQUIRED = "ACQUIRED"
    REPLAY = "REPLAY"
    IN_PROGRESS = "IN_PROGRESS"
    MISMATCH = "MISMATCH"


class IdempotencyEngine:
    """Enterprise idempotency coordinator supporting multi-tenant isolation and fail-safe replays."""

    def __init__(self):
        self._lock = threading.Lock()
        self._in_flight_keys: Dict[str, str] = {}  # key -> user_id

    @staticmethod
    def compute_request_hash(method: str, path: str, body: bytes) -> str:
        """Computes deterministic SHA-256 hash across HTTP method, normalized path, and raw body."""
        hasher = hashlib.sha256()
        hasher.update(method.upper().strip().encode("utf-8"))
        hasher.update(path.strip().encode("utf-8"))
        hasher.update(body or b"")
        return hasher.hexdigest()

    def acquire(
        self,
        key: str,
        user_id: str,
        method: str,
        path: str,
        body: bytes,
        ttl_seconds: int = 86400
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Attempts to acquire execution rights for an Idempotency-Key.
        Returns:
            - ("ACQUIRED", None) -> Proceed with request execution.
            - ("REPLAY", record) -> Return cached response immediately.
            - ("IN_PROGRESS", None) -> Duplicate in-flight request, return 409 Conflict.
            - ("MISMATCH", record) -> Key reused with different payload, return 422 Unprocessable Entity.
        """
        request_hash = self.compute_request_hash(method, path, body)
        composite_key = f"{user_id}:{key}"

        with self._lock:
            # 1. Check in-memory in-flight table
            if composite_key in self._in_flight_keys:
                return IdempotencyResult.IN_PROGRESS, None

            db = get_db()
            record = db.get_idempotency_record(key, user_id=user_id)

            if record:
                # Validate payload integrity
                if record.get("request_hash") != request_hash:
                    logger.warning(f"Idempotency key mismatch: key={key}, user={user_id}")
                    return IdempotencyResult.MISMATCH, record

                if record.get("status") == "COMPLETED":
                    return IdempotencyResult.REPLAY, record

                if record.get("status") == "PENDING":
                    return IdempotencyResult.IN_PROGRESS, record

            # Register in-flight lock
            self._in_flight_keys[composite_key] = user_id

            # Persist pending record in database
            expires_at = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat()
            db.save_idempotency_record({
                "idempotency_key": key,
                "user_id": user_id,
                "method": method,
                "path": path,
                "request_hash": request_hash,
                "status": "PENDING",
                "status_code": None,
                "response_headers": {},
                "response_body": None,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at
            })

            return IdempotencyResult.ACQUIRED, None

    def complete(
        self,
        key: str,
        user_id: str,
        status_code: int,
        response_headers: Dict[str, str],
        response_body: str
    ) -> bool:
        """Marks request execution as completed and stores response for replay."""
        composite_key = f"{user_id}:{key}"
        with self._lock:
            self._in_flight_keys.pop(composite_key, None)

        # Filter hop-by-hop headers before caching
        safe_headers = {}
        for h, v in response_headers.items():
            h_lower = h.lower()
            if h_lower not in ("content-length", "transfer-encoding", "connection", "keep-alive"):
                safe_headers[h] = v

        db = get_db()
        return db.update_idempotency_record(
            idempotency_key=key,
            status="COMPLETED",
            status_code=status_code,
            response_headers=safe_headers,
            response_body=response_body
        )

    def release(self, key: str, user_id: str) -> bool:
        """Releases the lock on error or unhandled exception so request can be safely retried."""
        composite_key = f"{user_id}:{key}"
        with self._lock:
            self._in_flight_keys.pop(composite_key, None)

        db = get_db()
        return db.delete_idempotency_record(key)


idempotency_engine = IdempotencyEngine()
