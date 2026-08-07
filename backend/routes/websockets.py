"""WebSocket ConnectionManager and real-time live activity stream router."""

import logging
import json
import asyncio
from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSockets & Live Stream"])


class ConnectionManager:
    """Manages active WebSocket connections for live activity streaming."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Active connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send personal WS message: {e}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast event message to all connected clients."""
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error broadcasting WS message: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager
ws_manager = ConnectionManager()


@router.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time live community activity stream."""
    await ws_manager.connect(websocket)

    # Send initial welcome message
    await ws_manager.send_personal_message(
        {
            "event": "connected",
            "message": "Connected to Smart Community Platform live stream",
            "active_clients": len(ws_manager.active_connections)
        },
        websocket
    )

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                # Handle client ping / heartbeat
                if payload.get("type") == "ping":
                    await ws_manager.send_personal_message({"type": "pong"}, websocket)
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def broadcast_event(event_type: str, data: Dict[str, Any]):
    """Helper function to broadcast events to all active WS clients."""
    await ws_manager.broadcast({
        "event": event_type,
        "data": data,
        "timestamp": asyncio.get_event_loop().time()
    })
