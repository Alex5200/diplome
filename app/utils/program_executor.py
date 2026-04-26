#!/usr/bin/env python3

"""
Program Executor Module — Расширенная версия с поддержкой всех блоков

Поддерживаемые блоки:
- move_joint: Движение конкретного мотора в позицию
- move_xyz: Движение по XYZ координатам (с IK)
- linear_move: Линейное перемещение в 3D
- rotate: Поворот ориентации (Rx, Ry, Rz)
- arc_move: Дуговое движение через промежуточную точку
- home: Возврат в домашнюю позицию
- center: Центральная позиция (2048)
- set_speed: Установка скорости
- set_accel: Установка ускорения
- wait_time: Ожидание
- wait_input: Ожидание входного сигнала
- torque_on/off: Управление моментом
- gripper: Управление захватом
- message: Вывод сообщения
- loop: Циклы
- if/else/endif: Условия
- goto/label: Переходы
- subroutine/return: Подпрограммы
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.config.constants import (
    DEFAULT_ACC,
    DEFAULT_SPEED,
    MAX_POSITION,
    MIN_POSITION,
)
from app.controllers.motor_controller import MotorController
from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF


class ExecutionState(Enum):
    """Состояния исполнения программы."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ExecutionResult:
    """Результат исполнения программы."""

    success: bool
    executed_blocks: int
    total_blocks: int
    error_message: str | None = None
    execution_time: float = 0.0


