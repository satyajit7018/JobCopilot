"""
JobCopilot - Security Headers & Request Tracing Middleware
Applies Defense-in-Depth HTTP security headers (CSP, HSTS, X-Frame-Options),
request-id correlation tracking, and structured latency logging.
"""

import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.settings import settings
from app.core.telemetry import telemetry

logger = logging.getLogger("jobcopilot.access")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects strict security headers onto every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 1. Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "manifest-src 'self'; "
            "worker-src 'self'; "
            "connect-src 'self' ws: wss: http: https:;"
        )

        # 2. Frame & Clickjacking Protection
        response.headers["X-Frame-Options"] = "DENY"

        # 3. MIME-Type Sniffing Protection
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 4. Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 5. Permissions Policy
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"

        # 6. HSTS in Production
        if settings.ENV.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Tracks unique correlation X-Request-ID, W3C traceparent, OpenTelemetry root spans, and logs request latencies."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        # Extract parent span context if incoming (traceparent / X-Trace-ID)
        header_dict = {k.lower(): v for k, v in request.headers.items()}
        parent_context = telemetry.extract_context_from_headers(header_dict)

        span = telemetry.start_span(
            name="http.request",
            parent_context=parent_context,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.target": request.url.path,
                "http.user_agent": request.headers.get("user-agent", ""),
                "http.request_id": request_id
            }
        )

        request.state.trace_id = span.context.trace_id
        request.state.span_id = span.context.span_id
        request.state.traceparent = span.context.to_traceparent()

        start_time = time.time()
        try:
            with span:
                response = await call_next(request)
                span.set_attribute("http.status_code", response.status_code)
                if response.status_code >= 500:
                    span.status_code = "ERROR"
        except Exception as exc:
            span.record_exception(exc)
            raise exc

        duration_ms = round((time.time() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["traceparent"] = span.context.to_traceparent()
        response.headers["X-Trace-ID"] = span.context.trace_id
        response.headers["X-Span-ID"] = span.context.span_id
        
        # Log structured request details with trace correlation
        if not request.url.path.startswith("/metrics") and not request.url.path.startswith("/health"):
            user_id = getattr(request.state, "user_id", "anonymous")
            logger.info(
                f'{{"request_id": "{request_id}", "trace_id": "{span.context.trace_id}", '
                f'"span_id": "{span.context.span_id}", "method": "{request.method}", '
                f'"path": "{request.url.path}", "status": {response.status_code}, '
                f'"duration_ms": {duration_ms}, "user_id": "{user_id}"}}'
            )

        return response


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Enforces at-most-once execution for mutating requests with an Idempotency-Key header.
    Replays completed cached responses, detects concurrent in-flight executions (409),
    and rejects payload signature divergences (422).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            return await call_next(request)

        # Extract user_id from token or request state for tenant isolation
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
                try:
                    import jwt
                    unverified = jwt.decode(token, options={"verify_signature": False})
                    user_id = unverified.get("sub")
                except Exception:
                    user_id = None
        if not user_id:
            client_ip = request.client.host if request.client else "127.0.0.1"
            user_id = f"ip_{client_ip}"

        from app.core.idempotency import idempotency_engine, IdempotencyResult
        import json

        body = await request.body()
        result, record = idempotency_engine.acquire(
            key=idempotency_key,
            user_id=user_id,
            method=request.method,
            path=request.url.path,
            body=body
        )

        if result == IdempotencyResult.IN_PROGRESS:
            return Response(
                content=json.dumps({
                    "detail": "Request with this Idempotency-Key is currently in progress. Please retry shortly."
                }),
                status_code=409,
                media_type="application/json",
                headers={"Idempotency-Key": idempotency_key, "Retry-After": "1"}
            )

        if result == IdempotencyResult.MISMATCH:
            return Response(
                content=json.dumps({
                    "detail": "Idempotency key payload mismatch: same key used with different request parameters."
                }),
                status_code=422,
                media_type="application/json",
                headers={"Idempotency-Key": idempotency_key}
            )

        if result == IdempotencyResult.REPLAY and record:
            replay_headers = dict(record.get("response_headers", {}))
            replay_headers["Idempotency-Key"] = idempotency_key
            replay_headers["Idempotency-Replayed"] = "true"
            replay_headers["X-Cache-Lookup"] = "HIT"
            return Response(
                content=record.get("response_body", ""),
                status_code=record.get("status_code", 200),
                headers=replay_headers,
                media_type=replay_headers.get("content-type", "application/json")
            )

        # ACQUIRED: execute request and capture response
        try:
            response = await call_next(request)

            # Read streaming response body
            response_chunks = []
            async for chunk in response.body_iterator:
                response_chunks.append(chunk)

            full_body_bytes = b"".join(response_chunks)
            full_body_str = full_body_bytes.decode("utf-8", errors="replace")

            # Re-wrap body iterator for client delivery
            async def _stream_gen():
                yield full_body_bytes

            response.body_iterator = _stream_gen()
            response.headers["Idempotency-Key"] = idempotency_key

            # Only cache non-5xx responses (allow transient server errors to be retried)
            if response.status_code < 500:
                response_headers = dict(response.headers)
                idempotency_engine.complete(
                    key=idempotency_key,
                    user_id=user_id,
                    status_code=response.status_code,
                    response_headers=response_headers,
                    response_body=full_body_str
                )
            else:
                idempotency_engine.release(idempotency_key, user_id)

            return response

        except Exception:
            idempotency_engine.release(idempotency_key, user_id)
            raise

