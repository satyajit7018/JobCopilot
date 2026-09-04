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
    """Tracks unique correlation X-Request-ID and logs request latencies."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        start_time = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        
        # Log structured request details
        if not request.url.path.startswith("/metrics") and not request.url.path.startswith("/health"):
            user_id = getattr(request.state, "user_id", "anonymous")
            logger.info(
                f'{{"request_id": "{request_id}", "method": "{request.method}", '
                f'"path": "{request.url.path}", "status": {response.status_code}, '
                f'"duration_ms": {duration_ms}, "user_id": "{user_id}"}}'
            )

        return response
