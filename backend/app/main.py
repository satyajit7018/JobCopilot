"""
JobCopilot - Backend Server Application
FastAPI Server with WebSockets, SQLite WAL, Static File Hosting, and Cryptographic Vault.
"""

from pathlib import Path
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.core.settings import settings
from app.api.middleware import SecurityHeadersMiddleware, RequestTracingMiddleware
from app.api.auth import limiter
from app.api.endpoints import router as api_router, ws_manager

app = FastAPI(
    title="JobCopilot API",
    description="Universal Autonomous Job Hunting, Self-Learning Application & Career Operating System",
    version="1.0.0"
)

# Wire Slowapi Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. Tracing & Latency Logger
app.add_middleware(RequestTracingMiddleware)

# 2. Strict Security Headers (CSP, HSTS, X-Frame-Options)
app.add_middleware(SecurityHeadersMiddleware)

# 3. CORS Policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else [settings.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept"],
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


# Mount Static Frontend
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(str(frontend_dir / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
