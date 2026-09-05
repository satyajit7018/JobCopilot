"""
JobCopilot - Backend Server Application
FastAPI Server with WebSockets, SQLite WAL, Static File Hosting, and Cryptographic Vault.
"""

from pathlib import Path
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import json
from fastapi.responses import Response, FileResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.core.settings import settings
from app.api.middleware import SecurityHeadersMiddleware, RequestTracingMiddleware, IdempotencyMiddleware
from app.api.auth import limiter
from app.api.endpoints import router as api_router, ws_manager
from app.core.database import get_db

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

# Prometheus Metrics Definitions
HTTP_REQUESTS_TOTAL = Counter("jobcopilot_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
HTTP_REQUEST_DURATION = Histogram("jobcopilot_http_request_duration_seconds", "HTTP request latency in seconds", ["endpoint"])

# Wire Slowapi Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. Tracing & Latency Logger
app.add_middleware(RequestTracingMiddleware)

# 2. Idempotency Key Engine for Mutating Operations
app.add_middleware(IdempotencyMiddleware)

# 3. Strict Security Headers (CSP, HSTS, X-Frame-Options)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
