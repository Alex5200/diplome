#!/usr/bin/env python3

"""
Vision Tracker Service — визуальное слежение за объектом через AI (VLM).

Архитектура:
    Камера (OpenCV) → Кадр → AI Provider (Ollama/LM Studio/OpenAI) → Координаты объекта
    → PID-контроллер → Команды суставов → Робот следует за объектом

Поддерживаемые бэкенды:
    - Ollama + Qwen VL (локально)
    - LM Studio + любая VLM (локально/удалённо)
    - OpenAI GPT-4o (облако)
    - Любой OpenAI-compatible API

Использование:
    from app.services.ai_provider import AIProvider
    from app.services.vision_tracker_service import VisionTrackerService

    ai = AIProvider.ollama(model="qwen2.5-vl")
    # или: ai = AIProvider.lm_studio(url="http://192.168.1.100:1234/v1")

    tracker = VisionTrackerService(robot_service, kinematics_service, ai)
    tracker.configure(target_label="красный мяч")
    tracker.start_tracking()

Требования:
    pip install opencv-python requests numpy
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from ..core.base_service import BaseService
from .ai_provider import AIProvider

logger = logging.getLogger(__name__)

# ──────────────────── Настройки ────────────────────

DEFAULT_CAMERA_ID = 0
DEFAULT_FPS = 10
DEFAULT_VLM_INTERVAL = 0.5  # секунд между VLM запросами
DEFAULT_FRAME_W = 640
DEFAULT_FRAME_H = 480


# ──────────────────── Данные ────────────────────


@dataclass
class TrackingTarget:
    """Результат детекции от VLM."""

    found: bool = False
    label: str = ""
    cx: float = 0.5  # нормализованный центр X (0..1)
    cy: float = 0.5  # нормализованный центр Y (0..1)
    width: float = 0.0
    height: float = 0.0
    raw_response: str = ""


@dataclass
class TrackerState:
    """Полное состояние трекера."""

    is_tracking: bool = False
    target: TrackingTarget = field(default_factory=TrackingTarget)
    target_label: str = "red ball"
    current_angles: list[float] = field(default_factory=lambda: [0.0] * 6)
    error_x: float = 0.0  # отклонение от центра кадра
    error_y: float = 0.0
    fps: float = 0.0
    vlm_latency: float = 0.0
    frame_count: int = 0
    ai_provider_info: str = ""


# ──────────────────── PID ────────────────────


class SimplePID:
    """PID-контроллер для плавного слежения."""

    def __init__(
        self, kp: float = 1.0, ki: float = 0.0, kd: float = 0.1, output_limit: float = 30.0
    ):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = time.time()

    def update(self, error: float) -> float:
        now = time.time()
        dt = max(now - self._last_time, 0.001)
        self._last_time = now

        self._integral = max(
            -self.output_limit, min(self.output_limit, self._integral + error * dt)
        )
        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        output = self.kp * error + self.ki * self._integral + self.kd * derivative
        return max(-self.output_limit, min(self.output_limit, output))

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = time.time()


# ──────────────────── Промпты для VLM ────────────────────

DETECTION_PROMPT = """Look at this image. Find the object: "{target}".
If you see it, respond ONLY with JSON (no other text):
{{"found": true, "label": "{target}", "bbox": [x1, y1, x2, y2]}}
Coordinates are normalized 0.0-1.0 (fraction of image size).
x1,y1 = top-left, x2,y2 = bottom-right.

