#!/usr/bin/env python3

"""
Robot Service Module

Сервис высокого уровня для управления роботом.
Абстрагирует работу с моторами и предоставляет удобный API.
"""

import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..config.constants import (
    JOINT_NAMES,
)
from ..controllers.motor_controller import MotorController
from ..core.base_service import BaseService
from ..models.motor_data import JointState, MotorData, RobotState


class RobotService(BaseService):
    """
    Сервис управления роботом.

    Предоставляет высокоуровневый API для:
    - Подключения к моторам
    - Управления суставами
    - Мониторинга состояния
    - Безопасного движения

    Пример использования:
        robot = RobotService()
        robot.initialize()
        robot.connect('COM3')
        robot.move_joint(0, 30)  # Повернуть базу на 30 градусов
    """

    def __init__(self):
        """Инициализация сервиса робота."""
        super().__init__("RobotService")

        self._controller = MotorController()
        self._robot_state = RobotState()
        self._monitor_thread: threading.Thread | None = None
        self._monitor_running = False
        self._monitor_interval = 0.5  # секунды

        # Callback для обновлений состояния
        self._state_callback: Callable[[RobotState], None] | None = None

        # Инициализация суставов
        self._init_joints()

    def _init_joints(self) -> None:
        """Инициализация состояний суставов."""
        self._robot_state.joints = [
            JointState(index=i, name=JOINT_NAMES[i] if i < len(JOINT_NAMES) else f"Joint {i}")
            for i in range(6)
        ]

    def _do_initialize(self) -> bool:
        """Инициализация сервиса."""
        self._emit_event("robot_initializing", {})
        self._init_joints()
        self._emit_event("robot_initialized", {})
        return True

    def _do_start(self) -> None:
        """Запуск мониторинга."""
        self._start_monitoring()

    def _do_stop(self) -> None:
        """Остановка мониторинга."""
        self._stop_monitoring()

    def _get_extra_status(self) -> dict[str, Any]:
        """Дополнительный статус."""
        return {
            "robot_state": self._robot_state.to_dict(),
            "controller_connected": self._controller.connected,
        }

    # ==================== Подключение ====================

    def connect(self, port: str) -> bool:
        """
        Подключение к роботу.

        Args:
            port: COM порт

        Returns:
            True если успешно
        """
        self._controller.device = port
        if self._controller.connect():
            self._robot_state.is_connected = True
            self._emit_event("robot_connected", {"port": port})
            self._log(f"✅ Подключено к {port}")
            return True
        return False

    def disconnect(self) -> None:
        """Отключение от робота."""
        self._controller.disconnect()
        self._robot_state.is_connected = False
        self._stop_monitoring()
        self._emit_event("robot_disconnected", {})
        self._log("🔌 Отключено")

    @property
    def is_connected(self) -> bool:
        """Проверка подключения."""
        return self._controller.connected and self._robot_state.is_connected

    # ==================== Сканирование ====================

    def scan_motors(self) -> list[int]:
        """
        Сканирование моторов.

        Returns:
            Список найденных ID
        """
        found = self._controller.scan_servos()
        self._emit_event("motors_scanned", {"found": found})
        return found

    # ==================== Управление ====================

    def move_joint(self, joint_index: int, angle_deg: float, speed: int | None = None) -> bool:
        """
        Движение сустава к углу.

        Args:
            joint_index: Индекс сустава (0-5)
            angle_deg: Целевой угол в градусах
            speed: Скорость (None = безопасная по умолчанию)

        Returns:
            True если успешно
        """
        if not self.is_connected:
            return False

        # Конвертация угла в позицию
        joint = self._robot_state.joints[joint_index]
        position = joint.to_motor_position(angle_deg)

        # Движение
        success = self._controller.move_joint(joint_index, position, speed)

        if success:
            joint.angle_deg = angle_deg
            joint.position = position
            self._emit_event(
                "joint_moved",
                {
                    "joint": joint_index,
                    "angle": angle_deg,
                    "position": position,
                },
            )

        return success

    def move_joints(self, angles: list[float], speed: int | None = None) -> bool:
        """
        Движение нескольких суставов.

        Args:
            angles: Список углов для каждого сустава
            speed: Скорость движения

        Returns:
            True если успешно
        """
        if not self.is_connected:
            return False

        positions = [
            self._robot_state.joints[i].to_motor_position(angles[i])
            for i in range(min(len(angles), 6))
        ]

        success = self._controller.move_all_joints(positions, speed or 500)

        if success:
            for i, angle in enumerate(angles[:6]):
                self._robot_state.joints[i].angle_deg = angle
            self._emit_event("joints_moved", {"angles": angles})

        return success

    def set_torque(self, joint_index: int, enable: bool) -> bool:
        """
        Включение/выключение момента сустава.

        Args:
            joint_index: Индекс сустава
            enable: True для включения

        Returns:
            True если успешно
        """
        motor_id = self._controller.get_motor_id_for_joint(joint_index)
        success = self._controller.toggle_torque(motor_id, enable)

        if success:
            self._robot_state.joints[joint_index].torque_enabled = enable
            self._emit_event(
                "torque_changed",
                {
                    "joint": joint_index,
                    "enabled": enable,
                },
            )

        return success

    def emergency_stop(self) -> None:
        """Экстренная остановка всех моторов."""
        self._controller.emergency_stop_all()
        self._robot_state.is_moving = False
        self._emit_event("emergency_stop", {})
        self._log("🛑 ЭКСТРЕННАЯ ОСТАНОВКА", level="error")

    # ==================== Мониторинг ====================

    def _start_monitoring(self) -> None:
        """Запуск потока мониторинга."""
        if self._monitor_running:
            return

        self._monitor_running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _stop_monitoring(self) -> None:
        """Остановка мониторинга."""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None

    def _monitor_loop(self) -> None:
        """Цикл мониторинга."""
        while self._monitor_running:
            try:
                self._update_robot_state()

                # Callback если установлен
                if self._state_callback:
                    self._state_callback(self._robot_state)

            except Exception as e:
                self._emit_event("monitor_error", {"error": str(e)})

            threading.Event().wait(self._monitor_interval)

    def _update_robot_state(self) -> None:
        """Обновление состояния робота."""
        if not self.is_connected:
            return

        timestamp = datetime.now()
        self._robot_state.timestamp = timestamp

        # Обновление данных моторов
        for joint in self._robot_state.joints:
            motor_id = self._controller.get_motor_id_for_joint(joint.index)
            data = self._controller.read_motor_data(motor_id)

            if data:
                motor_data = MotorData(
                    motor_id=motor_id,
                    position=data.get("position"),
                    temperature=data.get("temperature"),
                    voltage=data.get("voltage"),
                    current=data.get("current"),
                    load=data.get("load"),
                    moving=data.get("moving"),
                    last_update=timestamp.timestamp(),
                )
                self._robot_state.motors[motor_id] = motor_data

                # Обновление состояния сустава
                if motor_data.position is not None:
                    joint.position = motor_data.position
                    joint.angle_deg = joint.to_angle(motor_data.position)

        # Проверка движения
        self._robot_state.is_moving = any(m.is_moving() for m in self._robot_state.motors.values())

    def set_state_callback(self, callback: Callable[[RobotState], None]) -> None:
        """
        Установка callback для обновлений состояния.

        Args:
            callback: Функция принимающая RobotState
        """
        self._state_callback = callback

    def get_robot_state(self) -> RobotState:
        """Получение текущего состояния."""
        return self._robot_state.copy() if hasattr(self._robot_state, "copy") else self._robot_state

    def get_joint_angles(self) -> list[float]:
        """Получение углов всех суставов."""
        return [j.angle_deg for j in self._robot_state.joints]

    # ==================== Конфигурация ====================

    def get_motor_mapping(self) -> dict[str, Any]:
        """Получение соответствия моторов."""
        return self._controller.get_motor_mapping()

    def update_motor_mapping(self, joint_index: int, motor_id: int, name: str = "") -> None:
        """Обновление соответствия мотора."""
        self._controller.update_motor_mapping(joint_index, motor_id, name)

    def save_config(self, filename: str) -> bool:
        """Сохранение конфигурации."""
        return self._controller.save_config(filename)

    def load_config(self, filename: str) -> bool:
        """Загрузка конфигурации."""
        return self._controller.load_config(filename)

    # ==================== Утилиты ====================

    def _log(self, message: str, level: str = "info") -> None:
        """Логирование сообщения."""
        self._emit_event("log_message", {"message": message, "level": level})
