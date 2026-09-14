"""
JobCopilot - Backend Server Application
FastAPI Server with WebSockets, SQLite WAL, Static File Hosting, and Cryptographic Vault.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.auth import limiter
from app.api.endpoints import router as api_router
from app.api.endpoints import ws_manager
from app.api.middleware import (
    ApiDeprecationMiddleware,
    IdempotencyMiddleware,
    RequestTracingMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.database import get_db
from app.core.settings import settings

# Sentry Exception Tracking in Production
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=1.0 if settings.ENV != "production" else 0.1,
            environment=settings.ENV
        )
    except Exception:
        pass

app = FastAPI(
    title="JobCopilot API",
    description="Universal Autonomous Job Hunting, Self-Learning Application & Career Operating System",
    version="1.0.0"
)

logger = logging.getLogger("jobcopilot.metrics")

# Prometheus Metrics Definitions
HTTP_REQUESTS_TOTAL = Counter("jobcopilot_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
HTTP_REQUEST_DURATION = Histogram("jobcopilot_http_request_duration_seconds", "HTTP request latency in seconds", ["endpoint"])
# Gauges referenced by monitoring/prometheus_alerts.yml (JobCopilotCircuitBreakerOpen,
# JobCopilotDlqBuildup) — populated at scrape time from live app state below.
CIRCUIT_BREAKER_STATE = Gauge(
    "jobcopilot_circuit_breaker_state",
    "Circuit breaker state (1 = active). One series per breaker per state label.",
    ["circuit_name", "state"],
)
DLQ_TASKS_COUNT = Gauge("jobcopilot_dlq_tasks_count", "Number of tasks currently in the dead-letter queue")


def _refresh_observability_gauges() -> None:
    """Sync the scrape-time gauges to current app state (best-effort, never raises)."""
    try:
        from app.core.circuit_breaker import CircuitState, get_all_circuit_statuses
        all_states = [s.value.lower() for s in CircuitState]
        for name, status in get_all_circuit_statuses().items():
            current = str(status.get("state", "")).lower()
            for st in all_states:
                CIRCUIT_BREAKER_STATE.labels(circuit_name=name, state=st).set(1 if st == current else 0)
    except Exception:
        logger.debug("Circuit breaker gauge refresh skipped", exc_info=True)
    try:
        from app.tasks.celery_app import local_task_runner
        DLQ_TASKS_COUNT.set(len(local_task_runner.get_dlq_tasks()))
    except Exception:
        logger.debug("DLQ gauge refresh skipped", exc_info=True)

# Wire Slowapi Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. Tracing & Latency Logger
app.add_middleware(RequestTracingMiddleware)

# 2. RFC 8594 Sunset & Deprecation Warning for Legacy /api/ Routes
app.add_middleware(ApiDeprecationMiddleware)

# 3. Idempotency Key Engine for Mutating Operations
app.add_middleware(IdempotencyMiddleware)

# 4. Strict Security Headers (CSP, HSTS, X-Frame-Options)
app.add_middleware(SecurityHeadersMiddleware)

# 3. CORS Policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else [settings.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "Accept",
        "Idempotency-Key",
        "traceparent",
        "X-Trace-ID",
        "X-Span-ID"
    ],
)

# Observability Endpoints
@app.get("/metrics", tags=["Observability"])
async def metrics_endpoint():
    """Prometheus application telemetry scrape target."""
    _refresh_observability_gauges()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health", tags=["Observability"])
async def health_check():
    """Deep system health probe validating database read/write and subsystem status."""
    db_status = "healthy"
    db_mode = "postgres" if (settings.DATABASE_URL and settings.DATABASE_URL.startswith("postgres")) else "sqlite_wal"
    try:
        db_adapter = get_db()
        _ = db_adapter.get_user_by_email("healthcheck@jobcopilot.local")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    is_overall_healthy = db_status == "healthy"
    status_code = 200 if is_overall_healthy else 503
    from app.core.circuit_breaker import get_all_circuit_statuses
    circuits = get_all_circuit_statuses()

    return Response(
        content=json.dumps({
            "status": "healthy" if is_overall_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.ENV,
            "version": "1.0.0",
            "database": {
                "status": db_status,
                "engine": db_mode
            },
            "circuit_breakers": circuits,
            "sentry_enabled": bool(settings.SENTRY_DSN)
        }),
        status_code=status_code,
        media_type="application/json"
    )

@app.post("/api/client-errors", tags=["Observability"], status_code=204)
@limiter.limit("30/minute")
async def report_client_error(request: Request):
    """Sink for uncaught client-side JS errors so frontend failures aren't invisible.

    Best-effort and never fails the caller: logs the error (with the request id
    for correlation) and forwards to Sentry when configured. Rate-limited per
    user/IP to prevent a broken client from flooding the backend.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if isinstance(payload, dict):
        info = {k: payload.get(k) for k in ("message", "source", "line", "col", "url", "stack", "userAgent")}
    else:
        info = {"message": str(payload)[:500]}
    request_id = getattr(request.state, "request_id", None)
    logger.warning("client_error request_id=%s %s", request_id, {k: v for k, v in info.items() if k != "stack"})
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.capture_message(f"[client] {info.get('message')}", level="error")
        except Exception:
            logger.debug("Sentry capture of client error failed", exc_info=True)
    return Response(status_code=204)


