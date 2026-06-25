#!/usr/bin/env python3
"""
TextProgramService — парсинг и выполнение текстовых робот-программ.

Поддерживает:
  - MOVE_J(joint, angle)           — движение сустава
  - MOVE_XYZ(x, y, z)              — движение по координатам
  - HOME(), CENTER()               — домашняя/центральная позиция
  - SPEED(percent)                 — скорость (0–100%)
  - TORQUE(joint, ON/OFF)          — момент
  - GRIPPER(OPEN/CLOSE, force?)    — захват
  - WAIT(seconds)                  — ожидание
  - FOR var = start TO end ... END_FOR  — цикл со счётчиком
  - WHILE condition ... END_WHILE       — цикл с условием
  - IF condition ... ELSE ... END_IF    — условный переход
  - LABEL(name), GOTO(name)        — метки и переходы
  - SUB(name), RETURN              — подпрограммы
  - PRINT(text)                    — сообщение в лог
  - // комментарии
"""

from __future__ import annotations

import re
import time
from typing import Any

from app.config.constants import MAX_POSITION, MIN_POSITION, DEFAULT_SPEED
from app.controllers.motor_controller import MotorController
from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF


class TextProgramService:
    """Интерпретатор текстовых робот-программ."""

    def __init__(self, controller: MotorController):
        self.controller = controller
        self.kinematics = RobotKinematics6DOF()
        self.ik_solver = InverseKinematics6DOF(self.kinematics)

        self._stop_flag = False
        self._speed = DEFAULT_SPEED  # step/s

        # Переменные (для FOR, WHILE, IF)
        self._vars: dict[str, float] = {}
        self._current_line = 0

        # Стеки для циклов
        self._for_stack: list[dict] = []      # {var, start, end, body_start}
        self._while_stack: list[dict] = []    # {body_start}

        # Стек условий
        self._if_level = 0
        self._skip_level = 0  # для пропуска ELSE/END_IF

        # Карта меток
        self._labels: dict[str, int] = {}

        self._parsed_lines: list[tuple[int, str, list]] = []  # (line_no, cmd, args)

    def stop(self):
        self._stop_flag = True

    def _log(self, msg: str, level: str = "info"):
        print(f"[{level.upper()}] {msg}")

    def _angle_to_pos(self, angle: float) -> int:
        return max(MIN_POSITION, min(MAX_POSITION, int((angle + 180) / 360 * MAX_POSITION)))

    def _pos_to_angle(self, pos: int) -> float:
        return (pos / MAX_POSITION) * 360 - 180

    def parse(self, text: str) -> list[tuple[int, str, list]]:
        """Парсинг текста в список команд."""
        lines = []
        self._labels.clear()
        for lineno, raw in enumerate(text.split("\n"), 1):
            line = raw.strip()
            if not line or line.startswith("//"):
                continue

            # Убираем inline-комментарий
            if "//" in line:
                line = line.split("//")[0].strip()

            # Парсим команду
            cmd, args = self._parse_line(line, lineno)
            if cmd is None:
                continue

            # Если это метка — запоминаем
            if cmd == "LABEL":
                self._labels[args[0]] = lineno
                continue

            lines.append((lineno, cmd, args))

        self._parsed_lines = lines
        return lines

    def _parse_line(self, line: str, lineno: int) -> tuple[str | None, list]:
        """Парсинг одной строки."""
        # LABEL(name)
        m = re.match(r"LABEL\s*\(\s*([^)]+)\s*\)", line, re.IGNORECASE)
        if m:
            return "LABEL", [m.group(1).strip()]

        # FOR var = start TO end
        m = re.match(
            r"FOR\s+(\w+)\s*=\s*([\d.-]+)\s+TO\s+([\d.-]+)",
            line, re.IGNORECASE,
        )
        if m:
            return "FOR", [m.group(1), float(m.group(2)), float(m.group(3))]

        m = re.match(r"END_FOR", line, re.IGNORECASE)
        if m:
            return "END_FOR", []

        # WHILE condition
        m = re.match(r"WHILE\s+(.+)", line, re.IGNORECASE)
        if m:
            return "WHILE", [m.group(1).strip()]

        m = re.match(r"END_WHILE", line, re.IGNORECASE)
        if m:
            return "END_WHILE", []

        # IF condition
        m = re.match(r"IF\s+(.+)", line, re.IGNORECASE)
        if m:
            return "IF", [m.group(1).strip()]

        m = re.match(r"ELSE", line, re.IGNORECASE)
        if m:
            return "ELSE", []

        m = re.match(r"END_IF", line, re.IGNORECASE)
        if m:
            return "END_IF", []

        # GOTO(label)
        m = re.match(r"GOTO\s*\(\s*([^)]+)\s*\)", line, re.IGNORECASE)
        if m:
            return "GOTO", [m.group(1).strip()]

        # SUB(name)
        m = re.match(r"SUB\s*\(\s*([^)]+)\s*\)", line, re.IGNORECASE)
        if m:
            return "SUB", [m.group(1).strip()]

        m = re.match(r"RETURN", line, re.IGNORECASE)
        if m:
            return "RETURN", []

        # MOVE_J(joint, angle)
        m = re.match(r"MOVE_J\s*\(\s*(\d+)\s*,\s*([\d.-]+)\s*\)", line, re.IGNORECASE)
        if m:
            return "MOVE_J", [int(m.group(1)) - 1, float(m.group(2))]

        # MOVE_XYZ(x, y, z)
        m = re.match(
            r"MOVE_XYZ\s*\(\s*([\d.-]+)\s*,\s*([\d.-]+)\s*,\s*([\d.-]+)\s*\)",
            line, re.IGNORECASE,
        )
        if m:
            return "MOVE_XYZ", [float(m.group(1)), float(m.group(2)), float(m.group(3))]

        # HOME(), CENTER()
        m = re.match(r"(HOME|CENTER)\s*\(\s*\)", line, re.IGNORECASE)
        if m:
            return m.group(1).upper(), []

        # SPEED(percent)
        m = re.match(r"SPEED\s*\(\s*([\d.]+)\s*\)", line, re.IGNORECASE)
        if m:
            return "SPEED", [float(m.group(1))]

        # TORQUE(joint, ON/OFF)
        m = re.match(r"TORQUE\s*\(\s*(\w+)\s*,\s*(ON|OFF)\s*\)", line, re.IGNORECASE)
        if m:
            j = m.group(1).upper()
            j_idx = -1 if j == "ALL" else int(j) - 1
            return "TORQUE", [j_idx, m.group(2).upper()]

        # GRIPPER(OPEN) or GRIPPER(CLOSE, force)
        m = re.match(r"GRIPPER\s*\(\s*(\w+)\s*(?:,\s*([\d.]+))?\s*\)", line, re.IGNORECASE)
        if m:
            return "GRIPPER", [m.group(1).upper(), float(m.group(2) or 50)]

        # WAIT(seconds)
        m = re.match(r"WAIT\s*\(\s*([\d.]+)\s*\)", line, re.IGNORECASE)
        if m:
            return "WAIT", [float(m.group(1))]

        # PRINT(text)
        m = re.match(r"PRINT\s*\(\s*(.+)\s*\)", line, re.IGNORECASE)
        if m:
            return "PRINT", [m.group(1).strip().strip("\"'")]

        # ASSIGN (var = value)
        m = re.match(r"(\w+)\s*=\s*([\d.-]+)", line)
        if m:
            return "ASSIGN", [m.group(1), float(m.group(2))]

        self._log(f"Syntax error at line {lineno}: {line}", "error")
        return None, []

    def _eval_condition(self, cond: str) -> bool:
        """Вычисление условия IF/WHILE."""
        cond = cond.strip()
        # Простые сравнения: var > val, var < val, var == val
        m = re.match(r"(\w+)\s*(==|!=|>=|<=|>|<)\s*([\d.-]+)", cond)
        if m:
            var = m.group(1)
            op = m.group(2)
            val = float(m.group(3))
            actual = self._vars.get(var, 0)
            if op == "==":
                return abs(actual - val) < 0.001
            elif op == "!=":
                return abs(actual - val) >= 0.001
            elif op == ">=":
                return actual >= val
            elif op == "<=":
                return actual <= val
            elif op == ">":
                return actual > val
            elif op == "<":
                return actual < val
        # True / false
        if cond.lower() == "true":
            return True
        if cond.lower() == "false":
            return False
        # connected / not_connected
        if cond.lower() == "connected":
            return bool(self.controller and self.controller.connected)
        if cond.lower() == "not_connected":
            return not (self.controller and self.controller.connected)
        return True  # fallback

    def execute(self, text: str, log_callback=None):
        """Выполнить текстовую программу."""
        if log_callback:
            self._log = log_callback

        self._stop_flag = False
        self._vars.clear()
        self._for_stack.clear()
        self._while_stack.clear()
        self._if_level = 0
        self._skip_level = 0

        lines = self.parse(text)
        if not lines:
            self._log("No commands to execute", "warning")
            return

        i = 0
        while i < len(lines):
            if self._stop_flag:
                self._log("Program stopped by user", "warning")
                return

            lineno, cmd, args = lines[i]

            try:
                # ── Управляющие конструкции ──
                if cmd == "FOR":
                    var, start, end = args
                    self._vars[var] = start
                    self._for_stack.append({
                        "var": var, "end": end, "body_start": i, "line": lineno,
                    })
                    i += 1
                    continue

                elif cmd == "END_FOR":
                    if self._for_stack:
                        loop = self._for_stack[-1]
                        var = loop["var"]
                        self._vars[var] = self._vars.get(var, 0) + 1
                        if self._vars[var] <= loop["end"]:
                            i = loop["body_start"] + 1
                            continue
                        self._for_stack.pop()
                    i += 1
                    continue

                elif cmd == "WHILE":
                    skip = not self._eval_condition(args[0])
                    self._while_stack.append({
                        "body_start": i, "condition": args[0], "skip": skip, "line": lineno,
                    })
                    if skip:
                        # Пропускаем тело до END_WHILE
                        depth = 1
                        while depth > 0 and i < len(lines):
                            i += 1
                            if i >= len(lines):
                                break
                            c = lines[i][1]
                            if c == "WHILE":
                                depth += 1
                            elif c == "END_WHILE":
                                depth -= 1
                        self._while_stack.pop()
                        i += 1
                        continue
                    i += 1
                    continue

                elif cmd == "END_WHILE":
                    if self._while_stack:
                        loop = self._while_stack[-1]
                        if not loop["skip"] and self._eval_condition(loop["condition"]):
                            i = loop["body_start"] + 1
                            continue
                        self._while_stack.pop()
                    i += 1
                    continue

                elif cmd == "IF":
                    skip = not self._eval_condition(args[0])
                    self._if_level += 1
                    if skip:
                        self._skip_level = self._if_level
                    self._vars["_if_skip_" + str(self._if_level)] = 1 if skip else 0
                    i += 1
                    continue

                elif cmd == "ELSE":
                    skip_level = None
                    for key, val in list(self._vars.items()):
                        if key.startswith("_if_skip_"):
                            skip_level = key
                    if skip_level:
                        # Инвертируем пропуск
                        self._vars[skip_level] = 1 - self._vars[skip_level]
                    i += 1
                    continue

                elif cmd == "END_IF":
                    for key in list(self._vars.keys()):
                        if key.startswith("_if_skip_"):
                            del self._vars[key]
                    self._if_level = max(0, self._if_level - 1)
                    i += 1
                    continue

                elif cmd == "GOTO":
                    label = args[0]
                    if label in self._labels:
                        # Ищем номер строки в parsed_lines
                        for idx, (ln, c, a) in enumerate(lines):
                            if ln == self._labels[label]:
                                i = idx
                                break
                        else:
                            i += 1
                    else:
                        self._log(f"Label not found: {label} (line {lineno})", "error")
                        i += 1
                    continue

                elif cmd == "SUB":
                    self._log(f"Subroutine call: {args[0]} (line {lineno})", "info")
                    # В данной реализации SUB — как PRINT
                    i += 1
                    continue

                elif cmd == "RETURN":
                    i += 1
                    continue

                # ── Проверка пропуска (IF false) ──
                skip = False
                for key, val in self._vars.items():
                    if key.startswith("_if_skip_") and val == 1:
                        skip = True
                        break

                if skip:
                    i += 1
                    continue

                # ── Исполняемые команды ──
                if cmd == "MOVE_J":
                    j, angle = args
                    pos = self._angle_to_pos(angle)
                    if self.controller and self.controller.connected:
                        self.controller.move_joint(j, pos, speed=self._speed)
                    self._log(f"J{j+1} → {pos} ({angle}°)", "info")

                elif cmd == "MOVE_XYZ":
                    x, y, z = args
                    result = self.ik_solver.solve(x, y, z)
                    if result is None:
                        self._log(f"Point ({x},{y},{z}) unreachable (line {lineno})", "error")
                    elif self.controller and self.controller.connected:
                        for j, angle in enumerate(result):
                            pos = self._angle_to_pos(angle)
                            self.controller.move_joint(j, pos, speed=self._speed)
                        self._log(f"XYZ({x},{y},{z}) → OK", "info")

                elif cmd == "HOME":
                    if self.controller and self.controller.connected:
                        for j in range(6):
                            self.controller.move_joint(j, 0, speed=self._speed)
                        self._log("HOME position", "success")

                elif cmd == "CENTER":
                    if self.controller and self.controller.connected:
                        for j in range(6):
                            self.controller.move_joint(j, 2048, speed=self._speed)
                        self._log("CENTER position", "success")

                elif cmd == "SPEED":
                    pct = max(0, min(100, args[0]))
                    self._speed = int(100 + (pct / 100) * 4900)
                    self._log(f"Speed: {pct}% ({self._speed} step/s)", "info")

                elif cmd == "TORQUE":
                    j_idx, state = args
                    if self.controller and self.controller.connected:
                        on = state == "ON"
                        if j_idx == -1:
                            for j in range(6):
                                mid = self.controller.get_motor_id_for_joint(j)
                                self.controller.toggle_torque(mid, on)
                        else:
                            mid = self.controller.get_motor_id_for_joint(j_idx)
                            self.controller.toggle_torque(mid, on)
                        self._log(f"Torque {'ON' if on else 'OFF'} {'ALL' if j_idx==-1 else j_idx+1}", "info")

                elif cmd == "GRIPPER":
                    action, force = args
                    self._log(f"Gripper {action} (force: {force}%)", "info")

                elif cmd == "WAIT":
                    time.sleep(max(0, args[0]))

                elif cmd == "PRINT":
                    self._log(args[0], "info")

                elif cmd == "ASSIGN":
                    var, val = args
                    self._vars[var] = val

            except Exception as e:
                self._log(f"Error at line {lineno}: {e}", "error")
                if self._stop_flag:
                    return

            i += 1

        self._log("Program completed", "success")
