#!/usr/bin/env python3
"""
Web entry point — FastAPI server with JWT auth + UDP motor telemetry.

Provides REST API, WebSocket, and UDP broadcast for remote robot control.

Usage:
    pip install fastapi uvicorn PyJWT
    python main.py [--no-auth]

Endpoints:
    POST /auth/login               — получить JWT токен
    POST /auth/token/generate      — генерация API-токена (требует JWT)
    GET  /auth/me                  — инфо о текущем токене

    GET  /api/status               — Robot state JSON (публичный)
    POST /api/connect              — подключиться к роботу (требует токен, или без auth)
    POST /api/disconnect           — отключиться (требует токен, или без auth)
    POST /api/move                 — двигать сустав (требует токен, или без auth)
    POST /api/stop                 — аварийная остановка (требует токен, или без auth)
    POST /api/ik                   — inverse kinematics (требует токен, или без auth)

    GET  /api/ml/status            — статус ML-трекера
    POST /api/ml/start             — запустить ML-трекинг (требует токен)
    POST /api/ml/stop              — остановить ML-трекинг (требует токен)

    WS   /ws                       — Real-time motor telemetry
    UDP  0.0.0.0:5005              — Motor position broadcast (каждые 50 мс)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import sys
import threading
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.api.auth import require_token
from web.api.auth import router as auth_router
from web.api.routes import _controller
from web.api.routes import router as api_router
from web.api.websocket import push_telemetry
from web.api.websocket import router as ws_router

logger = logging.getLogger(__name__)

# ──────────────────── App ────────────────────

app = FastAPI(
    title="ST3215 Robot Control API",
    description=(
        "Web interface for 6-axis robot manipulator control.\n\n"
        "## Authentication\n"
        "1. POST `/auth/login` → получите JWT токен\n"
        "2. Используйте `Authorization: Bearer <token>` для защищённых эндпоинтов\n"
        "3. Для machine-to-machine: POST `/auth/token/generate` → API-токен\n\n"
        "## UDP Telemetry\n"
        "Позиции моторов транслируются по UDP на порт **5005** каждые 50 мс.\n"
        'Формат: JSON `{"type": "motor_positions", "motors": {...}, "ts": float}`'
    ),
    version="2.0.0",
)

# ──────────────────── Роутеры ────────────────────

app.include_router(auth_router, prefix="/auth")
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

_STATIC = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC):
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(os.path.join(_STATIC, "index.html"))


# ──────────────────── ML Tracking эндпоинты ────────────────────

_ml_service = None  # инициализируется лениво


@app.get("/api/ml/status")
async def ml_status():
    """Статус ML-трекера (публичный)."""
    if _ml_service is None:
        return {"running": False, "message": "ML service not initialized"}
    state = _ml_service.get_state()
    return {
        "running": state.is_running,
        "model": state.model_name,
        "fps": state.fps,
        "frames": state.frame_count,
        "detection": state.last_detection.to_dict() if state.last_detection else None,
    }


@app.post("/api/ml/start")
async def ml_start(
    model_path: str = "weights/best.pt",
    camera_id: int = 0,
    target_class: str | None = None,
    auto_control: bool = False,
    _payload: dict = Depends(require_token),
):
    """
    Запустить ML-трекинг (требует токен).

    Параметры:
        model_path: путь к .pt файлу YOLO/PyTorch
        camera_id: индекс камеры
        target_class: класс объекта для фильтрации (или None = любой)
        auto_control: автоматически двигать робота
    """
    global _ml_service

    if _ml_service and _ml_service.get_state().is_running:
        return {"status": "already_running"}

    try:
        from app.models.ml_model_manager import (
            AIRobotController,
            FineTunedVisionModel,
            VisionModelManager,
        )
        from app.services.ml_tracking_service import MLTrackingService
        from web.api.routes import _controller as ctrl

        manager = VisionModelManager()
        model = FineTunedVisionModel(
            name="robot_picker",
            model_path=model_path,
            target_class=target_class,
        )
        manager.register(model)
        ok = manager.set_active("robot_picker")

        if not ok:
            return {"status": "error", "detail": f"Failed to load model: {model_path}"}

        ai_ctrl = AIRobotController(manager)
        _ml_service = MLTrackingService(
            robot_service=ctrl,
            ai_controller=ai_ctrl,
            camera_id=camera_id,
            auto_control=auto_control,
        )
        _ml_service.start()
        return {"status": "started", "model": model_path, "camera": camera_id}

    except Exception as e:
        logger.exception("ml_start failed: %s", e)
        return {"status": "error", "detail": str(e)}


@app.post("/api/ml/stop")
async def ml_stop(_payload: dict = Depends(require_token)):
    """Остановить ML-трекинг (требует токен)."""
    global _ml_service
    if _ml_service:
        _ml_service.stop()
        _ml_service = None
    return {"status": "stopped"}


# ──────────────────── UDP Motor Telemetry ────────────────────


class UDPMotorBroadcaster:
    """
    Постоянная UDP-трансляция позиций моторов.

    Клиент:
        import socket, json
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", 5005))
        while True:
            data, addr = sock.recvfrom(4096)
            msg = json.loads(data)
            print(msg["motors"])
    """

    def __init__(
        self,
        broadcast_addr: str = "255.255.255.255",
        port: int = 5005,
        interval: float = 0.05,  # 20 Hz
    ):
        self._addr = broadcast_addr
        self._port = port
        self._interval = interval
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="udp-broadcast")
        self._thread.start()
        logger.info(
            "UDP broadcaster started → %s:%d @ %.0f Hz", self._addr, self._port, 1 / self._interval
        )

    def stop(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("UDP broadcaster stopped")

    def _loop(self) -> None:
        from web.api.routes import _controller as ctrl

        while self._running:
            try:
                motors: dict[str, Any] = {}

                if ctrl and ctrl.is_connected:
                    for mid in ctrl.get_connected_motors():
                        data = ctrl.get_motor_data(mid)
                        if data:
                            motors[str(mid)] = {
                                "position": data.position,
                                "temperature": data.temperature,
                                "voltage": data.voltage,
                                "current": data.current,
                                "load": data.load,
                            }

                payload = json.dumps(
                    {
                        "type": "motor_positions",
                        "motors": motors,
                        "ts": time.time(),
                        "connected": bool(ctrl and ctrl.is_connected),
                    }
                ).encode()

                if self._sock:
                    self._sock.sendto(payload, (self._addr, self._port))

            except Exception as e:
                logger.debug("UDP broadcast error: %s", e)

            time.sleep(self._interval)


_udp_broadcaster = UDPMotorBroadcaster()


# ──────────────────── WebSocket телеметрия ────────────────────


async def _ws_telemetry_loop() -> None:
    """Фоновая задача: читает данные моторов и пушит в WebSocket клиентов."""
    from web.api.routes import _controller as ctrl

    while True:
        try:
            motors: dict[str, Any] = {}
            if ctrl and ctrl.is_connected:
                for mid in ctrl.get_connected_motors():
                    data = ctrl.get_motor_data(mid)
                    if data:
                        motors[str(mid)] = {
                            "position": data.position,
                            "temperature": data.temperature,
                            "voltage": data.voltage,
                            "current": data.current,
                            "load": data.load,
                            "status": data.status.value
                            if hasattr(data.status, "value")
                            else str(data.status),
                        }
            if motors:
                await push_telemetry(motors)
        except Exception as e:
            logger.debug("WS telemetry error: %s", e)
        await asyncio.sleep(0.2)  # 5 Hz


# ──────────────────── Lifecycle ────────────────────


@app.on_event("startup")
async def _startup():
    logger.info("🚀 Robot Control API v2.0 starting up...")

    # UDP broadcaster
    _udp_broadcaster.start()

    # WebSocket telemetry background task
    asyncio.create_task(_ws_telemetry_loop())

    logger.info("✅ Startup complete")
    logger.info("   Run:  python main.py [--no-auth] [--mock]  # for no-auth + mock mode")
    logger.info("   Auth: POST /auth/login  (admin/admin by default)")
    logger.info("   Docs: http://localhost:8000/docs")
    logger.info("   UDP:  port 5005 (motor positions @ 20 Hz)")


@app.on_event("shutdown")
async def _shutdown():
    logger.info("🛑 Shutting down...")
    _udp_broadcaster.stop()
    if _ml_service:
        _ml_service.stop()
    logger.info("👋 Goodbye")


# ──────────────────── Entry point ────────────────────

if __name__ == "__main__":
    import argparse
    import uvicorn

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Robot Control API")
    parser.add_argument("--no-auth", action="store_true", help="Disable authentication")
    parser.add_argument("--no-auth-secret", type=str, default="", help="Secret for no-auth mode")
    parser.add_argument("--mock", action="store_true", help="Use mock motor controller (for development)")
    parser.add_argument("--host", type=str, default="", help="Host to bind to")
    parser.add_argument("--port", type=int, default=0, help="Port to bind to")
    args, _ = parser.parse_known_args()

    if args.no_auth:
        os.environ["AUTH_ENABLED"] = "false"
        os.environ["NO_AUTH_SECRET"] = args.no_auth_secret or os.environ.get("NO_AUTH_SECRET", "dev-secret")
        logging.info("🔓 Auth disabled (--no-auth)")

    no_auth_secret = os.environ.get("NO_AUTH_SECRET", "")
    if no_auth_secret:
        logging.info("🔐 Limited auth mode active")

    if args.mock:
        os.environ["MOCK_MODE"] = "true"
        logging.info("🎭 Mock motor controller enabled (--mock)")

    host = args.host or os.environ.get("HOST", "0.0.0.0")
    port = args.port or int(os.environ.get("PORT", "8000"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.info(f"🚀 Starting server on {host}:{port}")
    uvicorn.run("web.main:app", host=host, port=port, reload=False)
