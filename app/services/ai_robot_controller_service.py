#!/usr/bin/env python3
"""
AI Robot Controller Service — локальный ИИ (Qwen3 VL) управляет роботом.

Архитектура:
    Camera → Frame
        ↓
    Qwen3 VL (Ollama) ← System Prompt (описание робота + текущее состояние)
        ↓
    JSON команда: {"action": "move", "joints": [...], "gripper": 0, "reason": "..."}
        ↓
    Safety Check (лимиты суставов, скорость)
        ↓
    RobotService.move_joints()

Режимы:
    AUTO  — непрерывная петля: камера → ИИ → движение (~1-2 Гц, ограничено VLM)
    STEP  — один шаг по нажатию кнопки
    WATCH — ИИ анализирует, но не двигает (только логирует)

Системный промпт:
    ИИ знает структуру робота (6 DOF + gripper), текущие углы,
    координаты end-effector и видит изображение с камеры.
    Отвечает строго JSON без лишнего текста.

Использование:
    from app.services.ai_provider import AIProvider
    from app.services.ai_robot_controller_service import AIRobotControllerService

    ai = AIProvider.ollama(model="qwen3:8b-q4_K_M")   # или qwen2.5-vl
    svc = AIRobotControllerService(robot_service, kinematics_service, ai)
    svc.set_task("Найди красный предмет и положи его в левый угол")
    svc.start()
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

import cv2
import numpy as np

from ..core.base_service import BaseService
from .ai_provider import AIProvider

logger = logging.getLogger(__name__)

# ──────────────────── Константы ────────────────────

DEFAULT_CAMERA_ID = 0
DEFAULT_FPS = 5  # кадров в секунду захвата
DEFAULT_AI_INTERVAL = 1.5  # секунд между запросами к ИИ
DEFAULT_FRAME_W = 640
DEFAULT_FRAME_H = 480
JOINT_LIMIT_DEG = 150.0  # максимальный угол каждого сустава
MAX_DELTA_PER_STEP = 15.0  # максимальное изменение угла за один шаг (безопасность)
MAX_SPEED = 1000  # максимальная скорость моторов


# ──────────────────── Режимы работы ────────────────────


class ControlMode(Enum):
    AUTO = auto()  # непрерывно: камера → ИИ → движение
    STEP = auto()  # один шаг вручную
    WATCH = auto()  # только анализ, без движения


# ──────────────────── Команда от ИИ ────────────────────


@dataclass
class AICommand:
    """Команда управления роботом, распознанная из ответа ИИ."""

    action: str = "idle"  # move | grip | release | stop | home | idle
    joint_deltas: list[float] = field(default_factory=lambda: [0.0] * 6)
    joint_targets: list[float] | None = None  # если ИИ задал абсолютные углы
    gripper_open: bool | None = None  # None = не менять
    speed: int = 600
    reason: str = ""  # объяснение от ИИ
    confidence: float = 1.0
    raw_response: str = ""
    success: bool = True
    error: str = ""

    def is_safe(self) -> bool:
        """Проверить безопасность команды."""
        for d in self.joint_deltas:
            if abs(d) > MAX_DELTA_PER_STEP:
                return False
        if self.joint_targets:
            for t in self.joint_targets:
                if abs(t) > JOINT_LIMIT_DEG:
                    return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "joint_deltas": [round(d, 2) for d in self.joint_deltas],
            "joint_targets": self.joint_targets,
            "gripper_open": self.gripper_open,
            "speed": self.speed,
            "reason": self.reason,
            "confidence": self.confidence,
            "safe": self.is_safe(),
        }

    @classmethod
    def idle_cmd(cls, reason: str = "") -> "AICommand":
        return cls(action="idle", reason=reason)

    @classmethod
    def error_cmd(cls, error: str) -> "AICommand":
        return cls(action="idle", success=False, error=error)


# ──────────────────── Состояние сервиса ────────────────────


@dataclass
class ControllerState:
    """Снимок состояния AI-контроллера."""

    mode: str = "idle"
    is_running: bool = False
    task: str = ""
    step_count: int = 0
    last_command: AICommand | None = None
    last_ai_latency: float = 0.0
    fps: float = 0.0
    joint_angles: list[float] = field(default_factory=lambda: [0.0] * 6)
    camera_id: int = 0
    ai_model: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "is_running": self.is_running,
            "task": self.task,
            "step_count": self.step_count,
            "last_command": self.last_command.to_dict() if self.last_command else None,
            "latency_s": round(self.last_ai_latency, 3),
            "fps": round(self.fps, 1),
            "joints": [round(a, 1) for a in self.joint_angles],
            "model": self.ai_model,
            "error": self.error,
        }


# ──────────────────── Системный промпт ────────────────────

_SYSTEM_PROMPT = """You are a precise robot arm controller.
The robot is a 6-DOF manipulator with joints J1-J6 and a gripper.

