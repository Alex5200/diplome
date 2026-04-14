#!/usr/bin/env python3
"""
ML Tracking Service — сервис отслеживания объектов через локальные ML-модели.

Расширяет возможности VisionTrackerService (VLM через API) добавляя:
    - Работу с локальными моделями (YOLO, PyTorch custom)
    - ИИ-прослойку для авто-управления роботом
    - Параллельный режим: VLM для идентификации + ML для трекинга

Использование:
    from app.models.ml_model_manager import FineTunedVisionModel, VisionModelManager, AIRobotController
    from app.services.ml_tracking_service import MLTrackingService

    manager = VisionModelManager()
    manager.register(FineTunedVisionModel("picker", "weights/best.pt", target_class="cup"))
    manager.set_active("picker")

    ai_ctrl = AIRobotController(manager)
    svc = MLTrackingService(robot_service, ai_ctrl)
    svc.start()
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from ..core.base_service import BaseService
from ..models.ml_model_manager import AIRobotController, DetectionResult, RobotCommand

logger = logging.getLogger(__name__)

DEFAULT_CAMERA_ID = 0
DEFAULT_FPS = 15
DEFAULT_FRAME_W = 640
DEFAULT_FRAME_H = 480


@dataclass
class MLTrackerState:
    """Состояние ML-трекера."""

    is_running: bool = False
    camera_id: int = 0
    fps: float = 0.0
    frame_count: int = 0
    last_detection: DetectionResult | None = None
    last_command: RobotCommand | None = None
    model_name: str = ""
    error: str = ""


class MLTrackingService(BaseService):
    """
    Сервис ML-трекинга с ИИ-управлением роботом.

    Поток обработки:
        Camera → _capture_loop → frame → AIRobotController.process_frame
        → RobotCommand → robot.move_joints (если auto_control=True)
        → frame_callback (для GUI)
    """

    def __init__(
        self,
        robot_service,
        ai_controller: AIRobotController,
        camera_id: int = DEFAULT_CAMERA_ID,
        auto_control: bool = True,
    ):
        """
        Args:
            robot_service: RobotService для управления моторами
            ai_controller: AIRobotController с загруженной ML-моделью
            camera_id: индекс камеры OpenCV
            auto_control: если True — автоматически отправлять команды на робота
        """
        super().__init__("MLTrackingService")

        self.robot = robot_service
        self.ai_ctrl = ai_controller
        self._camera_id = camera_id
        self._auto_control = auto_control

        # Камера
        self._cap: cv2.VideoCapture | None = None
        self._frame_w = DEFAULT_FRAME_W
        self._frame_h = DEFAULT_FRAME_H

        # Состояние
        self._state = MLTrackerState(camera_id=camera_id)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        # Поток захвата
        self._capture_thread: threading.Thread | None = None

        # Callbacks
        self._frame_callback: Callable[[np.ndarray], None] | None = None
        self._state_callback: Callable[[MLTrackerState], None] | None = None
        self._command_callback: Callable[[RobotCommand], None] | None = None

    # ────────── Конфигурация ──────────

    def configure(
        self,
        camera_id: int | None = None,
        auto_control: bool | None = None,
        frame_size: tuple[int, int] | None = None,
    ) -> None:
        if camera_id is not None:
            self._camera_id = camera_id
            self._state.camera_id = camera_id
        if auto_control is not None:
            self._auto_control = auto_control
        if frame_size is not None:
            self._frame_w, self._frame_h = frame_size

    def set_frame_callback(self, cb: Callable[[np.ndarray], None]) -> None:
        """Callback вызывается на каждом кадре с overlay."""
        self._frame_callback = cb

    def set_state_callback(self, cb: Callable[[MLTrackerState], None]) -> None:
        """Callback вызывается при обновлении состояния."""
        self._state_callback = cb

    def set_command_callback(self, cb: Callable[[RobotCommand], None]) -> None:
        """Callback вызывается при каждой команде робота."""
        self._command_callback = cb

    # ────────── Жизненный цикл ──────────

    def _do_initialize(self) -> bool:
        if self.ai_ctrl.manager.active_model is None:
            logger.error("No active ML model in AIRobotController")
            return False

        cap = cv2.VideoCapture(self._camera_id)
        if not cap.isOpened():
            logger.error("Camera %d not available", self._camera_id)
            cap.release()
            return False
        cap.release()

        with self._lock:
            self._state.model_name = self.ai_ctrl.manager._active_name or ""

        return True

    def _do_start(self) -> None:
        self._stop_event.clear()
        self._open_camera()

        self._capture_thread = threading.Thread(
            target=self._capture_loop, name="ml-capture", daemon=True
        )
        self._capture_thread.start()

        with self._lock:
            self._state.is_running = True

        logger.info(
            "MLTrackingService started (model=%s, cam=%d, auto=%s)",
            self._state.model_name,
            self._camera_id,
            self._auto_control,
        )

    def _do_stop(self) -> None:
        self._stop_event.set()
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=5.0)
        self._close_camera()

        with self._lock:
            self._state.is_running = False

        logger.info("MLTrackingService stopped")

    def _get_extra_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "is_running": self._state.is_running,
                "model": self._state.model_name,
                "fps": self._state.fps,
                "frames": self._state.frame_count,
                "detection": self._state.last_detection.to_dict()
                if self._state.last_detection
                else None,
            }

    # ────────── Камера ──────────

    def _open_camera(self) -> None:
        self._cap = cv2.VideoCapture(self._camera_id)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._frame_w)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._frame_h)
        self._cap.set(cv2.CAP_PROP_FPS, DEFAULT_FPS)

    def _close_camera(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    # ────────── Основной цикл ──────────

    def _capture_loop(self) -> None:
        fps_count = 0
        fps_t = time.time()

        while not self._stop_event.is_set():
            if not self._cap or not self._cap.isOpened():
                time.sleep(0.05)
                continue

            ret, frame_bgr = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            # Конвертируем BGR → RGB для модели
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            # ── ML предсказание ──
            command = self.ai_ctrl.process_frame(frame_rgb)
            detection = self.ai_ctrl.last_detection

            with self._lock:
                self._state.last_detection = detection
                self._state.last_command = command
                self._state.frame_count += 1

            # ── Авто-управление роботом ──
            if self._auto_control and command.description != "idle":
                self._apply_command(command)

            # ── Callbacks ──
            if self._command_callback:
                self._command_callback(command)

            if self._state_callback:
                with self._lock:
                    self._state_callback(self._state)

            # ── Overlay и отправка в GUI ──
            if self._frame_callback:
                overlay = self._draw_overlay(frame_bgr, detection, command)
                self._frame_callback(overlay)

            # ── FPS счётчик ──
            fps_count += 1
            if time.time() - fps_t >= 1.0:
                with self._lock:
                    self._state.fps = fps_count
                fps_count = 0
                fps_t = time.time()

            time.sleep(1.0 / DEFAULT_FPS)

    # ────────── Управление роботом ──────────

    def _apply_command(self, command: RobotCommand) -> None:
        """Применить команду робота (суставы + gripper)."""
        try:
            if not self.robot.is_connected:
                return

            current = self.robot.get_joint_angles()
            new_angles = [c + d for c, d in zip(current, command.joint_deltas)]
            self.robot.move_joints(new_angles, speed=command.speed)

            if command.gripper_open is not None:
                # Предполагаем что gripper — последний сустав или отдельный метод
                if hasattr(self.robot, "set_gripper"):
                    self.robot.set_gripper(command.gripper_open)

        except Exception as e:
            logger.exception("apply_command failed: %s", e)
            with self._lock:
                self._state.error = str(e)

    # ────────── Overlay ──────────

    def _draw_overlay(
        self,
        frame_bgr: np.ndarray,
        detection: DetectionResult | None,
        command: RobotCommand | None,
    ) -> np.ndarray:
        overlay = frame_bgr.copy()
        h, w = overlay.shape[:2]

        # Перекрестие центра
        cx, cy = w // 2, h // 2
        cv2.line(overlay, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 1)
        cv2.line(overlay, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 1)

        if detection and detection.found:
            # Bounding box
            if detection.bbox and len(detection.bbox) == 4:
                x1 = int(detection.bbox[0] * w)
                y1 = int(detection.bbox[1] * h)
                x2 = int(detection.bbox[2] * w)
                y2 = int(detection.bbox[3] * h)
                cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    overlay,
                    f"{detection.label} {detection.confidence:.2f}",
                    (x1, max(y1 - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )

            # Линия к центру
            obj_cx = int(detection.cx * w)
            obj_cy = int(detection.cy * h)
            cv2.circle(overlay, (obj_cx, obj_cy), 5, (0, 0, 255), -1)
            cv2.line(overlay, (cx, cy), (obj_cx, obj_cy), (0, 255, 255), 1)
        else:
            cv2.putText(
                overlay, "NOT FOUND", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
            )

        # Статус команды
        cmd_text = command.description if command else ""
        with self._lock:
            fps = self._state.fps
            lat = detection.latency_ms if detection else 0.0

        info = f"FPS:{fps:.0f} | ML:{lat:.0f}ms | {cmd_text}"
        cv2.putText(overlay, info, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)

        return overlay

    # ────────── Публичный API ──────────

    def start(self) -> None:
        """Запустить ML-трекинг."""
        self.initialize()
        super().start()

    def stop(self) -> None:
        """Остановить ML-трекинг."""
        super().stop()

    def get_state(self) -> MLTrackerState:
        with self._lock:
            return MLTrackerState(
                is_running=self._state.is_running,
                camera_id=self._state.camera_id,
                fps=self._state.fps,
                frame_count=self._state.frame_count,
                last_detection=self._state.last_detection,
                last_command=self._state.last_command,
                model_name=self._state.model_name,
                error=self._state.error,
            )

    def set_auto_control(self, enabled: bool) -> None:
        """Включить/выключить авто-управление роботом."""
        self._auto_control = enabled
        logger.info("auto_control → %s", enabled)
