"""
JobCopilot - Multi-Tenant WebSocket & Pub/Sub Gateway
Dispatches real-time telemetry, logs, HITL prompts, and notifications per tenant (user_id).
Supports local multi-room WebSocket and Redis Pub/Sub cluster distribution.
"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from fastapi import WebSocket


class MultiTenantWebSocketGateway:
    """Manages active WebSockets segmented by user_id."""

    def __init__(self):
        # Map of user_id -> List[WebSocket]
        self.user_sockets: Dict[str, List[WebSocket]] = {}
        self.broadcast_sockets: List[WebSocket] = []
        self.redis_client = None

    async def connect(self, websocket: WebSocket, user_id: str = "default_user"):
        await websocket.accept()
        if user_id not in self.user_sockets:
            self.user_sockets[user_id] = []
        self.user_sockets[user_id].append(websocket)
        self.broadcast_sockets.append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str = "default_user"):
        if user_id in self.user_sockets:
            if websocket in self.user_sockets[user_id]:
                self.user_sockets[user_id].remove(websocket)
        if websocket in self.broadcast_sockets:
            self.broadcast_sockets.remove(websocket)

    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """Publishes message strictly to the specified tenant's connected clients."""
        payload = json.dumps(message)
        sockets = self.user_sockets.get(user_id, [])
        for ws in list(sockets):
            try:
                await ws.send_text(payload)
            except Exception:
                self.disconnect(ws, user_id)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts global message to all connected clients."""
        payload = json.dumps(message)
        for ws in list(self.broadcast_sockets):
            try:
                await ws.send_text(payload)
            except Exception:
                if ws in self.broadcast_sockets:
                    self.broadcast_sockets.remove(ws)


# Global WebSocket Gateway Singleton
ws_gateway = MultiTenantWebSocketGateway()