Joint limits: ±150 degrees each.
Joint mapping:
  J1 = base rotation (yaw, left/right)
  J2 = shoulder pitch (forward/back)
  J3 = elbow pitch (up/down)
  J4 = wrist roll
  J5 = wrist pitch (end-effector up/down)
  J6 = end-effector rotation
  Gripper: true=open, false=closed

Your task: {task}

Current joint angles (degrees): {joints}
End-effector position (mm): {ee_pos}

Look at the camera image and decide the next robot action.

Respond ONLY with valid JSON, no other text:
{{
  "action": "move" | "grip" | "release" | "stop" | "home" | "idle",
  "joint_deltas": [dJ1, dJ2, dJ3, dJ4, dJ5, dJ6],
  "gripper_open": true | false | null,
  "speed": 400..1000,
  "reason": "brief explanation",
  "confidence": 0.0..1.0
}}

Rules:
- joint_deltas: small incremental changes, max ±15 degrees per step
- Use "idle" when task is complete or no action needed
- Use "stop" only for emergency
- Be conservative: small safe movements first
- If you cannot see the scene clearly, use "idle" with confidence < 0.3"""


# ──────────────────── Парсер ответа ИИ ────────────────────


def parse_ai_command(response_text: str, raw: str = "") -> AICommand:
    """
    Разобрать JSON-ответ ИИ в AICommand.

    Устойчив к:
    - markdown блокам (```json ... ```)
    - лишнему тексту до/после JSON
    - неполным полям
    """
    from .ai_provider import parse_json_from_text

    data = parse_json_from_text(response_text)
    if not data:
        return AICommand.error_cmd(f"Failed to parse JSON from: {response_text[:100]}")

    action = str(data.get("action", "idle")).lower()
    valid_actions = {"move", "grip", "release", "stop", "home", "idle"}
    if action not in valid_actions:
        action = "idle"

    raw_deltas = data.get("joint_deltas", [0.0] * 6)
    if not isinstance(raw_deltas, list) or len(raw_deltas) != 6:
        raw_deltas = [0.0] * 6

    joint_deltas = [float(max(-MAX_DELTA_PER_STEP, min(MAX_DELTA_PER_STEP, d))) for d in raw_deltas]

    gripper_raw = data.get("gripper_open")
    if gripper_raw is None:
        gripper_open = None
    else:
        gripper_open = bool(gripper_raw)

    speed = int(data.get("speed", 600))
    speed = max(100, min(MAX_SPEED, speed))

    confidence = float(data.get("confidence", 1.0))
    confidence = max(0.0, min(1.0, confidence))

    return AICommand(
        action=action,
        joint_deltas=joint_deltas,
        gripper_open=gripper_open,
        speed=speed,
        reason=str(data.get("reason", "")),
        confidence=confidence,
        raw_response=raw,
        success=True,
    )


# ──────────────────── Основной сервис ────────────────────


class AIRobotControllerService(BaseService):
    """
    Сервис: локальный ИИ (Qwen3 VL) → управление роботом.

    Поток данных:
        Camera capture thread  →  _current_frame
        AI query thread        →  _last_command (каждые ai_interval секунд)
        Execution thread       →  robot.move_joints(...)

    Все три потока используют threading.Event для синхронизации и остановки.
    """

    def __init__(
        self,
        robot_service,
        kinematics_service,
        ai_provider: AIProvider,
        camera_id: int = DEFAULT_CAMERA_ID,
        mode: ControlMode = ControlMode.AUTO,
        ai_interval: float = DEFAULT_AI_INTERVAL,
    ):
        super().__init__("AIRobotControllerService")

        self.robot = robot_service
        self.kin = kinematics_service
        self.ai = ai_provider

        self._camera_id = camera_id
        self._mode = mode
        self._ai_interval = ai_interval

        # Camera
        self._cap: cv2.VideoCapture | None = None
        self._current_frame: np.ndarray | None = None
        self._frame_lock = threading.Lock()

        # State
        self._task = "Explore the scene and describe what you see"
        self._state = ControllerState(ai_model=repr(ai_provider))
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._step_event = threading.Event()  # для режима STEP

        # Threads
        self._capture_thread: threading.Thread | None = None
        self._ai_thread: threading.Thread | None = None

        # History
        self._command_history: list[AICommand] = []
        self._max_history = 50

        # Callbacks
        self._frame_callback: Callable[[np.ndarray], None] | None = None
        self._command_callback: Callable[[AICommand], None] | None = None
        self._state_callback: Callable[[ControllerState], None] | None = None
        self._log_callback: Callable[[str, str], None] | None = None

    # ─── Конфигурация ───

    def set_task(self, task: str) -> None:
        """Задать задачу для ИИ (что делать роботу)."""
        with self._state_lock:
            self._task = task
            self._state.task = task
        self._log(f"Task set: {task}", "info")

    def set_mode(self, mode: ControlMode) -> None:
        """Сменить режим работы."""
        self._mode = mode
        with self._state_lock:
            self._state.mode = mode.name.lower()
        self._log(f"Mode → {mode.name}", "info")

    def set_ai_provider(self, ai: AIProvider) -> None:
        """Сменить AI-провайдер на лету."""
        self.ai = ai
        with self._state_lock:
            self._state.ai_model = repr(ai)

    def set_camera(self, camera_id: int) -> None:
        self._camera_id = camera_id

    def set_ai_interval(self, seconds: float) -> None:
        self._ai_interval = max(0.5, seconds)

    # ─── Callbacks ───

    def set_frame_callback(self, cb: Callable[[np.ndarray], None]) -> None:
        self._frame_callback = cb

    def set_command_callback(self, cb: Callable[[AICommand], None]) -> None:
        self._command_callback = cb

    def set_state_callback(self, cb: Callable[[ControllerState], None]) -> None:
        self._state_callback = cb

    def set_log_callback(self, cb: Callable[[str, str], None]) -> None:
        """cb(message, level) — для вывода в GUI лог."""
        self._log_callback = cb

    # ─── Lifecycle (BaseService) ───

    def _do_initialize(self) -> bool:
        if not self.ai.is_available():
            logger.error("AI provider not available: %s", self.ai)
            return False
        cap = cv2.VideoCapture(self._camera_id)
        ok = cap.isOpened()
        cap.release()
        if not ok:
            logger.error("Camera %d not available", self._camera_id)
            return False
        return True

    def _do_start(self) -> None:
        self._stop_event.clear()
        self._open_camera()

        self._capture_thread = threading.Thread(
            target=self._capture_loop, name="ai-capture", daemon=True
        )
        self._ai_thread = threading.Thread(target=self._ai_loop, name="ai-query", daemon=True)

        self._capture_thread.start()
        self._ai_thread.start()

        with self._state_lock:
            self._state.is_running = True
            self._state.mode = self._mode.name.lower()

        self._log(
            f"AI Robot Controller started (mode={self._mode.name}, model={self._state.ai_model})",
            "success",
        )

    def _do_stop(self) -> None:
        self._stop_event.set()
        self._step_event.set()  # разбудить если ждём шага
        for t in (self._capture_thread, self._ai_thread):
            if t and t.is_alive():
                t.join(timeout=5.0)
        self._close_camera()
        with self._state_lock:
            self._state.is_running = False
        self._log("AI Robot Controller stopped", "warning")

    def _get_extra_status(self) -> dict[str, Any]:
        with self._state_lock:
            return self._state.to_dict()

    # ─── Camera ───

    def _open_camera(self) -> None:
        self._cap = cv2.VideoCapture(self._camera_id)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_FRAME_W)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_FRAME_H)
        self._cap.set(cv2.CAP_PROP_FPS, DEFAULT_FPS)

    def _close_camera(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def _capture_loop(self) -> None:
        fps_count = 0
        fps_t = time.time()

        while not self._stop_event.is_set():
            if not self._cap or not self._cap.isOpened():
                time.sleep(0.1)
                continue
            ret, bgr = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            with self._frame_lock:
                self._current_frame = rgb

            if self._frame_callback:
                self._frame_callback(rgb)

            fps_count += 1
            if time.time() - fps_t >= 1.0:
                with self._state_lock:
                    self._state.fps = fps_count
                fps_count = 0
                fps_t = time.time()

            time.sleep(1.0 / DEFAULT_FPS)

    # ─── AI Loop ───

    def _ai_loop(self) -> None:
        """Основной цикл: кадр → ИИ → команда → выполнение."""
        while not self._stop_event.is_set():
            # В режиме STEP ждём сигнала
            if self._mode == ControlMode.STEP:
                self._step_event.wait()
                self._step_event.clear()
                if self._stop_event.is_set():
                    break

            # Взять текущий кадр
            with self._frame_lock:
                frame = self._current_frame.copy() if self._current_frame is not None else None

            if frame is None:
                time.sleep(0.2)
                continue

            # Получить текущие углы суставов
            joint_angles = self._get_joint_angles()
            ee_pos = self._get_ee_pos(joint_angles)

            # Запрос к ИИ
            command = self._query_ai(frame, joint_angles, ee_pos)

            with self._state_lock:
                self._state.last_command = command
                self._state.last_ai_latency = command.raw_response.__len__() * 0  # обновим ниже
                self._state.joint_angles = joint_angles
                self._state.step_count += 1

            # Сохранить историю
            self._command_history.append(command)
            if len(self._command_history) > self._max_history:
                self._command_history.pop(0)

            if self._command_callback:
                self._command_callback(command)

            if self._state_callback:
                with self._state_lock:
                    self._state_callback(self._state)

            # Выполнить команду (кроме режима WATCH)
            if self._mode != ControlMode.WATCH:
                self._execute_command(command)

            # Пауза между запросами (только AUTO)
            if self._mode == ControlMode.AUTO:
                self._stop_event.wait(self._ai_interval)

    # ─── AI Query ───

    def _query_ai(
        self,
        frame: np.ndarray,
        joint_angles: list[float],
        ee_pos: list[float],
    ) -> AICommand:
        """Отправить кадр + состояние в Qwen3 VL, получить команду."""
        with self._state_lock:
            task = self._task

        prompt = _SYSTEM_PROMPT.format(
            task=task,
            joints=[round(a, 1) for a in joint_angles],
            ee_pos=[round(p, 0) for p in ee_pos],
        )

        self._log(
            f"→ AI query: task='{task[:40]}...' joints={[round(a, 1) for a in joint_angles]}",
            "info",
        )

        t0 = time.time()
        try:
            response = self.ai.chat_json(
                prompt=prompt,
                images=[frame],
            )
            latency = time.time() - t0

            with self._state_lock:
                self._state.last_ai_latency = latency

            if not response.success:
                self._log(f"✗ AI error: {response.error}", "error")
                return AICommand.error_cmd(response.error)

            cmd = parse_ai_command(response.content, raw=response.content)
            cmd.raw_response = response.content

            self._log(
                f"← AI [{latency:.1f}s] action={cmd.action} "
                f"reason='{cmd.reason[:60]}' conf={cmd.confidence:.2f}",
                "success" if cmd.action != "idle" else "info",
            )

            return cmd

        except Exception as e:
            logger.exception("AI query failed: %s", e)
            self._log(f"✗ Exception: {e}", "error")
            return AICommand.error_cmd(str(e))

    # ─── Execution ───

    def _execute_command(self, command: AICommand) -> None:
        """Выполнить команду на роботе."""
        if not command.success or command.action == "idle":
            return

        if not self.robot.is_connected:
            self._log("Robot not connected — command skipped", "warning")
            return

        if not command.is_safe():
            self._log(f"⚠ Unsafe command blocked: deltas={command.joint_deltas}", "error")
            return

        try:
            if command.action == "stop":
                self.robot.emergency_stop()
                self._log("🛑 Emergency stop executed", "error")

            elif command.action == "home":
                self.robot.move_joints([0.0] * 6, speed=400)
                self._log("🏠 Home position", "info")

            elif command.action in ("move", "grip", "release"):
                # Вычислить целевые углы
                current = self._get_joint_angles()
                if command.joint_targets:
                    targets = [
                        max(-JOINT_LIMIT_DEG, min(JOINT_LIMIT_DEG, t))
                        for t in command.joint_targets
                    ]
                else:
                    targets = [
                        max(-JOINT_LIMIT_DEG, min(JOINT_LIMIT_DEG, c + d))
                        for c, d in zip(current, command.joint_deltas)
                    ]

                self.robot.move_joints(targets, speed=command.speed)
                self._log(
                    f"⚙ move joints → {[round(t, 1) for t in targets]} speed={command.speed}",
                    "info",
                )

                # Gripper
                if command.gripper_open is not None:
                    if hasattr(self.robot, "set_gripper"):
                        self.robot.set_gripper(command.gripper_open)
                    elif command.action == "grip":
                        self._log("✊ Grip", "info")
                    elif command.action == "release":
                        self._log("🖐 Release", "info")

        except Exception as e:
            logger.exception("Command execution failed: %s", e)
            self._log(f"✗ Execution error: {e}", "error")
            with self._state_lock:
                self._state.error = str(e)

    # ─── Step mode ───

    def trigger_step(self) -> None:
        """Запустить один шаг (только в режиме STEP)."""
        if self._mode == ControlMode.STEP:
            self._step_event.set()

    # ─── Utilities ───

    def _get_joint_angles(self) -> list[float]:
        """Получить текущие углы суставов."""
        try:
            if self.robot and self.robot.is_connected:
                return self.robot.get_joint_angles()
        except Exception:
            pass
        with self._state_lock:
            return list(self._state.joint_angles)

    def _get_ee_pos(self, joint_angles: list[float]) -> list[float]:
        """Вычислить позицию end-effector через кинематику."""
        try:
            if self.kin:
                result = self.kin.forward_kinematics(joint_angles)
                if result is not None:
                    return [float(result[0]), float(result[1]), float(result[2])]
        except Exception:
            pass
        # Fallback — упрощённая FK
        from ..models.rl.environment import RobotArmEnv

        env = RobotArmEnv()
        pos = env._forward_kinematics(np.array(joint_angles))
        return [float(pos[0]), float(pos[1]), float(pos[2])]

    def _log(self, msg: str, level: str = "info") -> None:
        logger.info("[AIRobotCtrl] %s", msg)
        if self._log_callback:
            self._log_callback(msg, level)

    # ─── Public API ───

    def start(self) -> bool:
        """Инициализировать и запустить сервис."""
        self.initialize()
        super().start()
        return self._state.is_running

    def stop(self) -> None:
        """Остановить сервис."""
        super().stop()

    def get_state(self) -> ControllerState:
        with self._state_lock:
            return ControllerState(
                mode=self._state.mode,
                is_running=self._state.is_running,
                task=self._state.task,
                step_count=self._state.step_count,
                last_command=self._state.last_command,
                last_ai_latency=self._state.last_ai_latency,
                fps=self._state.fps,
                joint_angles=list(self._state.joint_angles),
                camera_id=self._camera_id,
                ai_model=self._state.ai_model,
                error=self._state.error,
            )

    def get_history(self) -> list[AICommand]:
        return list(self._command_history)

    def clear_history(self) -> None:
        self._command_history.clear()

    def __repr__(self) -> str:
        return (
            f"AIRobotControllerService("
            f"mode={self._mode.name}, "
            f"ai={self._state.ai_model}, "
            f"running={self._state.is_running})"
        )
