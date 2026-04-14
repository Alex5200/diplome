#!/usr/bin/env python3
"""
SimToRealMirror — непрерывное зеркалирование между MuJoCo и реальным роботом.
"""

from __future__ import annotations

import logging
import math
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mujoco_robot_sim import MuJoCoRobotController

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
from models.kinematics import RobotKinematics6DOF

logger = logging.getLogger(__name__)

MAX_POSITION = 4095
DEFAULT_ACC = 5
MIN_SPEED = 50
MAX_SPEED = 3400


@dataclass
class MirrorStats:
    commands_sent: int = 0
    errors: int = 0
    frames_dropped: int = 0
    _rate_window: list[float] = field(default_factory=list)
    _window_size: int = 50
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_command(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._rate_window.append(now)
            if len(self._rate_window) > self._window_size:
                self._rate_window.pop(0)
            self.commands_sent += 1

    def record_error(self) -> None:
        with self._lock:
            self.errors += 1

    def record_drop(self) -> None:
        with self._lock:
            self.frames_dropped += 1

    @property
    def actual_rate_hz(self) -> float:
        with self._lock:
            if len(self._rate_window) < 2:
                return 0.0
            span = self._rate_window[-1] - self._rate_window[0]
            return (len(self._rate_window) - 1) / span if span > 0 else 0.0

    def as_dict(self) -> dict:
        with self._lock:
            return {
                "commands_sent": self.commands_sent,
                "errors": self.errors,
                "frames_dropped": self.frames_dropped,
                "actual_rate_hz": round(self.actual_rate_hz, 1),
            }


class SimToRealMirror:
    def __init__(
        self,
        controller: "MuJoCoRobotController",
        *,
        mode: str = "sim_to_real",
        transport: str = "serial",
        port: str = "COM3",
        baudrate: int = 1_000_000,
        rate_hz: float = 20.0,
        motor_speed: int = 300,
        safety_check: bool = True,
        ros2_node_name: str = "mujoco_mirror",
        joint_offsets_deg: list[float] | None = None,
    ) -> None:
        if mode not in ("sim_to_real", "real_to_sim"):
            raise ValueError(f"mode must be 'sim_to_real' or 'real_to_sim', got {mode!r}")
        if transport not in ("serial", "ros2"):
            raise ValueError(f"transport must be 'serial' or 'ros2', got {transport!r}")

        self._ctrl = controller
        self._mode = mode
        self._transport = transport
        self._port = port
        self._baudrate = baudrate
        self._rate_hz = rate_hz
        self._interval = 1.0 / rate_hz
        self._motor_speed = max(MIN_SPEED, min(MAX_SPEED, motor_speed))
        self._safety_check = safety_check
        self._ros2_node_name = ros2_node_name

        self._offsets_deg = list(joint_offsets_deg) if joint_offsets_deg else [0.0] * 6

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats = MirrorStats()
        self._real_to_sim_queue: queue.Queue[list[float]] = queue.Queue(maxsize=10)
        self._ctrl_lock = threading.Lock()

        self._ros2_node = None
        self._ros2_publisher = None
        self._ros2_imports = {}

    def start(self) -> bool:
        if self._stop_event.is_set():
            self._stop_event.clear()
        if self._thread and self._thread.is_alive():
            logger.warning("SimToRealMirror уже запущен")
            return True
        if not self._connect():
            return False
        self._thread = threading.Thread(
            target=self._mirror_loop, name="SimToRealMirror", daemon=True
        )
        self._thread.start()
        logger.info(
            "SimToRealMirror запущен: mode=%s transport=%s rate=%.0f Гц speed=%d offsets=%s",
            self._mode,
            self._transport,
            self._rate_hz,
            self._motor_speed,
            self._offsets_deg,
        )
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._disconnect()
        logger.info("SimToRealMirror остановлен. %s", self._stats.as_dict())

    def __enter__(self) -> "SimToRealMirror":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
        return False

    def _connect(self) -> bool:
        if self._transport == "serial":
            try:
                logger.info("Попытка подключения к %s (baud=%d)...", self._port, self._baudrate)
                with self._ctrl_lock:
                    ok = self._ctrl.connect_real_robot(self._port)
                if not ok:
                    logger.error("Контроллер вернул False при подключении к %s", self._port)
                    return False
                logger.info("✓ Подключено к %s", self._port)
                return True
            except Exception as e:
                logger.error("Исключение при подключении к %s: %s", self._port, e)
                return False
        elif self._transport == "ros2":
            return self._connect_ros2()
        return False

    def _connect_ros2(self) -> bool:
        try:
            import rclpy
            from trajectory_msgs.msg import JointTrajectoryPoint

            if not rclpy.ok():
                rclpy.init()
            self._ros2_node = rclpy.create_node(self._ros2_node_name)
            self._ros2_publisher = self._ros2_node.create_publisher(
                JointTrajectoryPoint, "/robot/joint_cmd", 10
            )
            self._ros2_imports = {"rclpy": rclpy, "JointTrajectoryPoint": JointTrajectoryPoint}
            logger.info("ROS2 publisher создан: /robot/joint_cmd")
            return True
        except ImportError:
            logger.error("rclpy не найден. Используйте transport='serial'.")
            return False
        except Exception as e:
            logger.error("Ошибка инициализации ROS2: %s", e)
            return False

    def _disconnect(self) -> None:
        if self._transport == "serial":
            with self._ctrl_lock:
                self._ctrl.disconnect_real_robot()
        elif self._transport == "ros2" and self._ros2_node:
            try:
                self._ros2_node.destroy_node()
            except Exception:
                pass
            finally:
                if self._ros2_imports.get("rclpy") and self._ros2_imports["rclpy"].ok():
                    self._ros2_imports["rclpy"].shutdown()
            self._ros2_node = None
            self._ros2_publisher = None
            self._ros2_imports.clear()

    def _mirror_loop(self) -> None:
        while not self._stop_event.is_set():
            t0 = time.monotonic()
            try:
                if self._mode == "sim_to_real":
                    self._step_sim_to_real()
                else:
                    self._step_real_to_sim()
            except Exception as e:
                logger.warning("Ошибка в цикле зеркалирования: %s", e)
                self._stats.record_error()

            elapsed = time.monotonic() - t0
            sleep_time = self._interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                self._stats.record_drop()
                time.sleep(0.001)

    def _step_sim_to_real(self) -> None:
        with self._ctrl_lock:
            angles_deg = list(self._ctrl.get_joint_angles())

        # Применяем смещения
        angles_deg = [a + o for a, o in zip(angles_deg, self._offsets_deg)]

        if self._safety_check:
            angles_deg = _clamp_angles(angles_deg, self._ctrl.SAFE_ANGLE_LIMITS_DEG)

        if self._transport == "serial":
            self._send_serial(angles_deg)
        elif self._transport == "ros2":
            self._send_ros2(angles_deg)
        self._stats.record_command()

    def _step_real_to_sim(self) -> None:
        with self._ctrl_lock:
            raw_angles = list(self._ctrl.read_real_angles())

        if raw_angles:
            # Обратное смещение для корректного отображения в симуляции
            angles = [a - o for a, o in zip(raw_angles, self._offsets_deg)]
            try:
                self._real_to_sim_queue.put_nowait(angles)
            except queue.Full:
                self._stats.record_drop()
            self._stats.record_command()
        else:
            self._stats.record_error()

    def poll_real_angles(self) -> list[float] | None:
        try:
            return self._real_to_sim_queue.get_nowait()
        except queue.Empty:
            return None

    def _send_serial(self, angles_deg: list[float]) -> None:
        with self._ctrl_lock:
            if not self._ctrl.st3215:
                return
            for i, angle in enumerate(angles_deg):
                motor_id = self._ctrl._get_motor_id(i)
                position = RobotKinematics6DOF.angle_to_motor_position(angle)
                position = self._ctrl._apply_inversion(position, i)
                st3215 = self._ctrl.st3215
                position = max(0, min(MAX_POSITION, position))
                try:
                    st3215.MoveTo(motor_id, position, speed=self._motor_speed, acc=DEFAULT_ACC)
                except Exception as e:
                    logger.warning("Мотор %d: %s", motor_id, e)
                    self._stats.record_error()

    def _send_ros2(self, angles_deg: list[float]) -> None:
        if not self._ros2_publisher or not self._ros2_imports.get("rclpy"):
            return
        try:
            msg = self._ros2_imports["JointTrajectoryPoint"]()
            msg.positions = [math.radians(a) for a in angles_deg]
            msg.velocities = [0.0] * 6
            self._ros2_publisher.publish(msg)
        except Exception as e:
            logger.warning("ROS2 publish error: %s", e)
            self._stats.record_error()

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def transport(self) -> str:
        return self._transport

    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set()

    @property
    def stats(self) -> dict:
        return {
            **self._stats.as_dict(),
            "mode": self._mode,
            "transport": self._transport,
            "target_rate_hz": self._rate_hz,
            "motor_speed": self._motor_speed,
            "safety_check": self._safety_check,
            "offsets_deg": self._offsets_deg,
        }

    def set_motor_speed(self, speed: int) -> None:
        self._motor_speed = max(MIN_SPEED, min(MAX_SPEED, speed))
        logger.info("Скорость моторов: %d", self._motor_speed)

    def set_rate(self, rate_hz: float) -> None:
        self._rate_hz = max(1.0, min(100.0, rate_hz))
        self._interval = 1.0 / self._rate_hz
        logger.info("Частота зеркалирования: %.0f Гц", self._rate_hz)

    def set_offsets(self, offsets: list[float]) -> None:
        if len(offsets) != 6:
            raise ValueError("Offsets must contain exactly 6 values")
        self._offsets_deg = list(offsets)
        logger.info("Калибровочные смещения обновлены: %s", self._offsets_deg)


def _clamp_angles(angles_deg: list[float], limits: list[tuple[float, float]]) -> list[float]:
    return [max(lo, min(hi, a)) for a, (lo, hi) in zip(angles_deg, limits)]
