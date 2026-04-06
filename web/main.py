"""
Web entry point — FastAPI server.
Provides REST API and WebSocket interface for remote robot control.

Usage:
    pip install fastapi uvicorn
    uvicorn web.main:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
    GET  /                     — Web UI (static HTML)
    GET  /api/status           — Robot state JSON
    POST /api/connect          — Connect to serial port
    POST /api/disconnect       — Disconnect
    POST /api/move             — Move joint(s)
    POST /api/stop             — Emergency stop
    POST /api/ik               — Inverse kinematics solve
    WS   /ws                   — Real-time motor telemetry
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from web.api.routes import router as api_router
from web.api.websocket import router as ws_router

app = FastAPI(
    title="ST3215 Robot Control API",
    description="Web interface for 6-axis robot manipulator control",
    version="1.0.0",
)

app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

_STATIC = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC):
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(os.path.join(_STATIC, "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web.main:app", host="0.0.0.0", port=8000, reload=True)
