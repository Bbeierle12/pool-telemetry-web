"""WebSocket handler for real-time events."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Optional, Set

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.auth import verify_ws_token
from app.models.database import Session, Event

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections for real-time event broadcasting."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if session_id not in self.active_connections:
                self.active_connections[session_id] = set()
            self.active_connections[session_id].add(websocket)

    async def disconnect(self, session_id: str, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            if session_id in self.active_connections:
                self.active_connections[session_id].discard(websocket)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]

    async def broadcast(self, session_id: str, message: dict):
        """Broadcast a message to all connections for a session."""
        if session_id not in self.active_connections:
            return

        data = json.dumps(message)
        dead_connections = []

        for websocket in self.active_connections[session_id]:
            try:
                await websocket.send_text(data)
            except Exception:
                dead_connections.append(websocket)

        # Clean up dead connections
        for ws in dead_connections:
            await self.disconnect(session_id, ws)

    def get_connection_count(self, session_id: str) -> int:
        """Get number of active connections for a session."""
        return len(self.active_connections.get(session_id, set()))


# Global connection manager
manager = ConnectionManager()


@router.websocket("/events/{session_id}")
async def events_websocket(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time events.

    Requires authentication via token query parameter.

    Clients receive:
    - ball_update: Ball positions and states
    - shot: Shot detected
    - pocket: Ball pocketed
    - foul: Foul detected
    - status: Session status changes
    """
    # Verify authentication
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    profile_id = verify_ws_token(token)
    if not profile_id:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify session exists and belongs to user
    async with async_session() as db:
        result = await db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.profile_id == profile_id
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            await websocket.close(code=4004, reason="Session not found")
            return

    await manager.connect(session_id, websocket)

    # Send initial connection confirmation
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            # Receive messages from client (commands, heartbeat)
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "ping":
                    # Respond to heartbeat
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "subscribe":
                    # Client wants to subscribe to specific event types
                    event_types = message.get("event_types", [])
                    await websocket.send_json({
                        "type": "subscribed",
                        "event_types": event_types,
                    })

            except json.JSONDecodeError:
                pass  # Ignore invalid JSON

    except WebSocketDisconnect:
        await manager.disconnect(session_id, websocket)


# Helper functions for broadcasting events from other parts of the app

async def broadcast_ball_update(session_id: str, balls: list):
    """Broadcast ball position updates."""
    await manager.broadcast(session_id, {
        "type": "ball_update",
        "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "balls": balls,
    })


async def broadcast_event(session_id: str, event_type: str, data: dict):
    """Broadcast a game event."""
    await manager.broadcast(session_id, {
        "type": event_type,
        "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "data": data,
    })


async def broadcast_shot(session_id: str, shot_data: dict):
    """Broadcast shot detected."""
    await manager.broadcast(session_id, {
        "type": "shot",
        "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "shot": shot_data,
    })


async def broadcast_pocket(session_id: str, ball_name: str, pocket_id: str):
    """Broadcast ball pocketed."""
    await manager.broadcast(session_id, {
        "type": "pocket",
        "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ball": ball_name,
        "pocket": pocket_id,
    })


async def broadcast_foul(session_id: str, foul_type: str, details: dict):
    """Broadcast foul detected."""
    await manager.broadcast(session_id, {
        "type": "foul",
        "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "foul_type": foul_type,
        "details": details,
    })


async def broadcast_status(session_id: str, status: str, message: str = None):
    """Broadcast session status change."""
    await manager.broadcast(session_id, {
        "type": "status",
        "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "status": status,
        "message": message,
    })


# Store event in database
async def store_and_broadcast_event(
    session_id: str,
    event_type: str,
    event_data: dict,
    timestamp_ms: int = None
):
    """Store an event in the database and broadcast to clients."""
    if timestamp_ms is None:
        timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # Store in database
    async with async_session() as db:
        event = Event(
            session_id=session_id,
            timestamp_ms=timestamp_ms,
            event_type=event_type,
            event_data=event_data,
        )
        db.add(event)
        await db.commit()

    # Broadcast to connected clients
    await broadcast_event(session_id, event_type, event_data)