If NOT visible, respond: {{"found": false}}"""


# ──────────────────── Основной сервис ────────────────────


class VisionTrackerService(BaseService):
    """
    Визуальное слежение за объектом через VLM + PID управление роботом.

    Три параллельных потока:
        1. Capture — захват кадров с камеры (10+ FPS)
        2. VLM — отправка кадров в AI модель (~2 FPS, зависит от модели)
        3. Control — PID контур управления суставами робота (20 Hz)
    """

    def __init__(self, robot_service, kinematics_service, ai_provider: AIProvider):
        """
        Args:
            robot_service: RobotService для управления моторами
            kinematics_service: KinematicsService для кинематики
            ai_provider: AIProvider (Ollama / LM Studio / OpenAI / ...)
        """
        super().__init__("VisionTrackerService")

        self.robot = robot_service
        self.kin = kinematics_service
        self.ai = ai_provider

        # Камера
        self._camera_id = DEFAULT_CAMERA_ID
        self._cap: cv2.VideoCapture | None = None
        self._frame_w = DEFAULT_FRAME_W
        self._frame_h = DEFAULT_FRAME_H

        # Состояние
        self._tracker_state = TrackerState()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        # Потоки
        self._capture_thread: threading.Thread | None = None
        self._vlm_thread: threading.Thread | None = None
        self._control_thread: threading.Thread | None = None

        # Последний кадр
        self._current_frame: np.ndarray | None = None
        self._frame_lock = threading.Lock()

        # PID (J1 = pan/горизонт, J2 = tilt/вертикаль)
        self._pid_pan = SimplePID(kp=25.0, ki=0.5, kd=3.0, output_limit=15.0)
        self._pid_tilt = SimplePID(kp=20.0, ki=0.3, kd=2.5, output_limit=10.0)

        # Настройки
        self._vlm_interval = DEFAULT_VLM_INTERVAL
        self._control_rate = 20  # Гц

        # Callbacks
        self._frame_callback = None
        self._state_callback = None

    # ──────────── Конфигурация ────────────

    def configure(
        self,
        target_label: str = "red ball",
        camera_id: int = 0,
        vlm_interval: float = DEFAULT_VLM_INTERVAL,
        pid_pan: tuple[float, float, float] | None = None,
        pid_tilt: tuple[float, float, float] | None = None,
        frame_size: tuple[int, int] | None = None,
    ):
        """
        Настройка трекера.

        Args:
            target_label: Объект для слежения ("red ball", "hand", "face", ...)
            camera_id: OpenCV camera ID
            vlm_interval: Секунды между VLM запросами (меньше = точнее, но больше нагрузка)
            pid_pan: (Kp, Ki, Kd) горизонтальное вращение J1
            pid_tilt: (Kp, Ki, Kd) вертикальный наклон J2
            frame_size: (width, height) разрешение камеры
        """
        self._tracker_state.target_label = target_label
        self._camera_id = camera_id
        self._vlm_interval = vlm_interval

        if pid_pan:
            self._pid_pan = SimplePID(*pid_pan)
        if pid_tilt:
            self._pid_tilt = SimplePID(*pid_tilt)
        if frame_size:
            self._frame_w, self._frame_h = frame_size

        logger.info(
            "Tracker configured: target='%s', camera=%d, ai=%s", target_label, camera_id, self.ai
        )

    def set_ai_provider(self, ai: AIProvider):
        """Сменить AI провайдер на лету (например Ollama → LM Studio)."""
        self.ai = ai
        logger.info("AI provider switched to: %s", ai)

    def set_frame_callback(self, callback):
        """Callback для получения кадров с overlay (для GUI)."""
        self._frame_callback = callback

    def set_state_callback(self, callback):
        """Callback для обновлений состояния трекера."""
        self._state_callback = callback

    # ──────────── Жизненный цикл ────────────

    def _do_initialize(self) -> bool:
        # Проверка AI
        if not self.ai.is_available():
            logger.error("AI provider недоступен: %s", self.ai)
            return False

        # Проверка камеры
        cap = cv2.VideoCapture(self._camera_id)
        if not cap.isOpened():
            logger.error("Камера %d недоступна", self._camera_id)
            cap.release()
            return False
        cap.release()

        with self._lock:
            self._tracker_state.ai_provider_info = repr(self.ai)

        self._emit_event("vision_tracker_initialized", self.ai.get_config())
        return True

    def _do_start(self) -> None:
        self._stop_event.clear()
        self._open_camera()

        self._capture_thread = threading.Thread(
            target=self._capture_loop, name="vt-capture", daemon=True
        )
        self._vlm_thread = threading.Thread(target=self._vlm_loop, name="vt-vlm", daemon=True)
        self._control_thread = threading.Thread(
            target=self._control_loop, name="vt-control", daemon=True
        )

        self._capture_thread.start()
        self._vlm_thread.start()
        self._control_thread.start()

        with self._lock:
            self._tracker_state.is_tracking = True

        self._emit_event("tracking_started", {"target": self._tracker_state.target_label})

    def _do_stop(self) -> None:
        self._stop_event.set()
        for t in (self._capture_thread, self._vlm_thread, self._control_thread):
            if t and t.is_alive():
                t.join(timeout=3.0)
        self._close_camera()

        with self._lock:
            self._tracker_state.is_tracking = False

        self._pid_pan.reset()
        self._pid_tilt.reset()
        self._emit_event("tracking_stopped", {})

    def _get_extra_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "is_tracking": self._tracker_state.is_tracking,
                "target": self._tracker_state.target_label,
                "found": self._tracker_state.target.found,
                "error": (self._tracker_state.error_x, self._tracker_state.error_y),
                "vlm_latency": self._tracker_state.vlm_latency,
                "fps": self._tracker_state.fps,
                "ai": repr(self.ai),
            }

    # ──────────── Камера ────────────

    def _open_camera(self):
        self._cap = cv2.VideoCapture(self._camera_id)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._frame_w)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._frame_h)
        self._cap.set(cv2.CAP_PROP_FPS, DEFAULT_FPS)

    def _close_camera(self):
        if self._cap:
            self._cap.release()
            self._cap = None

    def _capture_loop(self):
        fps_count = 0
        fps_t = time.time()

        while not self._stop_event.is_set():
            if not self._cap or not self._cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            with self._frame_lock:
                self._current_frame = frame.copy()

            fps_count += 1
            if time.time() - fps_t >= 1.0:
                with self._lock:
                    self._tracker_state.fps = fps_count
                    self._tracker_state.frame_count += fps_count
                fps_count = 0
                fps_t = time.time()

            if self._frame_callback:
                self._frame_callback(self._draw_overlay(frame))

            time.sleep(1.0 / DEFAULT_FPS)

    # ──────────── VLM поток ────────────

    def _vlm_loop(self):
        """Периодически отправляет кадр в VLM и обновляет target."""
        while not self._stop_event.is_set():
            with self._frame_lock:
                frame = self._current_frame.copy() if self._current_frame is not None else None

            if frame is not None:
                target = self._detect_object(frame)
                with self._lock:
                    self._tracker_state.target = target
                    if target.found:
                        self._tracker_state.error_x = target.cx - 0.5
                        self._tracker_state.error_y = target.cy - 0.5

                if self._state_callback:
                    self._state_callback(self._tracker_state)

            self._stop_event.wait(self._vlm_interval)

    def _detect_object(self, frame: np.ndarray) -> TrackingTarget:
        """Отправить кадр в AI и получить координаты объекта."""
        prompt = DETECTION_PROMPT.format(target=self._tracker_state.target_label)
        response = self.ai.chat_json(prompt, images=[frame])

        if not response.success:
            logger.warning("VLM error: %s", response.error)
            return TrackingTarget(found=False, raw_response=response.error)

        with self._lock:
            self._tracker_state.vlm_latency = response.latency

        data = response.json_data
        if not data or not data.get("found"):
            return TrackingTarget(found=False, raw_response=response.content)

        bbox = data.get("bbox", [0, 0, 1, 1])
        if len(bbox) != 4:
            return TrackingTarget(found=False, raw_response=response.content)

        x1, y1, x2, y2 = [max(0.0, min(1.0, float(v))) for v in bbox]

        return TrackingTarget(
            found=True,
            label=data.get("label", self._tracker_state.target_label),
            cx=(x1 + x2) / 2,
            cy=(y1 + y2) / 2,
            width=abs(x2 - x1),
            height=abs(y2 - y1),
            raw_response=response.content,
        )

    # ──────────── Control поток ────────────

    def _control_loop(self):
        """PID контур: ошибка → корректировка J1 (pan) и J2 (tilt)."""
        dt = 1.0 / self._control_rate

        while not self._stop_event.is_set():
            with self._lock:
                target = self._tracker_state.target
                error_x = self._tracker_state.error_x
                error_y = self._tracker_state.error_y

            if target.found and self.robot.is_connected:
                delta_pan = self._pid_pan.update(error_x)
                delta_tilt = self._pid_tilt.update(error_y)

                current = self.robot.get_joint_angles()
                new_angles = list(current)
                new_angles[0] = self._clamp(current[0] - delta_pan)  # pan
                new_angles[1] = self._clamp(current[1] - delta_tilt)  # tilt

                self.robot.move_joints(new_angles, speed=800)

                with self._lock:
                    self._tracker_state.current_angles = new_angles
            else:
                self._pid_pan.reset()
                self._pid_tilt.reset()

            self._stop_event.wait(dt)

    @staticmethod
    def _clamp(angle: float, limit: float = 150.0) -> float:
        return max(-limit, min(limit, angle))

    # ──────────── Overlay ────────────

    def _draw_overlay(self, frame: np.ndarray) -> np.ndarray:
        overlay = frame.copy()
        h, w = overlay.shape[:2]

        with self._lock:
            target = self._tracker_state.target
            err_x = self._tracker_state.error_x
            err_y = self._tracker_state.error_y
            latency = self._tracker_state.vlm_latency

        # Перекрестие
        cx, cy = w // 2, h // 2
        cv2.line(overlay, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 1)
        cv2.line(overlay, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 1)

        if target.found:
            bx1 = int((target.cx - target.width / 2) * w)
            by1 = int((target.cy - target.height / 2) * h)
            bx2 = int((target.cx + target.width / 2) * w)
            by2 = int((target.cy + target.height / 2) * h)
            cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (0, 255, 0), 2)

            obj_cx, obj_cy = int(target.cx * w), int(target.cy * h)
            cv2.circle(overlay, (obj_cx, obj_cy), 6, (0, 0, 255), -1)
            cv2.line(overlay, (cx, cy), (obj_cx, obj_cy), (0, 255, 255), 1)

            cv2.putText(
                overlay,
                f"{target.label}",
                (bx1, by1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
        else:
            cv2.putText(
                overlay, "TARGET NOT FOUND", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
            )

        # Статус
        info = f"VLM: {latency:.1f}s | err: ({err_x:+.2f}, {err_y:+.2f}) | {repr(self.ai)[:40]}"
        cv2.putText(overlay, info, (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)

        return overlay

    # ──────────── Публичный API ────────────

    def start_tracking(self, target_label: str | None = None):
        """Запустить слежение."""
        if target_label:
            self._tracker_state.target_label = target_label
        self.initialize()
        self.start()

    def stop_tracking(self):
        """Остановить слежение."""
        self.stop()

    def set_target(self, label: str):
        """Сменить объект на лету."""
        with self._lock:
            self._tracker_state.target_label = label
        self._pid_pan.reset()
        self._pid_tilt.reset()
        logger.info("Target → %s", label)

    def get_tracker_state(self) -> TrackerState:
        """Получить состояние трекера."""
        with self._lock:
            return TrackerState(
                is_tracking=self._tracker_state.is_tracking,
                target=self._tracker_state.target,
                target_label=self._tracker_state.target_label,
                current_angles=list(self._tracker_state.current_angles),
                error_x=self._tracker_state.error_x,
                error_y=self._tracker_state.error_y,
                fps=self._tracker_state.fps,
                vlm_latency=self._tracker_state.vlm_latency,
                frame_count=self._tracker_state.frame_count,
                ai_provider_info=repr(self.ai),
            )

    def get_current_frame(self) -> np.ndarray | None:
        """Получить кадр с overlay."""
        with self._frame_lock:
            if self._current_frame is not None:
                return self._draw_overlay(self._current_frame)
        return None


# ──────────────────── Standalone ────────────────────


def run_standalone(
    port: str = "/dev/ttyUSB0",
    target: str = "red ball",
    camera_id: int = 0,
    provider: str = "ollama",
    model: str = "qwen2.5-vl",
    server_url: str = "",
):
    """
    Запуск в standalone режиме (без GUI).

    python -m app.services.vision_tracker_service \\
        --provider ollama --model qwen2.5-vl --target "red ball"

    python -m app.services.vision_tracker_service \\
        --provider lm_studio --server http://192.168.1.100:1234/v1 \\
        --model qwen2.5-vl-7b --target "hand"
    """
    from .kinematics_service import KinematicsService
    from .robot_service import RobotService

    print("=" * 60)
    print("  VISION TRACKER — AI Object Following")
    print("=" * 60)

    # AI провайдер
    if provider == "ollama":
        ai = AIProvider.ollama(model=model, url=server_url or "http://localhost:11434")
    elif provider == "lm_studio":
        ai = AIProvider.lm_studio(url=server_url or "http://localhost:1234/v1", model=model)
    elif provider == "openai":
        import os

        ai = AIProvider.openai(api_key=os.environ.get("OPENAI_API_KEY", ""), model=model)
    else:
        ai = AIProvider.custom(url=server_url, model=model)

    print(f"[+] AI: {ai}")
    if not ai.is_available():
        print("[!] AI provider недоступен!")
        models = ai.list_models()
        print(f"    Доступные модели: {models}")
        return

    print(f"[+] Модели: {ai.list_models()}")

    # Робот
    robot = RobotService()
    robot.initialize()
    print(f"[+] Подключение к {port}...")
    if not robot.connect(port):
        print("[!] Не удалось подключиться!")
        return

    kin = KinematicsService()
    kin.initialize()

    # Трекер
    tracker = VisionTrackerService(robot, kin, ai)
    tracker.configure(target_label=target, camera_id=camera_id)

    print(f"[+] Слежение за: '{target}'")
    print("[+] Клавиши: q=выход, t=новый объект, s=сменить провайдер")
    print()

    tracker.start_tracking()

    try:
        while True:
            frame = tracker.get_current_frame()
            if frame is not None:
                cv2.imshow("Vision Tracker", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("t"):
                    new_target = input("New target: ").strip()
                    if new_target:
                        tracker.set_target(new_target)
                elif key == ord("s"):
                    print("\nСмена провайдера:")
                    print("  1) Ollama (local)")
                    print("  2) LM Studio (remote)")
                    print("  3) OpenAI")
                    choice = input("Выбор: ").strip()
                    if choice == "1":
                        new_model = input("Model [qwen2.5-vl]: ").strip() or "qwen2.5-vl"
                        tracker.set_ai_provider(AIProvider.ollama(model=new_model))
                    elif choice == "2":
                        url = (
                            input("URL [http://localhost:1234/v1]: ").strip()
                            or "http://localhost:1234/v1"
                        )
                        new_model = input("Model: ").strip() or model
                        tracker.set_ai_provider(AIProvider.lm_studio(url=url, model=new_model))
                    elif choice == "3":
                        key = input("API Key: ").strip()
                        tracker.set_ai_provider(AIProvider.openai(api_key=key))
            else:
                time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[+] Остановка...")
        tracker.stop_tracking()
        robot.disconnect()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vision Tracker with AI")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--target", default="red ball")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument(
        "--provider", choices=["ollama", "lm_studio", "openai", "custom"], default="ollama"
    )
    parser.add_argument("--model", default="qwen2.5-vl")
    parser.add_argument("--server", default="", help="Server URL (for lm_studio/custom)")
    args = parser.parse_args()

    run_standalone(
        port=args.port,
        target=args.target,
        camera_id=args.camera,
        provider=args.provider,
        model=args.model,
        server_url=args.server,
    )
