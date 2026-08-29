"""
JobCopilot - Backend Server Application
FastAPI Server with WebSockets, SQLite WAL, and Cryptographic Vault.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router, ws_manager

app = FastAPI(
    title="JobCopilot API",
    description="Universal Autonomous Job Hunting, Self-Learning Application & Career Operating System",
    version="1.0.0"
)

# Enable CORS for React frontend (Vite default: http://localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST Router
app.include_router(api_router)


# WebSocket Route for Real-Time Streaming (Bot Logs, HITL Alerts, Kanban status)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming ping/heartbeat
            await websocket.send_json({"type": "PONG", "message": "connected"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.get("/")
async def root():
    return {
        "app": "JobCopilot",
        "status": "online",
        "docs_url": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