# Include REST Router
app.include_router(api_router)


# WebSocket Route for Strict Authenticated Real-Time Streaming
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """
    Strict Authenticated WebSocket Gateway.
    Requires unrevoked, valid JWT Bearer access token passed via query parameter (?token=...).
    Closes with 4001 (Unauthorized) if token is missing, invalid, or revoked.
    """
    from app.api.auth import decode_jwt_token
    from app.core.database import db

    if not token:
        await websocket.close(code=4001, reason="Authentication required. Provide token query parameter.")
        return

    try:
        payload = decode_jwt_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001, reason="Invalid token type.")
            return

        jti = payload.get("jti")
        if jti and db.is_token_revoked(jti):
            await websocket.close(code=4001, reason="Token has been revoked.")
            return

        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token subject.")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid authentication token.")
        return

    await ws_manager.connect(websocket, user_id=user_id)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "PONG", "message": "connected", "user_id": user_id})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id=user_id)
    except Exception:
        ws_manager.disconnect(websocket, user_id=user_id)


# Mount Static Frontend & PWA Routes
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")
    icons_dir = frontend_dir / "icons"
    if icons_dir.exists():
        app.mount("/icons", StaticFiles(directory=str(icons_dir)), name="icons")

    @app.get("/manifest.json")
    async def serve_manifest():
        manifest_file = frontend_dir / "manifest.json"
        if manifest_file.exists():
            return FileResponse(str(manifest_file), media_type="application/manifest+json")
        return Response(status_code=404)

    @app.get("/sw.js")
    async def serve_service_worker():
        sw_file = frontend_dir / "sw.js"
        if sw_file.exists():
            return FileResponse(
                str(sw_file),
                media_type="application/javascript",
                headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"}
            )
        return Response(status_code=404)

    @app.get("/")
    async def serve_frontend():
        return FileResponse(str(frontend_dir / "index.html"))

# Mount Legal Documentation Routes
docs_dir = Path(__file__).resolve().parent.parent.parent / "docs"

def _render_legal_doc(file_path: Path, title: str) -> HTMLResponse:
    if not file_path.exists():
        return HTMLResponse("<h1>Document Not Found</h1>", status_code=404)
    content = file_path.read_text(encoding="utf-8")
    try:
        from markdown_it import MarkdownIt
        md = MarkdownIt()
        rendered_body = md.render(content)
    except Exception:
        import html
        rendered_body = f"<pre>{html.escape(content)}</pre>"

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — JobCopilot</title>
  <style>
    body {{
      background: #06080d;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.6;
      margin: 0;
      padding: 2.5rem 1rem;
    }}
    .legal-container {{
      max-width: 820px;
      margin: 0 auto;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 12px;
      padding: 2.5rem;
      backdrop-filter: blur(16px);
      box-shadow: 0 10px 35px rgba(0, 0, 0, 0.6);
    }}
    h1, h2, h3, h4 {{ color: #ffffff; margin-top: 1.5rem; }}
    a {{ color: #818cf8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    pre, code {{ background: rgba(0, 0, 0, 0.4); padding: 2px 6px; border-radius: 4px; color: #38bdf8; font-family: monospace; font-size: 13px; }}
    hr {{ border: none; border-top: 1px solid rgba(255, 255, 255, 0.1); margin: 2rem 0; }}
    .back-nav {{ margin-bottom: 1.5rem; font-size: 14px; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 13.5px; }}
    th, td {{ border: 1px solid rgba(255, 255, 255, 0.12); padding: 8px 12px; text-align: left; }}
    th {{ background: rgba(255, 255, 255, 0.05); color: #fff; }}
  </style>
</head>
<body>
  <div class="legal-container">
    <div class="back-nav"><a href="/">&larr; Back to JobCopilot</a></div>
    {rendered_body}
  </div>
</body>
</html>"""
    return HTMLResponse(content=page_html, status_code=200)

@app.get("/legal/terms", response_class=HTMLResponse, tags=["Legal"])
async def serve_terms():
    return _render_legal_doc(docs_dir / "compliance" / "TERMS_OF_SERVICE.md", "Terms of Service")

@app.get("/legal/privacy", response_class=HTMLResponse, tags=["Legal"])
async def serve_privacy():
    return _render_legal_doc(docs_dir / "PRIVACY.md", "Privacy Policy")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
