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

from app.api.endpoints import router as api_router, ws_manager

app = FastAPI(
    title="JobCopilot API",
    description="Universal Autonomous Job Hunting, Self-Learning Application & Career Operating System",
    version="1.0.0"
)

# Enable CORS with explicit origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST Router
app.include_router(api_router)


# WebSocket Route for Real-Time Streaming (Bot Logs, HITL Alerts, Kanban status)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    from app.api.auth import decode_jwt_token
    user_id = None
    if token:
        try:
            payload = decode_jwt_token(token)
            user_id = payload.get("sub")
        except Exception:
            pass

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
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
