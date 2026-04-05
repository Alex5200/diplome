#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Program Executor Module

Исполнитель программ блочного программирования.
"""

import threading
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from app.controllers.motor_controller import MotorController
from app.config.constants import DEFAULT_SPEED


class ExecutionState(Enum):
    """Состояния исполнения программы."""
    IDLE = 'idle'
    RUNNING = 'running'
    PAUSED = 'paused'
    STOPPED = 'stopped'
    COMPLETED = 'completed'
    ERROR = 'error'


@dataclass
class ExecutionResult:
    """Результат исполнения программы."""
    success: bool
    executed_blocks: int
    total_blocks: int
    error_message: Optional[str] = None
    execution_time: float = 0.0


class ProgramExecutor:
    """
    Исполнитель программ блочного программирования.

    Поддерживает:
        - Последовательное выполнение блоков
        - Паузу и остановку выполнения
        - Обработку ошибок
        - Callback уведомления о прогрессе

    Типы блоков:
        - move_to: Движение сустава в позицию
        - home: Возврат в домашнюю позицию
        - wait_time: Ожидание указанное время
        - torque_on: Включение момента
        - torque_off: Выключение момента

    Пример использования:
        executor = ProgramExecutor(controller)
        executor.on_block_complete = lambda b: print(f"Блок {b} выполнен")
        result = executor.execute(program_blocks)
    """

    # Типы поддерживаемых блоков
    BLOCK_TYPES = {
        'move_to': 'Движение в позицию',
        'home': 'Домашняя позиция',
        'wait_time': 'Ожидание',
        'torque_on': 'Включение момента',
        'torque_off': 'Выключение момента',
    }

    def __init__(self, controller: MotorController):
        """
        Инициализация исполнителя программ.

        Args:
            controller: Контроллер моторов для выполнения команд
        """
        self.controller = controller
        self.state = ExecutionState.IDLE
        self._stop_flag = False
        self._pause_flag = False
        self._current_block_index = 0
        self._start_time = 0.0

        # Callback функции
        self.on_block_start: Optional[Callable[[Dict[str, Any], int], None]] = None
        self.on_block_complete: Optional[Callable[[Dict[str, Any], int], None]] = None
        self.on_block_error: Optional[Callable[[Dict[str, Any], int, str], None]] = None
        self.on_program_complete: Optional[Callable[[ExecutionResult], None]] = None

    def execute(self, program: List[Dict[str, Any]], async_mode: bool = True) -> Optional[ExecutionResult]:
        """
        Выполнение программы.

        Args:
            program: Список блоков программы
            async_mode: Если True, выполняется в отдельном потоке

        Returns:
            ExecutionResult при синхронном выполнении, None при асинхронном
        """
        if not program:
            return ExecutionResult(
                success=True,
                executed_blocks=0,
                total_blocks=0,
                execution_time=0.0
            )

        if async_mode:
            thread = threading.Thread(target=self._execute_sync, args=(program,), daemon=True)
            thread.start()
            return None
        else:
            return self._execute_sync(program)

    def _execute_sync(self, program: List[Dict[str, Any]]) -> ExecutionResult:
        """
        Синхронное выполнение программы.

        Args:
            program: Список блоков программы

        Returns:
            Результат выполнения
        """
        self.state = ExecutionState.RUNNING
        self._stop_flag = False
        self._pause_flag = False
        self._start_time = time.time()
        self._current_block_index = 0

        executed_blocks = 0
        error_message = None

        try:
            for i, block in enumerate(program):
                if self._stop_flag:
                    self.state = ExecutionState.STOPPED
                    return ExecutionResult(
                        success=False,
                        executed_blocks=executed_blocks,
                        total_blocks=len(program),
                        error_message='Программа остановлена пользователем',
                        execution_time=time.time() - self._start_time
                    )

                # Обработка паузы
                while self._pause_flag:
                    time.sleep(0.1)
                    if self._stop_flag:
                        self.state = ExecutionState.STOPPED
                        return ExecutionResult(
                            success=False,
                            executed_blocks=executed_blocks,
                            total_blocks=len(program),
                            error_message='Программа остановлена пользователем',
                            execution_time=time.time() - self._start_time
                        )

                self._current_block_index = i
                params = block.get('params', {})
                block_id = block.get('id', i)

                # Callback начала блока
                if self.on_block_start:
                    self.on_block_start(params, block_id)

                try:
                    self._execute_block(params)
                    executed_blocks += 1

                    # Callback завершения блока
                    if self.on_block_complete:
                        self.on_block_complete(params, block_id)

                except Exception as e:
                    error_message = f"Ошибка блока {block_id}: {str(e)}"
                    self.state = ExecutionState.ERROR

                    # Callback ошибки
                    if self.on_block_error:
                        self.on_block_error(params, block_id, str(e))

                    return ExecutionResult(
                        success=False,
                        executed_blocks=executed_blocks,
                        total_blocks=len(program),
                        error_message=error_message,
                        execution_time=time.time() - self._start_time
                    )

            self.state = ExecutionState.COMPLETED
            execution_time = time.time() - self._start_time

            result = ExecutionResult(
                success=True,
                executed_blocks=executed_blocks,
                total_blocks=len(program),
                execution_time=execution_time
            )

            # Callback завершения программы
            if self.on_program_complete:
                self.on_program_complete(result)

            return result

        except Exception as e:
            self.state = ExecutionState.ERROR
            return ExecutionResult(
                success=False,
                executed_blocks=executed_blocks,
                total_blocks=len(program),
                error_message=f"Критическая ошибка: {str(e)}",
                execution_time=time.time() - self._start_time
            )

    def _execute_block(self, params: Dict[str, Any]) -> None:
        """
        Выполнение одного блока программы.

        Args:
            params: Параметры блока

        Raises:
            ValueError: Если тип блока не поддерживается
            Exception: Если произошла ошибка при выполнении
        """
        block_type = params.get('type', '')

        if block_type == 'move_to':
            self._execute_move_to(params)
        elif block_type == 'home':
            self._execute_home(params)
        elif block_type == 'wait_time':
            self._execute_wait_time(params)
        elif block_type == 'torque_on':
            self._execute_torque_on(params)
        elif block_type == 'torque_off':
            self._execute_torque_off(params)
        else:
            raise ValueError(f"Неподдерживаемый тип блока: {block_type}")

    def _execute_move_to(self, params: Dict[str, Any]) -> None:
        """
        Выполнение блока движения в позицию.

        Args:
            params: Параметры блока (joint, position, speed)
        """
        joint = params.get('joint', 0)
        position = params.get('position', 2048)
        speed = params.get('speed', DEFAULT_SPEED)

        if not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        success = self.controller.move_joint(joint, position, speed=speed)
        if not success:
            raise RuntimeError(f"Не удалось выполнить движение сустава {joint} в позицию {position}")

    def _execute_home(self, params: Dict[str, Any]) -> None:
        """
        Выполнение блока возврата в домашнюю позицию.

        Args:
            params: Параметры блока (joint или 'all')
        """
        joint = params.get('joint', 'all')

        if not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        if joint == 'all':
            for i in range(6):
                self.controller.move_joint(i, 0)
        else:
            self.controller.move_joint(joint, 0)

    def _execute_wait_time(self, params: Dict[str, Any]) -> None:
        """
        Выполнение блока ожидания.

        Args:
            params: Параметры блока (seconds)
        """
        seconds = params.get('seconds', 1.0)
        time.sleep(max(0, seconds))

    def _execute_torque_on(self, params: Dict[str, Any]) -> None:
        """
        Выполнение блока включения момента.

        Args:
            params: Параметры блока (joint)
        """
        joint = params.get('joint', 0)

        if not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        motor_id = self.controller.get_motor_id_for_joint(joint)
        self.controller.toggle_torque(motor_id, True)

    def _execute_torque_off(self, params: Dict[str, Any]) -> None:
        """
        Выполнение блока выключения момента.

        Args:
            params: Параметры блока (joint)
        """
        joint = params.get('joint', 0)

        if not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        motor_id = self.controller.get_motor_id_for_joint(joint)
        self.controller.toggle_torque(motor_id, False)

    def stop(self) -> None:
        """Остановка выполнения программы."""
        self._stop_flag = True
        self._pause_flag = False

    def pause(self) -> None:
        """Пауза выполнения программы."""
        if self.state == ExecutionState.RUNNING:
            self._pause_flag = True
            self.state = ExecutionState.PAUSED

    def resume(self) -> None:
        """Возобновление выполнения программы."""
        if self.state == ExecutionState.PAUSED:
            self._pause_flag = False
            self.state = ExecutionState.RUNNING

    def is_running(self) -> bool:
        """
        Проверка состояния выполнения.

        Returns:
            True если программа выполняется
        """
        return self.state in (ExecutionState.RUNNING, ExecutionState.PAUSED)

    def get_current_block_index(self) -> int:
        """
        Получение индекса текущего выполняемого блока.

        Returns:
            Индекс текущего блока
        """
        return self._current_block_index

    def get_state(self) -> ExecutionState:
        """
        Получение текущего состояния исполнения.

        Returns:
            Текущее состояние
        """
        return self.state
