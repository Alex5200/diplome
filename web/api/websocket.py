"""
WebSocket endpoint for real-time motor telemetry.

Clients connect to ws://<host>:8000/ws and receive JSON frames at ~5 Hz:
    {
        "type": "telemetry",
        "motors": { "<id>": { "position": int, "temperature": float, ... } }
    }
"""

from __future__ import annotations

import asyncio
import json
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

_clients: Set[WebSocket] = set()


async def _broadcast(data: dict) -> None:
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


@router.websocket("/ws")
async def telemetry_ws(ws: WebSocket):
    """Stream real-time motor telemetry to connected web clients."""
    await ws.accept()
    _clients.add(ws)
    try:
        # Keep the connection alive; telemetry is pushed by the background task
        while True:
            # Accept pings / client messages (ignored for now)
            await asyncio.wait_for(ws.receive_text(), timeout=30)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        _clients.discard(ws)


async def push_telemetry(motor_data: dict) -> None:
    """Called by the monitoring background task to push data to all clients."""
    await _broadcast({"type": "telemetry", "motors": motor_data})
