#!/usr/bin/env python3

"""
Program Service Module

Сервис для выполнения программ блочного программирования.
"""

import threading
import time
from collections.abc import Callable
from typing import Any

from ..core.base_service import BaseService
from ..models.motor_data import ProgramBlock, RobotProgram


class ProgramService(BaseService):
    """
    Сервис выполнения программ.

    Предоставляет возможности:
    - Загрузка/сохранение программ
    - Пошаговое выполнение
    - Пауза/возобновление
    - Прерывание выполнения
    """

    def __init__(self, robot_service=None):
        """
        Инициализация сервиса.

        Args:
            robot_service: Ссылка на RobotService для выполнения команд
        """
        super().__init__("ProgramService")

        self._robot_service = robot_service
        self._current_program: RobotProgram | None = None
        self._execution_thread: threading.Thread | None = None
        self._is_running = False
        self._is_paused = False
        self._current_block_index = 0
        self._execution_callback: Callable[[str, Any], None] | None = None

    def _do_initialize(self) -> bool:
        """Инициализация сервиса."""
        self._emit_event("program_service_initialized", {})
        return True

    def _do_start(self) -> None:
        """Запуск сервиса (не запускает программу)."""
        pass

    def _do_stop(self) -> None:
        """Остановка сервиса."""
        self.stop_execution()

    def _get_extra_status(self) -> dict[str, Any]:
        """Дополнительный статус."""
        return {
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "current_block": self._current_block_index,
            "program_name": self._current_program.name if self._current_program else None,
        }

    # ==================== Управление программой ====================

    def load_program(self, blocks: list[dict[str, Any]], name: str = "") -> bool:
        """
        Загрузка программы из списка блоков.

        Args:
            blocks: Список блоков программы
            name: Название программы

        Returns:
            True если успешно
        """
        try:
            self._current_program = RobotProgram(
                name=name,
                blocks=[ProgramBlock.from_dict(b) for b in blocks],
            )
            self._emit_event("program_loaded", {"name": name, "blocks": len(blocks)})
            return True
        except Exception as e:
            self._emit_event("program_error", {"error": str(e)})
            return False

    def get_current_program(self) -> RobotProgram | None:
        """Получение текущей программы."""
        return self._current_program

    def clear_program(self) -> None:
        """Очистка текущей программы."""
        self._current_program = None
        self._emit_event("program_cleared", {})

    # ==================== Выполнение ====================

    def start_execution(self) -> bool:
        """
        Запуск выполнения программы.

        Returns:
            True если успешно запущено
        """
        if not self._current_program or not self._current_program.blocks:
            self._emit_event("program_error", {"error": "Программа пуста"})
            return False

        if self._is_running:
            return False

        self._is_running = True
        self._is_paused = False
        self._current_block_index = 0

        self._execution_thread = threading.Thread(target=self._execute_program, daemon=True)
        self._execution_thread.start()

        self._emit_event("program_started", {"name": self._current_program.name})
        return True

    def stop_execution(self) -> None:
        """Остановка выполнения."""
        self._is_running = False
        self._is_paused = False
        if self._execution_thread:
            self._execution_thread.join(timeout=2.0)
            self._execution_thread = None

        self._emit_event("program_stopped", {})

    def pause_execution(self) -> None:
        """Пауза выполнения."""
        self._is_paused = True
        self._emit_event("program_paused", {})

    def resume_execution(self) -> None:
        """Возобновление выполнения."""
        self._is_paused = False
        self._emit_event("program_resumed", {})

    def _execute_program(self) -> None:
        """Основной цикл выполнения программы."""
        blocks = self._current_program.blocks

        while self._is_running and self._current_block_index < len(blocks):
            # Проверка паузы
            while self._is_paused and self._is_running:
                time.sleep(0.1)

            if not self._is_running:
                break

            block = blocks[self._current_block_index]
            self._emit_event(
                "block_started",
                {
                    "index": self._current_block_index,
                    "type": block.block_type,
                },
            )

            # Выполнение блока
            success = self._execute_block(block)

            self._emit_event(
                "block_completed",
                {
                    "index": self._current_block_index,
                    "success": success,
                },
            )

            self._current_block_index += 1

        # Завершение
        if self._is_running:
            self._is_running = False
            self._emit_event(
                "program_completed",
                {
                    "name": self._current_program.name,
                },
            )

    def _execute_block(self, block: ProgramBlock) -> bool:
        """
        Выполнение одного блока.

        Args:
            block: Блок для выполнения

        Returns:
            True если успешно
        """
        block_type = block.block_type
        params = block.params

        try:
            if block_type == "move_to":
                return self._execute_move_to(params)

            elif block_type == "move_all":
                return self._execute_move_all(params)

            elif block_type == "wait_time":
                return self._execute_wait(params)

            elif block_type == "torque_on":
                return self._execute_torque(params, enable=True)

            elif block_type == "torque_off":
                return self._execute_torque(params, enable=False)

            elif block_type == "home":
                return self._execute_home(params)

            else:
                self._emit_event("block_error", {"error": f"Неизвестный тип блока: {block_type}"})
                return False

        except Exception as e:
            self._emit_event("block_error", {"error": str(e)})
            return False

    def _execute_move_to(self, params: dict[str, Any]) -> bool:
        """Выполнение движения к позиции."""
        if not self._robot_service:
            return False

        joint = params.get("joint", 0)
        angle = params.get("angle", 0)
        speed = params.get("speed", 500)

        return self._robot_service.move_joint(joint, angle, speed)

    def _execute_move_all(self, params: dict[str, Any]) -> bool:
        """Выполнение движения всех суставов."""
        if not self._robot_service:
            return False

        angles = params.get("angles", [0] * 6)
        speed = params.get("speed", 500)

        return self._robot_service.move_joints(angles, speed)

    def _execute_wait(self, params: dict[str, Any]) -> bool:
        """Выполнение ожидания."""
        seconds = params.get("seconds", 1.0)
        time.sleep(seconds)
        return True

    def _execute_torque(self, params: dict[str, Any], enable: bool) -> bool:
        """Выполнение включения/выключения момента."""
        if not self._robot_service:
            return False

        joint = params.get("joint", 0)
        return self._robot_service.set_torque(joint, enable)

    def _execute_home(self, params: dict[str, Any]) -> bool:
        """Выполнение движения в домашнюю позицию."""
        if not self._robot_service:
            return False

        home_angles = params.get("angles", [0, 0, 0, 0, 0, 0])
        speed = params.get("speed", 300)

        return self._robot_service.move_joints(home_angles, speed)

    # ==================== Callback ====================

    def set_execution_callback(self, callback: Callable[[str, Any], None]) -> None:
        """
        Установка callback для событий выполнения.

        Args:
            callback: Функция(event_name, data)
        """
        self._execution_callback = callback

    def _emit_event(self, event_name: str, data: dict[str, Any]) -> None:
        """Отправка события с вызовом callback."""
        super()._emit_event(event_name, data)

        if self._execution_callback:
            self._execution_callback(event_name, data)

    # ==================== Свойства ====================

    @property
    def is_running(self) -> bool:
        """Проверка: выполняется ли программа."""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """Проверка: на паузе ли программа."""
        return self._is_paused

    @property
    def current_block_index(self) -> int:
        """Текущий индекс выполняемого блока."""
        return self._current_block_index

    @property
    def total_blocks(self) -> int:
        """Общее количество блоков."""
        return len(self._current_program.blocks) if self._current_program else 0

    @property
    def progress(self) -> float:
        """Прогресс выполнения (0.0 - 1.0)."""
        if not self._current_program:
            return 0.0
        return self._current_block_index / len(self._current_program.blocks)