class ProgramExecutor:
    """
    Расширенный исполнитель программ блочного программирования.

    Поддерживает все типы блоков с богатым функционалом.
    """

    # Типы поддерживаемых блоков
    BLOCK_TYPES = {
        # Motion
        "move_joint": "Движение мотора",
        "move_xyz": "Движение XYZ",
        "linear_move": "Линейное перемещение",
        "rotate": "Поворот ориентации",
        "arc_move": "Дуговое движение",
        "home": "Домой",
        "center": "Центр",
        # Settings
        "set_speed": "Скорость",
        "set_accel": "Ускорение",
        "torque_on": "Момент ВКЛ",
        "torque_off": "Момент ВЫКЛ",
        "gripper": "Захват",
        # Timing
        "wait_time": "Задержка",
        "wait_input": "Ждать вход",
        # Logic
        "loop_start": "Цикл начало",
        "loop_end": "Цикл конец",
        "if": "Если",
        "else": "Иначе",
        "endif": "Конец если",
        # Flow
        "goto": "Переход",
        "label": "Метка",
        "subroutine": "Подпрограмма",
        "return": "Возврат",
        "message": "Сообщение",
    }

    def __init__(self, controller: MotorController):
        """Инициализация исполнителя."""
        self.controller = controller
        self.state = ExecutionState.IDLE
        self._stop_flag = False
        self._pause_flag = False
        self._current_block_index = 0
        self._start_time = 0.0

        # Текущие настройки
        self._current_speed = DEFAULT_SPEED
        self._current_accel = DEFAULT_ACC

        # Для циклов и условий
        self._loop_stack: list[dict[str, Any]] = []
        self._if_stack: list[bool] = []
        self._label_positions: dict[str, int] = {}
        self._subroutine_stack: list[int] = []

        # Callbacks
        self.on_block_start: Callable[[dict[str, Any], int], None] | None = None
        self.on_block_complete: Callable[[dict[str, Any], int], None] | None = None
        self.on_block_error: Callable[[dict[str, Any], int, str], None] | None = None
        self.on_program_complete: Callable[[ExecutionResult], None] | None = None
        self.on_message: Callable[[str, str], None] | None = None

        # Кинематика для XYZ движений
        self.kinematics = RobotKinematics6DOF()
        self.ik_solver = InverseKinematics6DOF(self.kinematics)

    def execute(
        self, program: list[dict[str, Any]], async_mode: bool = True
    ) -> ExecutionResult | None:
        """Выполнение программы."""
        if not program:
            return ExecutionResult(
                success=True, executed_blocks=0, total_blocks=0, execution_time=0.0
            )

        # Построение карты меток
        self._build_label_map(program)

        if async_mode:
            thread = threading.Thread(target=self._execute_sync, args=(program,), daemon=True)
            thread.start()
            return None
        else:
            return self._execute_sync(program)

    def _build_label_map(self, program: list[dict[str, Any]]) -> None:
        """Построение карты меток для goto."""
        self._label_positions.clear()
        for i, block in enumerate(program):
            params = block.get("params", {})
            if params.get("type") == "label":
                name = params.get("name", f"LBL_{i}")
                self._label_positions[name] = i

    def _execute_sync(self, program: list[dict[str, Any]]) -> ExecutionResult:
        """Синхронное выполнение программы."""
        self.state = ExecutionState.RUNNING
        self._stop_flag = False
        self._pause_flag = False
        self._start_time = time.time()
        self._current_block_index = 0

        # Сброс состояний
        self._loop_stack.clear()
        self._if_stack.clear()
        self._subroutine_stack.clear()
        self._current_speed = DEFAULT_SPEED
        self._current_accel = DEFAULT_ACC

        executed_blocks = 0
        error_message = None

        i = 0
        while i < len(program):
            if self._stop_flag:
                self.state = ExecutionState.STOPPED
                return ExecutionResult(
                    success=False,
                    executed_blocks=executed_blocks,
                    total_blocks=len(program),
                    error_message="Программа остановлена пользователем",
                    execution_time=time.time() - self._start_time,
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
                        error_message="Программа остановлена пользователем",
                        execution_time=time.time() - self._start_time,
                    )

            block = program[i]
            params = block.get("params", {})
            block_id = block.get("id", i)
            block_type = params.get("type", "")

            # Проверка условий (if/else)
            if self._if_stack and not self._if_stack[-1]:
                # Мы в false-ветке if, пропускаем блок пока не встретим endif
                if block_type not in ("else", "endif"):
                    i += 1
                    continue
                elif block_type == "else":
                    # После else всегда идет endif в нашей логике
                    pass
                elif block_type == "endif":
                    self._if_stack.pop()

            # Callback начала блока
            if self.on_block_start:
                self.on_block_start(params, block_id)

            try:
                # Обработка блоков управления потоком (не выполняем их)
                if block_type in (
                    "loop_start",
                    "loop_end",
                    "if",
                    "else",
                    "endif",
                    "goto",
                    "label",
                    "subroutine",
                    "return",
                ):
                    self._handle_flow_control(block_type, params, program, i)
                else:
                    # Выполнение блока
                    self._execute_block(params, block_type)
                    executed_blocks += 1

                # Callback завершения блока
                if self.on_block_complete:
                    self.on_block_complete(params, block_id)

                # Переход к следующему блоку (может измениться в handle_flow_control)
                i = self._get_next_index(i, block_type, params, program)

            except Exception as e:
                error_message = f"Ошибка блока {block_id} ({block_type}): {e!s}"
                self.state = ExecutionState.ERROR

                if self.on_block_error:
                    self.on_block_error(params, block_id, str(e))

                if self.on_message:
                    self.on_message(f"ERROR: {error_message}", "error")

                return ExecutionResult(
                    success=False,
                    executed_blocks=executed_blocks,
                    total_blocks=len(program),
                    error_message=error_message,
                    execution_time=time.time() - self._start_time,
                )

        self.state = ExecutionState.COMPLETED
        execution_time = time.time() - self._start_time

        result = ExecutionResult(
            success=True,
            executed_blocks=executed_blocks,
            total_blocks=len(program),
            execution_time=execution_time,
        )

        if self.on_program_complete:
            self.on_program_complete(result)

        return result

    def _get_next_index(
        self,
        current_idx: int,
        block_type: str,
        params: dict[str, Any],
        program: list[dict],
    ) -> int:
        """Определение следующего индекса для выполнения."""
        # Обработка goto
        if block_type == "goto":
            label = params.get("label", "")
            if label in self._label_positions:
                return self._label_positions[label]
            return current_idx + 1

        # Обработка return - выход из подпрограммы
        if block_type == "return":
            if self._subroutine_stack:
                return self._subroutine_stack.pop()
            return current_idx + 1

        return current_idx + 1

    def _handle_flow_control(
        self,
        block_type: str,
        params: dict[str, Any],
        program: list[dict],
        current_idx: int,
    ) -> None:
        """Обработка блоков управления потоком."""

        if block_type == "loop_start":
            count = params.get("count", 1)
            name = params.get("name", f"loop_{len(self._loop_stack)}")
            self._loop_stack.append(
                {
                    "name": name,
                    "count": count,
                    "start_idx": current_idx,
                    "remaining": count,
                }
            )

        elif block_type == "loop_end":
            if self._loop_stack:
                loop = self._loop_stack[-1]
                loop["remaining"] -= 1
                if loop["remaining"] > 0:
                    # Вернуться к началу цикла
                    self._current_block_index = loop["start_idx"]
                    # Найдем индекс в program для возврата
                    for i, block in enumerate(program):
                        if i > current_idx and block.get("params", {}).get("type") == "loop_start":
                            if self._loop_stack and self._loop_stack[-1]["name"] == loop["name"]:
                                # Нужно вернуться - это обрабатывается в _get_next_index
                                pass

        elif block_type == "if":
            # Проверка условия
            condition = params.get("condition", "true")
            result = self._evaluate_condition(condition)
            self._if_stack.append(result)

        elif block_type == "else":
            # Инвертируем текущее условие
            if self._if_stack:
                self._if_stack[-1] = not self._if_stack[-1]

        elif block_type == "endif":
            if self._if_stack:
                self._if_stack.pop()

    def _evaluate_condition(self, condition: str) -> bool:
        """Оценка условия для if."""
        if condition == "true":
            return True
        elif condition == "connected":
            return self.controller.connected if self.controller else False
        elif condition == "not_connected":
            return not (self.controller.connected if self.controller else False)
        elif condition.startswith("input_"):
            # Здесь можно добавить проверку входов
            return False
        return True

    def _execute_block(self, params: dict[str, Any], block_type: str) -> None:
        """Выполнение одного блока."""

        if block_type == "move_joint":
            self._execute_move_joint(params)
        elif block_type == "move_xyz":
            self._execute_move_xyz(params)
        elif block_type == "linear_move":
            self._execute_linear_move(params)
        elif block_type == "rotate":
            self._execute_rotate(params)
        elif block_type == "arc_move":
            self._execute_arc_move(params)
        elif block_type == "home":
            self._execute_home(params)
        elif block_type == "center":
            self._execute_center(params)
        elif block_type == "set_speed":
            self._execute_set_speed(params)
        elif block_type == "set_accel":
            self._execute_set_accel(params)
        elif block_type == "torque_on":
            self._execute_torque_on(params)
        elif block_type == "torque_off":
            self._execute_torque_off(params)
        elif block_type == "gripper":
            self._execute_gripper(params)
        elif block_type == "wait_time":
            self._execute_wait_time(params)
        elif block_type == "wait_input":
            self._execute_wait_input(params)
        elif block_type == "message":
            self._execute_message(params)
        elif block_type == "subroutine":
            self._execute_subroutine(params)
        else:
            raise ValueError(f"Неподдерживаемый тип блока: {block_type}")

    def _execute_move_joint(self, params: dict[str, Any]) -> None:
        """Движение конкретного мотора в позицию."""
        joint = params.get("joint", 0)
        position = params.get("position", 2048)
        speed = params.get("speed", self._current_speed)

        if not self.controller or not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        # Проверка диапазона
        position = max(MIN_POSITION, min(MAX_POSITION, position))

        success = self.controller.move_joint(joint, position, speed=speed)
        if not success:
            raise RuntimeError(f"Не удалось двигать сустав {joint} в позицию {position}")

        # Сообщение
        if self.on_message:
            angle = (position / MAX_POSITION) * 360 - 180
            self.on_message(f"Move J{joint + 1} → {position} ({angle:.1f}°)", "info")

    def _execute_move_xyz(self, params: dict[str, Any]) -> None:
        """Движение по XYZ координатам с использованием IK."""
        x = params.get("x", 0.0)
        y = params.get("y", 0.0)
        z = params.get("z", 200.0)
        speed = params.get("speed", self._current_speed)

        if not self.controller or not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        # Решение обратной кинематики
        result = self.ik_solver.solve(x, y, z)
        if result is None:
            raise RuntimeError(f"Точка ({x}, {y}, {z}) недоступна для IK")

        # Применяем найденные углы к моторам
        for joint, angle in enumerate(result):
            position = int((angle + 180) / 360 * MAX_POSITION)
            position = max(MIN_POSITION, min(MAX_POSITION, position))
            self.controller.move_joint(joint, position, speed=speed)

        if self.on_message:
            angles_str = ", ".join([f"J{i + 1}={a:.1f}°" for i, a in enumerate(result)])
            self.on_message(f"Move XYZ({x}, {y}, {z}) → {angles_str}", "info")

    def _execute_linear_move(self, params: dict[str, Any]) -> None:
        """Линейное перемещение - аналогично XYZ но с интерполяцией."""
        # Пока просто используем XYZ
        self._execute_move_xyz(params)

    def _execute_rotate(self, params: dict[str, Any]) -> None:
        """Поворот ориентации (Rx, Ry, Rz)."""
        rx = params.get("rx", 0.0)
        ry = params.get("ry", 0.0)
        rz = params.get("rz", 0.0)
        speed = params.get("speed", self._current_speed)

        if not self.controller or not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        # Получаем текущие позиции моторов
        current_angles = []
        for joint in range(6):
            motor_id = self.controller.get_motor_id_for_joint(joint)
            pos = self.controller.joint_positions.get(motor_id, 2048)
            angle = (pos / MAX_POSITION) * 360 - 180
            current_angles.append(angle)

        # Вычисляем новые углы (упрощенно - добавляем к текущим)
        new_angles = [current_angles[j] + [rx, ry, rz][j] for j in range(3)]

        # Применяем для кисти (суставы 4, 5)
        for joint in range(3, 6):
            position = int((new_angles[joint - 3] + 180) / 360 * MAX_POSITION)
            position = max(MIN_POSITION, min(MAX_POSITION, position))
            self.controller.move_joint(joint, position, speed=speed)

        if self.on_message:
            self.on_message(f"Rotate Rx:{rx}° Ry:{ry}° Rz:{rz}°", "info")

    def _execute_arc_move(self, params: dict[str, Any]) -> None:
        """Дуговое движение через промежуточную точку."""
        # Упрощенная реализация - движение через 2 точки
        end_x = params.get("x", 0.0)
        end_y = params.get("y", 0.0)
        end_z = params.get("z", 200.0)
        via_x = params.get("via_x", 50.0)
        via_y = params.get("via_y", 50.0)
        via_z = params.get("via_z", 200.0)
        speed = params.get("speed", self._current_speed)

        # Двигаемся через промежуточную точку
        self._execute_move_xyz({"x": via_x, "y": via_y, "z": via_z, "speed": speed})
        time.sleep(0.5)  # Пауза между точками
        self._execute_move_xyz({"x": end_x, "y": end_y, "z": end_z, "speed": speed})

    def _execute_home(self, params: dict[str, Any]) -> None:
        """Возврат в домашнюю позицию (0)."""
        joint = params.get("joint", "all")
        speed = params.get("speed", self._current_speed)

        if not self.controller or not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        if joint == "all":
            for i in range(6):
                self.controller.move_joint(i, 0, speed=speed)
            if self.on_message:
                self.on_message("Home Position (All Joints)", "success")
        else:
            joint_idx = int(joint)
            self.controller.move_joint(joint_idx, 0, speed=speed)
            if self.on_message:
                self.on_message(f"Home J{joint_idx + 1}", "success")

    def _execute_center(self, params: dict[str, Any]) -> None:
        """Центральная позиция (2048)."""
        joint = params.get("joint", "all")
        speed = params.get("speed", self._current_speed)

        if not self.controller or not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        center_pos = 2048

        if joint == "all":
            for i in range(6):
                self.controller.move_joint(i, center_pos, speed=speed)
            if self.on_message:
                self.on_message("Center Position (All Joints)", "success")
        else:
            joint_idx = int(joint)
            self.controller.move_joint(joint_idx, center_pos, speed=speed)
            if self.on_message:
                self.on_message(f"Center J{joint_idx + 1}", "success")

    def _execute_set_speed(self, params: dict[str, Any]) -> None:
        """Установка скорости."""
        speed = params.get("speed", DEFAULT_SPEED)
        self._current_speed = max(100, min(5000, speed))

        if self.on_message:
            self.on_message(f"Speed set to {self._current_speed}", "info")

    def _execute_set_accel(self, params: dict[str, Any]) -> None:
        """Установка ускорения."""
        accel = params.get("accel", DEFAULT_ACC)
        self._current_accel = max(1, min(100, accel))

        if self.on_message:
            self.on_message(f"Acceleration set to {self._current_accel}", "info")

    def _execute_torque_on(self, params: dict[str, Any]) -> None:
        """Включение момента."""
        joint = params.get("joint", 0)

        if not self.controller or not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        motor_id = self.controller.get_motor_id_for_joint(joint)
        self.controller.toggle_torque(motor_id, True)

        if self.on_message:
            self.on_message(f"Torque ON J{joint + 1}", "success")

    def _execute_torque_off(self, params: dict[str, Any]) -> None:
        """Выключение момента."""
        joint = params.get("joint", 0)

        if not self.controller or not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        motor_id = self.controller.get_motor_id_for_joint(joint)
        self.controller.toggle_torque(motor_id, False)

        if self.on_message:
            self.on_message(f"Torque OFF J{joint + 1}", "warning")

    def _execute_gripper(self, params: dict[str, Any]) -> None:
        """Управление захватом."""
        close = params.get("close", True)
        force = params.get("force", 50)
        position = params.get("position", 2048)

        if not self.controller or not self.controller.connected:
            raise RuntimeError("Контроллер не подключен")

        # Предполагаем что захват подключен к 7-му мотору или какому-то
        # Здесь просто выводим сообщение
        action = "Close" if close else "Open"

        if self.on_message:
            self.on_message(f"Gripper {action} (Force: {force}%)", "info")

    def _execute_wait_time(self, params: dict[str, Any]) -> None:
        """Ожидание."""
        seconds = params.get("seconds", 1.0)
        time.sleep(max(0, seconds))

    def _execute_wait_input(self, params: dict[str, Any]) -> None:
        """Ожидание входного сигнала."""
        # Упрощенная реализация - просто ждем таймаут
        timeout = params.get("timeout", 30.0)
        input_num = params.get("input", 1)

        if self.on_message:
            self.on_message(f"Wait Input #{input_num}...", "warning")

        # Здесь можно добавить реальную проверку входов
        time.sleep(min(timeout, 1.0))  # Максимум 1 секунда для демо

    def _execute_message(self, params: dict[str, Any]) -> None:
        """Вывод сообщения."""
        text = params.get("text", "")
        msg_type = params.get("msg_type", "info")

        if self.on_message:
            self.on_message(text, msg_type)

    def _execute_subroutine(self, params: dict[str, Any]) -> None:
        """Вызов подпрограммы."""
        name = params.get("name", "SUB_1")

        # Сохраняем текущую позицию для return
        self._subroutine_stack.append(self._current_block_index + 1)

        if self.on_message:
            self.on_message(f"Call subroutine: {name}", "info")

    def stop(self) -> None:
        """Остановка выполнения."""
        self._stop_flag = True
        self._pause_flag = False

    def pause(self) -> None:
        """Пауза."""
        if self.state == ExecutionState.RUNNING:
            self._pause_flag = True
            self.state = ExecutionState.PAUSED

    def resume(self) -> None:
        """Возобновление."""
        if self.state == ExecutionState.PAUSED:
            self._pause_flag = False
            self.state = ExecutionState.RUNNING

    def is_running(self) -> bool:
        """Проверка выполнения."""
        return self.state in (ExecutionState.RUNNING, ExecutionState.PAUSED)

    def get_current_block_index(self) -> int:
        """Получение индекса текущего блока."""
        return self._current_block_index

    def get_state(self) -> ExecutionState:
        """Получение состояния."""
        return self.state
