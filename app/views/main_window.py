#!/usr/bin/env python3

"""
Main Window Module — FANUC-Style Robot Control GUI

Главное окно приложения управления роботом с интерфейсом
в стиле промышленных контроллеров FANUC.
"""

import json
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import matplotlib.pyplot as plt

from app.config.constants import (
    BASE_WINDOW_HEIGHT,
    BASE_WINDOW_WIDTH,
    DEFAULT_SPEED,
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    JOG_MODE_CARTESIAN,
    JOG_MODE_JOINT,
    MAX_POSITION,
    MAX_SCALE_PERCENT,
    MIN_SCALE_PERCENT,
    MONITOR_INTERVAL,
    SPEED_OVERRIDE_DEFAULT,
    SPEED_OVERRIDE_MAX,
    SPEED_OVERRIDE_MIN,
    TEXT_COLOR,
    WINDOW_SCALE_PERCENT,
)
from app.controllers import MotorController, MotorMonitor
from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF
from app.utils.config_manager import ConfigManager
from app.utils.logger import AppLogger
from app.utils.program_executor import ProgramExecutor
from app.views.ai_control_panel import AIControlPanel
from app.views.block_programming import BlockPalette, ProgramCanvas
from app.views.bottom_monitor_panel import BottomMonitorPanel
from app.views.kinematics_3d_panel import Kinematics3DPanel
from app.views.manual_control_panel import ManualControlPanel
from app.views.motor_mapping_panel import MotorMappingPanel
from app.views.vision_tracker_panel import VisionTrackerPanel


class FANUCStatusBar(tk.Frame):
    """
    Верхняя строка статуса в стиле FANUC iPendant.

    Показывает: режим | скорость % | координатная система | статус
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=FANUC_BG, height=36, **kwargs)
        self.pack_propagate(False)

        # Режим работы
        self.mode_label = tk.Label(
            self,
            text="JOINT",
            font=("SF Mono", 11, "bold"),
            bg=FANUC_BG,
            fg=FANUC_GREEN,
            padx=8,
        )
        self.mode_label.pack(side="left", padx=(10, 5))

        self._sep(self)

        # Скорость override
        self.speed_pct_label = tk.Label(
            self,
            text="50%",
            font=("Consolas", 11, "bold"),
            bg=FANUC_BG,
            fg=FANUC_ORANGE,
            padx=8,
        )
        self.speed_pct_label.pack(side="left", padx=5)

        self._sep(self)

        # Координатная система
        self.coord_label = tk.Label(
            self,
            text="WORLD",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_BLUE,
            padx=8,
        )
        self.coord_label.pack(side="left", padx=5)

        self._sep(self)

        # Статус программы
        self.prog_status_label = tk.Label(
            self,
            text="IDLE",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_GRAY,
            padx=8,
        )
        self.prog_status_label.pack(side="left", padx=5)

        # Правая часть — часы + cycle counter
        self.clock_label = tk.Label(
            self,
            text="00:00:00",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_GRAY,
            padx=8,
        )
        self.clock_label.pack(side="right", padx=10)

        self.cycle_label = tk.Label(
            self,
            text="CYCLE: 0",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_GRAY,
            padx=8,
        )
        self.cycle_label.pack(side="right", padx=5)

        # Индикатор подключения
        self.conn_canvas = tk.Canvas(self, width=14, height=14, bg=FANUC_BG, highlightthickness=0)
        self.conn_canvas.pack(side="right", padx=5)
        self.set_connected(False)

        self._update_clock()

    @staticmethod
    def _sep(parent):
        tk.Frame(parent, width=1, bg=FANUC_GRAY).pack(side="left", fill="y", padx=4, pady=6)

    def _update_clock(self):
        self.clock_label.config(text=time.strftime("%H:%M:%S"))
        self.after(1000, self._update_clock)

    def set_mode(self, mode: str):
        self.mode_label.config(text=mode.upper())

    def set_speed_pct(self, pct: int):
        color = FANUC_GREEN if pct >= 50 else FANUC_ORANGE if pct >= 20 else FANUC_RED
        self.speed_pct_label.config(text=f"{pct}%", fg=color)

    def set_prog_status(self, status: str):
        colors = {
            "IDLE": FANUC_GRAY,
            "RUN": FANUC_GREEN,
            "PAUSE": FANUC_ORANGE,
            "ABORT": FANUC_RED,
            "DONE": FANUC_BLUE,
        }
        self.prog_status_label.config(text=status, fg=colors.get(status, FANUC_TEXT))

    def set_connected(self, connected: bool):
        self.conn_canvas.delete("all")
        color = FANUC_GREEN if connected else FANUC_RED
        self.conn_canvas.create_oval(2, 2, 12, 12, fill=color, outline="")

    def set_cycle(self, count: int):
        self.cycle_label.config(text=f"CYCLE: {count}")


# ============================================================
#  Position Register Panel
# ============================================================


class PositionRegisterPanel(ttk.Frame):
    """
    Панель позиционных регистров (PR) в стиле FANUC.
    Сохранение/загрузка точек.
    """

    def __init__(self, parent, controller, kinematics, log_callback):
        super().__init__(parent)
        self.controller = controller
        self.kinematics = kinematics
        self.ik_solver = InverseKinematics6DOF(kinematics)
        self.log = log_callback

        # Регистры: {index: {'angles': [...], 'comment': str}}
        self.registers: dict[int, dict] = {}

        self._create_widgets()

    def _create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Заголовок
        header = tk.Frame(main, bg=FANUC_PANEL)
        header.pack(fill="x", pady=(0, 10))

        tk.Label(
            header,
            text="POSITION REGISTERS (PR)",
            font=("Consolas", 14, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_GREEN,
        ).pack(side="left", padx=10, pady=5)

        # Кнопки
        btn_frame = tk.Frame(header, bg=FANUC_PANEL)
        btn_frame.pack(side="right", padx=10)

        tk.Button(
            btn_frame,
            text="RECORD",
            font=("Arial", 9, "bold"),
            bg=FANUC_GREEN,
            fg=FANUC_TEXT,
            bd=0,
            padx=12,
            pady=4,
            command=self._record_current,
        ).pack(side="left", padx=3)

        tk.Button(
            btn_frame,
            text="MOVE TO",
            font=("Arial", 9, "bold"),
            bg=FANUC_BLUE,
            fg=FANUC_TEXT,
            bd=0,
            padx=12,
            pady=4,
            command=self._move_to_selected,
        ).pack(side="left", padx=3)

        tk.Button(
            btn_frame,
            text="DELETE",
            font=("Arial", 9, "bold"),
            bg=FANUC_RED,
            fg=FANUC_TEXT,
            bd=0,
            padx=12,
            pady=4,
            command=self._delete_selected,
        ).pack(side="left", padx=3)

        tk.Button(
            btn_frame,
            text="CLEAR ALL",
            font=("Arial", 9, "bold"),
            bg=FANUC_ORANGE,
            fg=FANUC_TEXT,
            bd=0,
            padx=12,
            pady=4,
            command=self._clear_all,
        ).pack(side="left", padx=3)

        # XYZ ввод для записи по координатам
        input_frame = ttk.LabelFrame(main, text="MANUAL INPUT (XYZ mm)")
        input_frame.pack(fill="x", pady=(0, 10))

        coords_frame = tk.Frame(input_frame, bg=FANUC_PANEL)
        coords_frame.pack(fill="x", padx=10, pady=8)

        self.xyz_vars = {}
        for i, (label, color) in enumerate(
            [("X", FANUC_RED), ("Y", FANUC_GREEN), ("Z", FANUC_BLUE)]
        ):
            tk.Label(
                coords_frame,
                text=f"{label}:",
                font=("Consolas", 11, "bold"),
                bg=FANUC_PANEL,
                fg=color,
            ).grid(row=0, column=i * 2, padx=(10, 2))

            var = tk.DoubleVar(value=0.0)
            self.xyz_vars[label.lower()] = var
            ttk.Spinbox(
                coords_frame,
                from_=-400,
                to=400,
                textvariable=var,
                width=8,
                font=("Consolas", 11),
                increment=5.0,
            ).grid(row=0, column=i * 2 + 1, padx=(2, 10))

        tk.Button(
            coords_frame,
            text="CALC IK + RECORD",
            font=("Arial", 9, "bold"),
            bg="#7B68EE",
            fg=FANUC_TEXT,
            bd=0,
            padx=12,
            pady=4,
            command=self._record_from_xyz,
        ).grid(row=0, column=6, padx=10)

        # Таблица регистров
        table_frame = ttk.Frame(main)
        table_frame.pack(fill="both", expand=True)

        columns = ("pr", "j1", "j2", "j3", "j4", "j5", "j6", "x", "y", "z", "comment")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        col_widths = {
            "pr": 50,
            "j1": 65,
            "j2": 65,
            "j3": 65,
            "j4": 65,
            "j5": 65,
            "j6": 65,
            "x": 70,
            "y": 70,
            "z": 70,
            "comment": 150,
        }
        col_titles = {
            "pr": "PR#",
            "j1": "J1",
            "j2": "J2",
            "j3": "J3",
            "j4": "J4",
            "j5": "J5",
            "j6": "J6",
            "x": "X mm",
            "y": "Y mm",
            "z": "Z mm",
            "comment": "Comment",
        }

        for col in columns:
            self.tree.heading(col, text=col_titles[col])
            self.tree.column(col, width=col_widths[col], anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Нижний статус
        self.status_label = tk.Label(
            main,
            text="0 registers",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_GRAY,
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(5, 0))

    def _get_current_angles(self) -> list[float]:
        """Получить текущие углы суставов."""
        angles = []
        for joint_idx in range(6):
            motor_id = self.controller.get_motor_id_for_joint(joint_idx)
            pos = self.controller.joint_positions.get(motor_id, 2048)
            angle = (pos / MAX_POSITION) * 360 - 180
            angles.append(round(angle, 1))
        return angles

    def _next_pr_index(self) -> int:
        if not self.registers:
            return 1
        return max(self.registers.keys()) + 1

    def _record_current(self):
        angles = self._get_current_angles()
        pos = self.kinematics.get_end_effector_position(angles)
        pr_idx = self._next_pr_index()

        self.registers[pr_idx] = {
            "angles": angles,
            "xyz": [round(pos[0], 1), round(pos[1], 1), round(pos[2], 1)],
            "comment": f"Recorded {time.strftime('%H:%M:%S')}",
        }
        self._refresh_table()
        self.log(f"PR[{pr_idx}] recorded: {angles}", "success")

    def _record_from_xyz(self):
        x = self.xyz_vars["x"].get()
        y = self.xyz_vars["y"].get()
        z = self.xyz_vars["z"].get()

        result = self.ik_solver.solve(x, y, z)
        if result is None:
            self.log(f"IK failed for ({x}, {y}, {z})", "error")
            messagebox.showerror("IK Error", f"Point ({x}, {y}, {z}) is unreachable!")
            return

        angles = [round(a, 1) for a in result]
        pr_idx = self._next_pr_index()

        self.registers[pr_idx] = {
            "angles": angles,
            "xyz": [round(x, 1), round(y, 1), round(z, 1)],
            "comment": f"IK ({x:.0f},{y:.0f},{z:.0f})",
        }
        self._refresh_table()
        self.log(f"PR[{pr_idx}] from IK: ({x},{y},{z}) -> {angles}", "success")

    def _move_to_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a register first!")
            return

        item = self.tree.item(selected[0])
        pr_idx = int(item["values"][0])
        if pr_idx not in self.registers:
            return

        reg = self.registers[pr_idx]
        angles = reg["angles"]

        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return

        for i, angle in enumerate(angles):
            position = int((angle + 180) / 360 * MAX_POSITION)
            position = max(0, min(MAX_POSITION, position))
            motor_id = self.controller.get_motor_id_for_joint(i)
            self.controller.move_to_position(motor_id, position)

        self.log(f"Moving to PR[{pr_idx}]: {angles}", "info")

    def _delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        pr_idx = int(item["values"][0])
        self.registers.pop(pr_idx, None)
        self._refresh_table()

    def _clear_all(self):
        if messagebox.askyesno("Confirm", "Clear all position registers?"):
            self.registers.clear()
            self._refresh_table()
            self.log("All registers cleared", "warning")

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for pr_idx in sorted(self.registers.keys()):
            reg = self.registers[pr_idx]
            angles = reg["angles"]
            xyz = reg.get("xyz", [0, 0, 0])
            comment = reg.get("comment", "")
            self.tree.insert(
                "",
                "end",
                values=(
                    pr_idx,
                    f"{angles[0]:.1f}",
                    f"{angles[1]:.1f}",
                    f"{angles[2]:.1f}",
                    f"{angles[3]:.1f}",
                    f"{angles[4]:.1f}",
                    f"{angles[5]:.1f}",
                    f"{xyz[0]:.1f}",
                    f"{xyz[1]:.1f}",
                    f"{xyz[2]:.1f}",
                    comment,
                ),
            )
        self.status_label.config(text=f"{len(self.registers)} registers")

    def save_registers(self, filename: str):
        data = {}
        for k, v in self.registers.items():
            data[str(k)] = v
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_registers(self, filename: str):
        with open(filename, encoding="utf-8") as f:
            data = json.load(f)
        self.registers = {int(k): v for k, v in data.items()}
        self._refresh_table()


# ============================================================
#  Teach Pendant Panel
# ============================================================


class TeachPendantPanel(ttk.Frame):
    """
    Панель Teach Pendant — запись и воспроизведение траекторий.
    """

    def __init__(self, parent, controller, kinematics, log_callback):
        super().__init__(parent)
        self.controller = controller
        self.kinematics = kinematics
        self.log = log_callback

        self.teach_points: list[dict] = []
        self.is_playing = False
        self._stop_flag = False

        self._create_widgets()

    def _create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Заголовок
        header = tk.Frame(main, bg=FANUC_PANEL)
        header.pack(fill="x", pady=(0, 10))

        tk.Label(
            header,
            text="TEACH PENDANT",
            font=("Consolas", 14, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_GREEN,
        ).pack(side="left", padx=10, pady=5)

        # Кнопки управления
        ctrl_frame = ttk.LabelFrame(main, text="CONTROLS")
        ctrl_frame.pack(fill="x", pady=(0, 10))

        btn_row = tk.Frame(ctrl_frame, bg=FANUC_PANEL)
        btn_row.pack(fill="x", padx=10, pady=8)

        buttons = [
            ("TEACH POINT", FANUC_GREEN, "black", self._teach_point),
            ("PLAY ALL", FANUC_BLUE, "white", self._play_all),
            ("PLAY ONCE", "#7B68EE", "white", self._play_once),
            ("STOP", FANUC_RED, "white", self._stop_play),
            ("CLEAR ALL", FANUC_ORANGE, "white", self._clear_all),
        ]

        for text, bg, fg, cmd in buttons:
            tk.Button(
                btn_row,
                text=text,
                font=("Arial", 10, "bold"),
                bg=bg,
                fg=fg,
                bd=0,
                padx=14,
                pady=6,
                command=cmd,
            ).pack(side="left", padx=4)

        # Настройки
        settings_frame = tk.Frame(ctrl_frame, bg=FANUC_PANEL)
        settings_frame.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(
            settings_frame,
            text="Delay (s):",
            font=("Arial", 10),
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
        ).pack(side="left", padx=5)

        self.delay_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(
            settings_frame,
            from_=0.1,
            to=10.0,
            textvariable=self.delay_var,
            width=6,
            increment=0.1,
            font=("Consolas", 10),
        ).pack(side="left", padx=5)

        tk.Label(
            settings_frame,
            text="Loops:",
            font=("Arial", 10),
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
        ).pack(side="left", padx=(20, 5))

        self.loop_var = tk.IntVar(value=1)
        ttk.Spinbox(
            settings_frame,
            from_=1,
            to=100,
            textvariable=self.loop_var,
            width=5,
            font=("Consolas", 10),
        ).pack(side="left", padx=5)

        self.play_status = tk.Label(
            settings_frame,
            text="IDLE",
            font=("Consolas", 10, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_GRAY,
        )
        self.play_status.pack(side="right", padx=10)

        # Таблица точек
        table_frame = ttk.Frame(main)
        table_frame.pack(fill="both", expand=True)

        columns = ("idx", "j1", "j2", "j3", "j4", "j5", "j6", "x", "y", "z")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)

        for col in columns:
            title = col.upper() if col != "idx" else "#"
            width = 50 if col == "idx" else 75
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Удаление по кнопке
        del_frame = tk.Frame(main, bg=FANUC_BG)
        del_frame.pack(fill="x", pady=5)

        tk.Button(
            del_frame,
            text="DELETE SELECTED",
            font=("Arial", 9, "bold"),
            bg=FANUC_RED,
            fg=FANUC_TEXT,
            bd=0,
            padx=10,
            pady=3,
            command=self._delete_selected,
        ).pack(side="left")

        self.count_label = tk.Label(
            del_frame,
            text="0 points",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_GRAY,
        )
        self.count_label.pack(side="right")

    def _get_current_state(self) -> dict:
        angles = []
        for joint_idx in range(6):
            motor_id = self.controller.get_motor_id_for_joint(joint_idx)
            pos = self.controller.joint_positions.get(motor_id, 2048)
            angle = (pos / MAX_POSITION) * 360 - 180
            angles.append(round(angle, 1))
        xyz = self.kinematics.get_end_effector_position(angles)
        return {
            "angles": angles,
            "xyz": [round(xyz[0], 1), round(xyz[1], 1), round(xyz[2], 1)],
        }

    def _teach_point(self):
        state = self._get_current_state()
        self.teach_points.append(state)
        self._refresh_table()
        self.log(f"Taught point #{len(self.teach_points)}: {state['angles']}", "success")

    def _play_all(self):
        if not self.teach_points:
            messagebox.showwarning("Warning", "No taught points!")
            return
        self._stop_flag = False
        self.is_playing = True
        threading.Thread(target=self._play_thread, args=(self.loop_var.get(),), daemon=True).start()

    def _play_once(self):
        if not self.teach_points:
            messagebox.showwarning("Warning", "No taught points!")
            return
        self._stop_flag = False
        self.is_playing = True
        threading.Thread(target=self._play_thread, args=(1,), daemon=True).start()

    def _play_thread(self, loops: int):
        self.after(0, lambda: self.play_status.config(text="RUNNING", fg=FANUC_GREEN))
        delay = self.delay_var.get()

        for loop_i in range(loops):
            if self._stop_flag:
                break
            for i, point in enumerate(self.teach_points):
                if self._stop_flag:
                    break
                self.after(0, lambda idx=i: self._highlight_row(idx))

                # Двигаем моторы
                for j, angle in enumerate(point["angles"]):
                    position = int((angle + 180) / 360 * MAX_POSITION)
                    position = max(0, min(MAX_POSITION, position))
                    motor_id = self.controller.get_motor_id_for_joint(j)
                    self.controller.move_to_position(motor_id, position)

                time.sleep(delay)

        self.is_playing = False
        self.after(0, lambda: self.play_status.config(text="DONE", fg=FANUC_BLUE))

    def _stop_play(self):
        self._stop_flag = True
        self.is_playing = False
        self.play_status.config(text="STOPPED", fg=FANUC_RED)

    def _highlight_row(self, idx: int):
        for item in self.tree.get_children():
            self.tree.item(item, tags=())
        items = self.tree.get_children()
        if idx < len(items):
            self.tree.item(items[idx], tags=("active",))
            self.tree.tag_configure("active", background="#2a4a2a")
            self.tree.see(items[idx])

    def _delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        idx = int(item["values"][0]) - 1
        if 0 <= idx < len(self.teach_points):
            self.teach_points.pop(idx)
            self._refresh_table()

    def _clear_all(self):
        if messagebox.askyesno("Confirm", "Clear all taught points?"):
            self.teach_points.clear()
            self._refresh_table()

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for i, pt in enumerate(self.teach_points):
            a = pt["angles"]
            xyz = pt.get("xyz", [0, 0, 0])
            self.tree.insert(
                "",
                "end",
                values=(
                    i + 1,
                    f"{a[0]:.1f}",
                    f"{a[1]:.1f}",
                    f"{a[2]:.1f}",
                    f"{a[3]:.1f}",
                    f"{a[4]:.1f}",
                    f"{a[5]:.1f}",
                    f"{xyz[0]:.1f}",
                    f"{xyz[1]:.1f}",
                    f"{xyz[2]:.1f}",
                ),
            )
        self.count_label.config(text=f"{len(self.teach_points)} points")


# ============================================================
#  Alarm History Panel
# ============================================================


class AlarmHistoryPanel(ttk.Frame):
    """Панель истории аварий/предупреждений в стиле FANUC."""

    def __init__(self, parent):
        super().__init__(parent)
        self.alarms: list[dict] = []
        self._create_widgets()

    def _create_widgets(self):
        header = tk.Frame(self, bg=FANUC_PANEL)
        header.pack(fill="x")

        tk.Label(
            header,
            text="ALARM HISTORY",
            font=("Consolas", 14, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_RED,
        ).pack(side="left", padx=10, pady=5)

        tk.Button(
            header,
            text="CLEAR",
            font=("Arial", 9, "bold"),
            bg=FANUC_ORANGE,
            fg=FANUC_TEXT,
            bd=0,
            padx=10,
            pady=3,
            command=self._clear,
        ).pack(side="right", padx=10, pady=5)

        columns = ("time", "level", "message")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        self.tree.heading("time", text="Time")
        self.tree.heading("level", text="Level")
        self.tree.heading("message", text="Message")
        self.tree.column("time", width=100)
        self.tree.column("level", width=80)
        self.tree.column("message", width=500)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

    def add_alarm(self, level: str, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.alarms.insert(0, {"time": timestamp, "level": level, "message": message})
        # Ограничение 500 записей
        if len(self.alarms) > 500:
            self.alarms = self.alarms[:500]

        tag = "error" if level == "ERROR" else "warning" if level == "WARNING" else "info"
        self.tree.insert("", 0, values=(timestamp, level, message), tags=(tag,))
        self.tree.tag_configure("error", foreground=FANUC_RED)
        self.tree.tag_configure("warning", foreground=FANUC_ORANGE)
        self.tree.tag_configure("info", foreground=FANUC_TEXT)

    def _clear(self):
        self.alarms.clear()
        self.tree.delete(*self.tree.get_children())


# ============================================================
#  Main Window
# ============================================================


class RobotControlGUI(tk.Tk):
    """
    Главное окно приложения управления роботом ST3215
    в стиле FANUC iPendant.
    """

    def __init__(self):
        super().__init__()

        self.title("ST3215 Robot Control v7.0 | FANUC iPendant Style")

        # Масштабирование окна под размер монитора
        screen_width = self.winfo_screenwidth()

        # Рассчитываем масштаб на основе ширины экрана
        scale_percent = (screen_width / BASE_WINDOW_WIDTH) * 100
        # Ограничиваем масштаб в пределах MIN_SCALE_PERCENT - MAX_SCALE_PERCENT
        scale_percent = max(MIN_SCALE_PERCENT, min(MAX_SCALE_PERCENT, scale_percent))

        # Применяем WINDOW_SCALE_PERCENT к рассчитанному масштабу
        final_scale = (scale_percent / 100) * (WINDOW_SCALE_PERCENT / 100)

        window_width = int(BASE_WINDOW_WIDTH * final_scale)
        window_height = int(BASE_WINDOW_HEIGHT * final_scale)

        self.geometry(f"{window_width}x{window_height}")
        self.minsize(
            int(BASE_WINDOW_WIDTH * MIN_SCALE_PERCENT / 100),
            int(BASE_WINDOW_HEIGHT * MIN_SCALE_PERCENT / 100),
        )
        self.configure(bg=FANUC_BG)

        # Компоненты
        self.controller = MotorController()
        self.monitor: MotorMonitor | None = None
        self.logger = AppLogger("robot_gui")
        self.config_manager = ConfigManager()
        self.program_executor: ProgramExecutor | None = None
        self.kinematics = RobotKinematics6DOF()

        # GUI панели
        self.motor_mapping_panel: MotorMappingPanel | None = None
        self.manual_panel: ManualControlPanel | None = None
        self.bottom_monitor: BottomMonitorPanel | None = None
        self.kinematics_panel: Kinematics3DPanel | None = None
        self.program_canvas: ProgramCanvas | None = None
        self.block_palette: BlockPalette | None = None
        self.position_register_panel: PositionRegisterPanel | None = None
        self.teach_panel: TeachPendantPanel | None = None
        self.alarm_panel: AlarmHistoryPanel | None = None
        self.fanuc_status_bar: FANUCStatusBar | None = None

        # Состояние
        self._monitor_update_pending = False
        self.speed_override = SPEED_OVERRIDE_DEFAULT
        self.jog_mode = JOG_MODE_JOINT
        self.cycle_count = 0

        # XYZ координаты
        self.tool_x_var = tk.StringVar(value="0.00")
        self.tool_y_var = tk.StringVar(value="0.00")
        self.tool_z_var = tk.StringVar(value="0.00")
        self.tool_rx_var = tk.StringVar(value="0.00")
        self.tool_ry_var = tk.StringVar(value="0.00")
        self.tool_rz_var = tk.StringVar(value="0.00")

        self._setup_styles()
        self._create_widgets()
        self._create_menu()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._bind_keyboard_shortcuts()

        self._log("ST3215 Robot Control v7.0 started", "success")
        self.controller.load_config()

    # ---- Styles ----

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TLabel", background=FANUC_BG, foreground=FANUC_TEXT, font=("Arial", 10))
        style.configure(
            "Header.TLabel",
            font=("Arial", 14, "bold"),
            foreground=FANUC_GREEN,
            background=FANUC_BG,
        )
        style.configure("TButton", font=("Arial", 10, "bold"), padding=5)
        style.configure(
            "Connect.TButton",
            font=("Arial", 12, "bold"),
            foreground="white",
            background=FANUC_BLUE,
            padding=10,
        )
        style.configure(
            "Emergency.TButton",
            font=("Arial", 14, "bold"),
            foreground="white",
            background="#cc0000",
            padding=15,
        )
        style.configure("TLabelframe", background=FANUC_PANEL, foreground=FANUC_TEXT)
        style.configure(
            "TLabelframe.Label",
            background=FANUC_PANEL,
            foreground=FANUC_GREEN,
            font=("Arial", 11, "bold"),
        )
        style.configure("TNotebook", background=FANUC_BG, padding=2)
        style.configure("TNotebook.Tab", padding=[12, 4], font=("Arial", 10, "bold"))
        style.configure("TFrame", background=FANUC_BG)
        style.configure("TScale", background=FANUC_BG, troughcolor=FANUC_PANEL)

    # ---- Menu ----

    def _create_menu(self):
        menubar = tk.Menu(self, bg=FANUC_PANEL, fg=FANUC_TEXT)
        self.config(menu=menubar)

        # File
        file_menu = tk.Menu(menubar, tearoff=0, bg=FANUC_PANEL, fg=FANUC_TEXT)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Config", command=self._save_config, accelerator="Ctrl+S")
        file_menu.add_command(label="Load Config", command=self._load_config)
        file_menu.add_separator()
        file_menu.add_command(label="Export Registers...", command=self._export_registers)
        file_menu.add_command(label="Import Registers...", command=self._import_registers)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)

        # Robot
        robot_menu = tk.Menu(menubar, tearoff=0, bg=FANUC_PANEL, fg=FANUC_TEXT)
        menubar.add_cascade(label="Robot", menu=robot_menu)
        robot_menu.add_command(label="Connect", command=self._toggle_connection)
        robot_menu.add_command(label="Scan Servos", command=self._scan_servos)
        robot_menu.add_separator()
        robot_menu.add_command(label="All Home (0)", command=self._go_all_home)
        robot_menu.add_command(label="All Center (2048)", command=self._go_all_center)
        robot_menu.add_separator()
        robot_menu.add_command(label="E-STOP", command=self._emergency_stop, accelerator="Escape")

        # Program
        prog_menu = tk.Menu(menubar, tearoff=0, bg=FANUC_PANEL, fg=FANUC_TEXT)
        menubar.add_cascade(label="Program", menu=prog_menu)
        prog_menu.add_command(label="Run", command=self._run_program, accelerator="F5")
        prog_menu.add_command(label="Stop", command=self._stop_program)
        prog_menu.add_separator()
        prog_menu.add_command(label="Save Program", command=self._save_program)
        prog_menu.add_command(label="Load Program", command=self._load_program)
        prog_menu.add_command(label="Clear Program", command=self._clear_program)

        # View
        view_menu = tk.Menu(menubar, tearoff=0, bg=FANUC_PANEL, fg=FANUC_TEXT)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(
            label="Jog Mode: Joint", command=lambda: self._set_jog_mode(JOG_MODE_JOINT)
        )
        view_menu.add_command(
            label="Jog Mode: Cartesian",
            command=lambda: self._set_jog_mode(JOG_MODE_CARTESIAN),
        )

        # Help
        help_menu = tk.Menu(menubar, tearoff=0, bg=FANUC_PANEL, fg=FANUC_TEXT)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self._show_shortcuts)
        help_menu.add_command(label="About", command=self._show_about)

    # ---- Widgets ----

    def _create_widgets(self):
        """Создание виджетов окна."""

        # === FANUC Status Bar (top) ===
        self.fanuc_status_bar = FANUCStatusBar(self)
        self.fanuc_status_bar.pack(fill="x")

        # === Нижняя область (пакуется ПЕРВОЙ — фиксируется внизу) ===
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(side="bottom", fill="x", padx=4, pady=(0, 4))

        # Мониторинг
        self.bottom_monitor = BottomMonitorPanel(bottom_frame, self.controller)
        self.bottom_monitor.pack(fill="x", pady=(0, 2))

        # Лог
        self.log_frame = ttk.LabelFrame(bottom_frame, text="LOG")
        self.log_frame.pack(fill="x")
        self._create_log_panel()

        # === Основная область ===
        content_frame = ttk.Frame(self)
        content_frame.pack(fill="both", expand=True)

        # Левая панель — быстрый доступ
        self.sidebar = self._create_sidebar(content_frame)
        self.sidebar.pack(side="left", fill="y", padx=(4, 0), pady=4)

        # Правая часть — вкладки
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill="both", expand=True)

        # Вкладка: Dashboard
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Dashboard")
        self._create_dashboard_tab()

        # Вкладка: Manual Jog
        self.manual_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.manual_tab, text="Jog")
        self.manual_panel = ManualControlPanel(
            self.manual_tab, self.controller, self._log, self._on_manual_update
        )
        self.manual_panel.pack(fill="both", expand=True)

        # Вкладка: 3D Kinematics
        self.kinematics_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.kinematics_tab, text="3D View")
        self.kinematics_panel = Kinematics3DPanel(self.kinematics_tab, self.controller, self._log)
        self.kinematics_panel.pack(fill="both", expand=True)

        # Вкладка: Position Registers
        self.pr_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.pr_tab, text="Registers")
        self.position_register_panel = PositionRegisterPanel(
            self.pr_tab, self.controller, self.kinematics, self._log
        )
        self.position_register_panel.pack(fill="both", expand=True)

        # Вкладка: Teach Pendant
        self.teach_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.teach_tab, text="Teach")
        self.teach_panel = TeachPendantPanel(
            self.teach_tab, self.controller, self.kinematics, self._log
        )
        self.teach_panel.pack(fill="both", expand=True)

        # Вкладка: Block Programming
        self.block_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.block_tab, text="Program")
        self._create_block_tab()

        # Вкладка: Motor Mapping
        self.mapping_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.mapping_tab, text="Setup")
        self.motor_mapping_panel = MotorMappingPanel(self.mapping_tab, self.controller, self._log)
        self.motor_mapping_panel.pack(fill="both", expand=True)

        # Вкладка: Coordinates
        self.coord_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.coord_tab, text="XYZ")
        self._create_coordinates_tab()

        # Вкладка: Alarms
        self.alarm_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.alarm_tab, text="Alarms")
        self.alarm_panel = AlarmHistoryPanel(self.alarm_tab)
        self.alarm_panel.pack(fill="both", expand=True)

        # Вкладка: AI Vision Tracker
        self.vision_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.vision_tab, text="AI Vision")
        self.vision_panel = VisionTrackerPanel(
            self.vision_tab,
            robot_service=self.controller,
            kinematics_service=self.kinematics,
            log_callback=self._log,
        )
        self.vision_panel.pack(fill="both", expand=True)

        # Вкладка: AI Robot Control
        self.ai_control_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.ai_control_tab, text="🤖 AI Control")
        self.ai_control_panel = AIControlPanel(
            self.ai_control_tab,
            robot_service=self.controller,
            kinematics_service=self.kinematics,
            log_callback=self._log,
        )
        self.ai_control_panel.pack(fill="both", expand=True)

        self._refresh_ports()

    def _create_sidebar(self, parent) -> tk.Frame:
        """Боковая панель быстрого доступа."""
        sidebar = tk.Frame(parent, bg=FANUC_BG, width=60)
        sidebar.pack_propagate(False)

        buttons = [
            ("CON", FANUC_BLUE, self._toggle_connection, "Connect/Disconnect"),
            ("SCN", FANUC_ORANGE, self._scan_servos, "Scan servos"),
            ("HOM", FANUC_GREEN, self._go_all_home, "All home (0)"),
            ("CTR", "#7B68EE", self._go_all_center, "All center (2048)"),
            ("TRQ", "#00aa00", self._torque_all_on, "Torque ON"),
            ("FRE", FANUC_ORANGE, self._torque_all_off, "Torque OFF"),
        ]

        for text, bg, cmd, tooltip in buttons:
            btn = tk.Button(
                sidebar,
                text=text,
                font=("Consolas", 8, "bold"),
                bg=bg,
                fg=FANUC_TEXT,
                bd=0,
                width=5,
                height=2,
                activebackground=FANUC_BG,
                activeforeground=FANUC_TEXT,
                command=cmd,
            )
            btn.pack(pady=3, padx=4)
            self._add_tooltip(btn, tooltip)

        # Разделитель
        tk.Frame(sidebar, height=2, bg=FANUC_GRAY).pack(fill="x", pady=8, padx=4)

        # E-STOP
        estop = tk.Button(
            sidebar,
            text="STOP",
            font=("Consolas", 8, "bold"),
            bg="#cc0000",
            fg=FANUC_TEXT,
            bd=0,
            width=5,
            height=2,
            activebackground="#ff0000",
            command=self._emergency_stop,
        )
        estop.pack(pady=3, padx=4)
        self._add_tooltip(estop, "EMERGENCY STOP (Esc)")

        # Speed override slider (vertical)
        tk.Frame(sidebar, height=2, bg=FANUC_GRAY).pack(fill="x", pady=8, padx=4)

        tk.Label(
            sidebar,
            text="SPD",
            font=("Consolas", 7, "bold"),
            bg=FANUC_BG,
            fg=FANUC_ORANGE,
        ).pack()

        self.speed_override_var = tk.IntVar(value=SPEED_OVERRIDE_DEFAULT)
        speed_scale = tk.Scale(
            sidebar,
            from_=SPEED_OVERRIDE_MAX,
            to=SPEED_OVERRIDE_MIN,
            variable=self.speed_override_var,
            orient="vertical",
            bg=FANUC_BG,
            fg=FANUC_ORANGE,
            troughcolor=FANUC_PANEL,
            highlightthickness=0,
            bd=0,
            width=12,
            length=120,
            font=("Consolas", 7),
            command=self._on_speed_override_change,
        )
        speed_scale.pack(padx=4, pady=2)

        self.speed_pct_sidebar = tk.Label(
            sidebar,
            text="50%",
            font=("Consolas", 8, "bold"),
            bg=FANUC_BG,
            fg=FANUC_ORANGE,
        )
        self.speed_pct_sidebar.pack()

        return sidebar

    @staticmethod
    def _add_tooltip(widget, text):
        """Простой tooltip."""
        tip = None

        def show(event):
            nonlocal tip
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")
            tk.Label(
                tip,
                text=text,
                bg="#ffffe0",
                fg=FANUC_TEXT,
                font=("Arial", 9),
                relief="solid",
                bd=1,
                padx=4,
                pady=2,
            ).pack()

        def hide(event):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    # ---- Dashboard Tab ----

    def _create_dashboard_tab(self):
        main = ttk.Frame(self.main_tab)
        main.pack(fill="both", expand=True, padx=15, pady=15)

        # Верхний блок — статус + подключение
        top_frame = ttk.Frame(main)
        top_frame.pack(fill="x", pady=(0, 10))

        # Индикатор подключения
        status_frame = tk.Frame(top_frame, bg=FANUC_PANEL, bd=1, relief="solid")
        status_frame.pack(fill="x")

        self.connection_indicator = tk.Canvas(
            status_frame, width=24, height=24, bg=FANUC_PANEL, highlightthickness=0
        )
        self.connection_indicator.pack(side="left", padx=10, pady=8)
        self._draw_connection_indicator("disconnected")

        self.status_label = tk.Label(
            status_frame,
            text="DISCONNECTED",
            font=("Consolas", 14, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_ORANGE,
        )
        self.status_label.pack(side="left", padx=10, pady=8)

        # Индикаторы осей
        self.axis_indicators = {}
        axis_frame = tk.Frame(status_frame, bg=FANUC_PANEL)
        axis_frame.pack(side="left", padx=20)
        for i in range(6):
            indicator = tk.Canvas(
                axis_frame, width=28, height=28, bg=FANUC_PANEL, highlightthickness=0
            )
            indicator.pack(side="left", padx=3)
            self._draw_axis_indicator(indicator, i, "inactive")
            self.axis_indicators[i] = indicator

        # Подключение
        conn_frame = ttk.LabelFrame(main, text="CONNECTION")
        conn_frame.pack(fill="x", pady=(0, 10))

        port_frame = tk.Frame(conn_frame, bg=FANUC_PANEL)
        port_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(
            port_frame,
            text="COM Port:",
            font=("Consolas", 11, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_GREEN,
        ).pack(side="left", padx=5)

        self.port_combo = ttk.Combobox(port_frame, width=25, font=("Consolas", 11))
        self.port_combo.pack(side="left", padx=5)

        tk.Button(
            port_frame,
            text="REFRESH",
            font=("Arial", 9, "bold"),
            bg=FANUC_GRAY,
            fg=FANUC_TEXT,
            bd=0,
            padx=10,
            pady=4,
            command=self._refresh_ports,
        ).pack(side="left", padx=5)

        self.connect_btn = tk.Button(
            port_frame,
            text="CONNECT",
            font=("Arial", 11, "bold"),
            bg=FANUC_BLUE,
            fg=FANUC_TEXT,
            bd=0,
            padx=20,
            pady=6,
            command=self._toggle_connection,
        )
        self.connect_btn.pack(side="left", padx=10)

        self.scan_btn = tk.Button(
            port_frame,
            text="SCAN SERVOS",
            font=("Arial", 11, "bold"),
            bg=FANUC_ORANGE,
            fg=FANUC_TEXT,
            bd=0,
            padx=20,
            pady=6,
            state="disabled",
            command=self._scan_servos,
        )
        self.scan_btn.pack(side="left", padx=5)

        # Быстрые действия
        quick_frame = ttk.LabelFrame(main, text="QUICK ACTIONS")
        quick_frame.pack(fill="x", pady=(0, 10))

        quick_inner = tk.Frame(quick_frame, bg=FANUC_PANEL)
        quick_inner.pack(fill="x", padx=10, pady=8)

        actions = [
            ("ALL HOME (0)", self._go_all_home, FANUC_BLUE),
            ("ALL CENTER (2048)", self._go_all_center, FANUC_GREEN),
            ("TORQUE ON", self._torque_all_on, "#00aa00"),
            ("TORQUE OFF", self._torque_all_off, FANUC_ORANGE),
            ("E-STOP", self._emergency_stop, "#cc0000"),
        ]

        for text, cmd, color in actions:
            tk.Button(
                quick_inner,
                text=text,
                font=("Arial", 10, "bold"),
                bg=color,
                fg=FANUC_TEXT,
                bd=0,
                padx=18,
                pady=8,
                command=cmd,
            ).pack(side="left", padx=4)

        # Текущие координаты (компактно)
        coord_frame = ttk.LabelFrame(main, text="TOOL POSITION (mm)")
        coord_frame.pack(fill="x", pady=(0, 10))

        coord_inner = tk.Frame(coord_frame, bg=FANUC_PANEL)
        coord_inner.pack(fill="x", padx=10, pady=8)

        self.dash_coord_labels = {}
        for label, var_name, color in [
            ("X", "tool_x_var", FANUC_RED),
            ("Y", "tool_y_var", FANUC_GREEN),
            ("Z", "tool_z_var", FANUC_BLUE),
            ("Rx", "tool_rx_var", FANUC_ORANGE),
            ("Ry", "tool_ry_var", "#E040FB"),
            ("Rz", "tool_rz_var", "#FFD600"),
        ]:
            tk.Label(
                coord_inner,
                text=f"{label}:",
                font=("Consolas", 12, "bold"),
                bg=FANUC_PANEL,
                fg=color,
            ).pack(side="left", padx=(12, 2))

            lbl = tk.Label(
                coord_inner,
                text="0.00",
                font=("Consolas", 13, "bold"),
                bg=FANUC_BG,
                fg=FANUC_TEXT,
                padx=8,
                pady=4,
                relief="sunken",
            )
            lbl.pack(side="left", padx=(0, 8))
            self.dash_coord_labels[label] = lbl

        # Совместные углы
        joints_frame = ttk.LabelFrame(main, text="JOINT POSITIONS")
        joints_frame.pack(fill="x")

        joints_inner = tk.Frame(joints_frame, bg=FANUC_PANEL)
        joints_inner.pack(fill="x", padx=10, pady=8)

        self.dash_joint_labels = {}
        for i in range(6):
            tk.Label(
                joints_inner,
                text=f"J{i + 1}:",
                font=("Consolas", 11, "bold"),
                bg=FANUC_PANEL,
                fg=FANUC_GREEN,
            ).pack(side="left", padx=(12, 2))

            lbl = tk.Label(
                joints_inner,
                text="0.0",
                font=("Consolas", 12),
                bg=FANUC_BG,
                fg=FANUC_TEXT,
                padx=6,
                pady=3,
                relief="sunken",
                width=8,
            )
            lbl.pack(side="left", padx=(0, 6))
            self.dash_joint_labels[i] = lbl

    # ---- Block Programming Tab ----

    def _create_block_tab(self):
        paned = ttk.PanedWindow(self.block_tab, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        # Canvas (создаем первым, чтобы palette мог его использовать)
        canvas_frame = ttk.Frame(paned)
        paned.add(canvas_frame, weight=3)
        self.program_canvas = ProgramCanvas(canvas_frame)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.program_canvas.yview
        )
        self.program_canvas.configure(yscrollcommand=scrollbar.set)
        self.program_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Palette (с правильной ссылкой на canvas)
        palette_frame = ttk.Frame(paned, width=200)
        paned.add(palette_frame, weight=1)
        self.block_palette = BlockPalette(palette_frame, self.program_canvas)
        self.block_palette.pack(fill="both", expand=True)

        # Кнопки
        btn_frame = ttk.Frame(self.block_tab)
        btn_frame.pack(fill="x", padx=5, pady=5)

        for text, cmd, color in [
            ("RUN", self._run_program, FANUC_GREEN),
            ("STOP", self._stop_program, FANUC_RED),
            ("CLEAR", self._clear_program, FANUC_ORANGE),
            ("SAVE", self._save_program, FANUC_BLUE),
            ("LOAD", self._load_program, FANUC_GRAY),
        ]:
            tk.Button(
                btn_frame,
                text=text,
                font=("Arial", 10, "bold"),
                bg=color,
                fg=FANUC_TEXT,
                bd=0,
                padx=14,
                pady=5,
                command=cmd,
            ).pack(side="left", padx=3)

    # ---- Coordinates Tab ----

    def _create_coordinates_tab(self):
        coord_frame = ttk.Frame(self.coord_tab)
        coord_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Линейные
        linear_frame = ttk.LabelFrame(coord_frame, text="LINEAR COORDINATES (mm)")
        linear_frame.pack(fill="x", padx=10, pady=10)

        self._create_coordinate_row(linear_frame, "X:", self.tool_x_var, FANUC_RED)
        self._create_coordinate_row(linear_frame, "Y:", self.tool_y_var, FANUC_GREEN)
        self._create_coordinate_row(linear_frame, "Z:", self.tool_z_var, FANUC_BLUE)

        # Угловые
        angular_frame = ttk.LabelFrame(coord_frame, text="ORIENTATION (deg)")
        angular_frame.pack(fill="x", padx=10, pady=10)

        self._create_coordinate_row(angular_frame, "Rx:", self.tool_rx_var, FANUC_ORANGE)
        self._create_coordinate_row(angular_frame, "Ry:", self.tool_ry_var, "#E040FB")
        self._create_coordinate_row(angular_frame, "Rz:", self.tool_rz_var, "#FFD600")

        btn_frame = ttk.Frame(coord_frame)
        btn_frame.pack(fill="x", padx=10, pady=10)

        tk.Button(
            btn_frame,
            text="REFRESH",
            font=("Arial", 10, "bold"),
            bg=FANUC_BLUE,
            fg=TEXT_COLOR,
            bd=0,
            padx=14,
            pady=5,
            command=self._update_tool_coordinates,
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="ZERO",
            font=("Arial", 10, "bold"),
            bg=FANUC_ORANGE,
            fg=TEXT_COLOR,
            bd=0,
            padx=14,
            pady=5,
            command=self._reset_tool_coordinates,
        ).pack(side="left", padx=5)

    def _create_coordinate_row(self, parent, label, variable, color):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=5)

        ttk.Label(row, text=label, font=("Consolas", 13, "bold"), foreground=color, width=5).pack(
            side="left", padx=10
        )

        ttk.Label(
            row,
            textvariable=variable,
            font=("Consolas", 16, "bold"),
            foreground=FANUC_TEXT,
            background=FANUC_BG,
            padding=10,
        ).pack(side="left", padx=10, fill="x", expand=True)

    # ---- Log Panel ----

    def _create_log_panel(self):
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame,
            height=3,
            font=("Consolas", 9),
            state="disabled",
            bg="#0a0a14",
            fg=FANUC_TEXT,
            insertbackground="white",
            selectbackground=FANUC_BLUE,
        )
        self.log_text.pack(fill="x", padx=5, pady=3)

        # Настройка цветовых тегов
        self.log_text.tag_configure("info", foreground=FANUC_TEXT)
        self.log_text.tag_configure("warning", foreground=FANUC_ORANGE)
        self.log_text.tag_configure("error", foreground=FANUC_RED)
        self.log_text.tag_configure("success", foreground=FANUC_GREEN)

        btn_row = tk.Frame(self.log_frame, bg=FANUC_BG)
        btn_row.pack(fill="x", padx=5, pady=(0, 3))

        tk.Button(
            btn_row,
            text="CLEAR LOG",
            font=("Arial", 8, "bold"),
            bg=FANUC_GRAY,
            fg=FANUC_TEXT,
            bd=0,
            padx=8,
            pady=2,
            command=self._clear_log,
        ).pack(side="right")

    # ---- Logging ----

    def _log(self, message: str, level: str = "info"):
        if not hasattr(self, "log_text"):
            return

        timestamp = time.strftime("%H:%M:%S")
        tag = level if level in ("info", "warning", "error", "success") else "info"

        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n", tag)
        self.log_text.config(state="disabled")
        self.log_text.see("end")

        # В alarm history для ошибок и предупреждений
        if level in ("error", "warning") and self.alarm_panel:
            alarm_level = "ERROR" if level == "error" else "WARNING"
            self.alarm_panel.add_alarm(alarm_level, message)

        log_method = getattr(self.logger, level, self.logger.info)
        log_method(message)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ---- Connection ----

    def _refresh_ports(self):
        try:
            import serial.tools.list_ports

            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.port_combo["values"] = ports
            if ports:
                self.port_combo.current(0)
        except Exception:
            pass

    def _toggle_connection(self):
        if self.controller.connected:
            self._disconnect()
        else:
            port = self.port_combo.get()
            if not port:
                messagebox.showwarning("Warning", "Select a COM port!")
                return
            self._connect(port)

    def _connect(self, port: str):
        self.controller.device = port
        if self.controller.connect():
            self._log(f"Connected to {port}", "success")
            self.status_label.config(text="CONNECTED", fg=FANUC_GREEN)
            self.connect_btn.config(text="DISCONNECT", bg=FANUC_RED)
            self.scan_btn.config(state="normal")
            self._draw_connection_indicator("connected")
            self.fanuc_status_bar.set_connected(True)
        else:
            self._log(f"Failed to connect to {port}", "error")

    def _disconnect(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None

        self.controller.disconnect()
        self._log("Disconnected", "info")
        self.status_label.config(text="DISCONNECTED", fg=FANUC_ORANGE)
        self.connect_btn.config(text="CONNECT", bg=FANUC_BLUE)
        self.scan_btn.config(state="disabled")
        self._draw_connection_indicator("disconnected")
        self.fanuc_status_bar.set_connected(False)

        for j in range(6):
            if j in self.axis_indicators:
                self._draw_axis_indicator(self.axis_indicators[j], j, "inactive")

    def _draw_connection_indicator(self, state: str):
        self.connection_indicator.delete("all")
        color = FANUC_GREEN if state == "connected" else FANUC_GRAY
        self.connection_indicator.create_oval(3, 3, 21, 21, fill=color, outline="white", width=1)

    def _draw_axis_indicator(self, canvas, axis, state):
        canvas.delete("all")
        colors = {
            "active": FANUC_GREEN,
            "inactive": FANUC_GRAY,
            "warning": FANUC_ORANGE,
        }
        color = colors.get(state, FANUC_GRAY)
        canvas.create_oval(3, 3, 25, 25, fill=color, outline="white", width=1)
        canvas.create_text(14, 14, text=f"J{axis + 1}", fill="white", font=("Consolas", 7, "bold"))

    def _update_axis_indicators(self, motor_data_dict):
        for j in range(6):
            motor_id = self.controller.get_motor_id_for_joint(j)
            state = "inactive"
            if motor_id in motor_data_dict:
                data = motor_data_dict[motor_id]
                if data.position is not None:
                    state = "active"
                    if data.is_overheating() or (data.load and data.load > 80):
                        state = "warning"
            if j in self.axis_indicators:
                self._draw_axis_indicator(self.axis_indicators[j], j, state)

    # ---- Scanning & Monitoring ----

    def _scan_servos(self):
        self._log("Scanning servos...", "info")
        threading.Thread(target=self._scan_servos_thread, daemon=True).start()

    def _scan_servos_thread(self):
        servos = self.controller.scan_servos()
        self.after(0, lambda: self._on_scan_complete(servos))

    def _on_scan_complete(self, servos):
        if servos:
            self._log(f"Found servos: {servos}", "success")
            self._start_monitoring(servos)
        else:
            self._log("No servos found", "warning")

    def _start_monitoring(self, motor_ids):
        self.monitor = MotorMonitor(self.controller, None)
        self.monitor.start(motor_ids)
        self._schedule_monitor_update()

    def _schedule_monitor_update(self):
        if self.monitor and self.monitor.running:
            try:
                data_copy = self.monitor.get_all_data()
                self._on_monitor_update(data_copy)
            except Exception as e:
                self._log(f"Monitor error: {e}", "warning")
            self.after(int(MONITOR_INTERVAL * 1000), self._schedule_monitor_update)

    def _on_monitor_update(self, motor_data_dict):
        if self._monitor_update_pending:
            return
        self._monitor_update_pending = True

        try:
            if self.bottom_monitor:
                self.bottom_monitor.update_data(motor_data_dict)

            self._update_axis_indicators(motor_data_dict)

            if self.manual_panel:
                self.manual_panel.update_from_monitor(motor_data_dict)

            if self.motor_mapping_panel:
                self.motor_mapping_panel.update_positions(motor_data_dict)

            if self.kinematics_panel:
                self.kinematics_panel.update_from_monitor(motor_data_dict)

            self._update_tool_coordinates()
            self._update_dashboard_joints()

        except Exception as e:
            self._log(f"GUI update error: {e}", "warning")
        finally:
            self._monitor_update_pending = False

    def _on_manual_update(self):
        pass

    # ---- Speed Override ----

    def _on_speed_override_change(self, value):
        pct = int(float(value))
        self.speed_override = pct
        speed = int(DEFAULT_SPEED * pct / 100)
        self.controller.set_manual_speed(speed)
        self.speed_pct_sidebar.config(text=f"{pct}%")
        self.fanuc_status_bar.set_speed_pct(pct)

    def _set_jog_mode(self, mode: str):
        self.jog_mode = mode
        self.fanuc_status_bar.set_mode(mode.upper())
        self._log(f"Jog mode: {mode}", "info")

    # ---- Quick Actions ----

    def _emergency_stop(self):
        # Без подтверждения — аварийная остановка должна быть мгновенной
        if self.controller.connected:
            self.controller.emergency_stop_all()
        self._log("EMERGENCY STOP ACTIVATED", "error")
        self.fanuc_status_bar.set_prog_status("ABORT")

    def _go_all_home(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return
        if messagebox.askyesno("Confirm", "Move all joints to 0?"):
            threading.Thread(target=self._execute_all_home, daemon=True).start()

    def _execute_all_home(self):
        for j in range(6):
            motor_id = self.controller.get_motor_id_for_joint(j)
            self.controller.move_to_position(motor_id, 0)
        self._log("All joints moved to 0", "info")

    def _go_all_center(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return
        if messagebox.askyesno("Confirm", "Move all joints to center (2048)?"):
            threading.Thread(target=self._execute_all_center, daemon=True).start()

    def _execute_all_center(self):
        for j in range(6):
            motor_id = self.controller.get_motor_id_for_joint(j)
            self.controller.move_to_position(motor_id, 2048)
        self._log("All joints moved to center", "info")

    def _torque_all_on(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return
        for j in range(6):
            motor_id = self.controller.get_motor_id_for_joint(j)
            self.controller.toggle_torque(motor_id, True)
        self._log("All torque ON", "success")

    def _torque_all_off(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return
        for j in range(6):
            motor_id = self.controller.get_motor_id_for_joint(j)
            self.controller.toggle_torque(motor_id, False)
        self._log("All torque OFF", "warning")

    # ---- Program Execution ----

    def _run_program(self):
        program = self.program_canvas.get_program() if self.program_canvas else []
        if not program:
            messagebox.showwarning("Warning", "Program is empty!")
            return

        self._log(f"Running program ({len(program)} blocks)", "success")
        self.fanuc_status_bar.set_prog_status("RUN")
        threading.Thread(target=self._execute_program, args=(program,), daemon=True).start()

    def _execute_program(self, program):
        for block in program:
            params = block.get("params", {})
            block_type = params.get("type", "")

            if block_type == "move_to":
                joint = params.get("joint", 0)
                position = params.get("position", 2048)
                self.controller.move_joint(joint, position)
            elif block_type == "home":
                for i in range(6):
                    self.controller.move_joint(i, 0)
            elif block_type == "wait_time":
                time.sleep(params.get("seconds", 1.0))
            elif block_type == "torque_on":
                motor_id = self.controller.get_motor_id_for_joint(params.get("joint", 0))
                self.controller.toggle_torque(motor_id, True)
            elif block_type == "torque_off":
                motor_id = self.controller.get_motor_id_for_joint(params.get("joint", 0))
                self.controller.toggle_torque(motor_id, False)

        self.cycle_count += 1
        self.after(0, lambda: self.fanuc_status_bar.set_cycle(self.cycle_count))
        self.after(0, lambda: self.fanuc_status_bar.set_prog_status("DONE"))
        self._log("Program completed", "success")

    def _stop_program(self):
        if self.program_executor:
            self.program_executor.stop()
        self.fanuc_status_bar.set_prog_status("ABORT")
        self._log("Program stopped", "warning")

    def _clear_program(self):
        if self.program_canvas:
            self.program_canvas.clear_all()
        self._log("Program cleared", "info")

    # ---- Config & File ----

    def _save_config(self):
        if self.controller.save_config():
            self._log("Config saved", "success")

    def _load_config(self):
        if self.controller.load_config():
            self._log("Config loaded", "success")
            if self.motor_mapping_panel:
                self.motor_mapping_panel._load_current_mapping()

    def _save_program(self):
        if self.program_canvas:
            program = self.program_canvas.get_program()
            with open("robot_program.json", "w") as f:
                json.dump(program, f, indent=2)
            self._log("Program saved", "success")

    def _load_program(self):
        try:
            with open("robot_program.json") as f:
                program = json.load(f)
            self._log(f"Program loaded ({len(program)} blocks)", "success")
        except FileNotFoundError:
            messagebox.showwarning("Warning", "Program file not found!")

    def _export_registers(self):
        if self.position_register_panel:
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                title="Export Position Registers",
            )
            if path:
                self.position_register_panel.save_registers(path)
                self._log(f"Registers exported: {path}", "success")

    def _import_registers(self):
        if self.position_register_panel:
            path = filedialog.askopenfilename(
                filetypes=[("JSON", "*.json")], title="Import Position Registers"
            )
            if path:
                try:
                    self.position_register_panel.load_registers(path)
                    self._log(f"Registers imported: {path}", "success")
                except Exception as e:
                    self._log(f"Import error: {e}", "error")

    # ---- Coordinates ----

    def _update_tool_coordinates(self):
        if self.kinematics_panel:
            angles = self.kinematics_panel.joint_angles
            end_pos = self.kinematics_panel.kinematics.get_end_effector_position(angles)

            x_str = f"{end_pos[0]:.2f}"
            y_str = f"{end_pos[1]:.2f}"
            z_str = f"{end_pos[2]:.2f}"

            self.tool_x_var.set(x_str)
            self.tool_y_var.set(y_str)
            self.tool_z_var.set(z_str)
            self.tool_rx_var.set(f"{angles[4]:.2f}")
            self.tool_ry_var.set(f"{angles[3]:.2f}")
            self.tool_rz_var.set(f"{angles[0]:.2f}")

            # Обновление Dashboard
            if hasattr(self, "dash_coord_labels"):
                self.dash_coord_labels.get("X", tk.Label()).config(text=x_str)
                self.dash_coord_labels.get("Y", tk.Label()).config(text=y_str)
                self.dash_coord_labels.get("Z", tk.Label()).config(text=z_str)
                self.dash_coord_labels.get("Rx", tk.Label()).config(text=f"{angles[4]:.2f}")
                self.dash_coord_labels.get("Ry", tk.Label()).config(text=f"{angles[3]:.2f}")
                self.dash_coord_labels.get("Rz", tk.Label()).config(text=f"{angles[0]:.2f}")

    def _update_dashboard_joints(self):
        """Обновление углов суставов на Dashboard."""
        if not hasattr(self, "dash_joint_labels"):
            return
        for j in range(6):
            motor_id = self.controller.get_motor_id_for_joint(j)
            pos = self.controller.joint_positions.get(motor_id, 2048)
            angle = (pos / MAX_POSITION) * 360 - 180
            if j in self.dash_joint_labels:
                self.dash_joint_labels[j].config(text=f"{angle:.1f}")

    def _reset_tool_coordinates(self):
        for var in (
            self.tool_x_var,
            self.tool_y_var,
            self.tool_z_var,
            self.tool_rx_var,
            self.tool_ry_var,
            self.tool_rz_var,
        ):
            var.set("0.00")
        self._log("Coordinates reset", "info")

    # ---- Keyboard Shortcuts ----

    def _bind_keyboard_shortcuts(self):
        self.bind("<Control-s>", lambda e: self._save_config())
        self.bind("<F5>", lambda e: self._run_program())
        self.bind("<Escape>", lambda e: self._emergency_stop())

        for i in range(6):
            self.bind(f"<Control-Key-{i + 1}>", lambda e, idx=i: self._select_joint(idx))

        self.bind("<Left>", lambda e: self._jog_selected(-1))
        self.bind("<Right>", lambda e: self._jog_selected(1))
        self.bind("<Up>", lambda e: self._jog_selected(1))
        self.bind("<Down>", lambda e: self._jog_selected(-1))

        # Speed override shortcuts
        self.bind("<plus>", lambda e: self._adjust_speed(5))
        self.bind("<minus>", lambda e: self._adjust_speed(-5))
        self.bind("<KP_Add>", lambda e: self._adjust_speed(5))
        self.bind("<KP_Subtract>", lambda e: self._adjust_speed(-5))

    def _select_joint(self, joint_idx):
        if self.manual_panel:
            self.manual_panel.select_joint(joint_idx)

    def _jog_selected(self, direction):
        if self.manual_panel and hasattr(self.manual_panel, "jog"):
            self.manual_panel.jog(direction)

    def _adjust_speed(self, delta):
        new_val = max(SPEED_OVERRIDE_MIN, min(SPEED_OVERRIDE_MAX, self.speed_override + delta))
        self.speed_override_var.set(new_val)
        self._on_speed_override_change(new_val)

    # ---- Help ----

    def _show_shortcuts(self):
        messagebox.showinfo(
            "Keyboard Shortcuts",
            "Ctrl+1..6  — Select joint J1..J6\n"
            "Arrow keys — Jog selected joint\n"
            "+/-        — Speed override\n"
            "Ctrl+S     — Save config\n"
            "F5         — Run program\n"
            "Escape     — Emergency stop\n",
        )

    def _show_about(self):
        messagebox.showinfo(
            "About",
            "ST3215 Robot Control Panel v7.0\n"
            "FANUC iPendant Style GUI\n\n"
            "6-DOF Robot Arm Controller\n"
            "ST3215 Servo Motors\n"
            "DH Kinematics + IK Solver\n\n"
            "Author: Alexandr Lyachov",
        )

    def _show_mapping_panel(self):
        self.notebook.select(self.mapping_tab)

    def _show_monitor_panel(self):
        self.notebook.select(0)

    # ---- Closing ----

    def _on_closing(self):
        if messagebox.askyesno("Exit", "Quit application?"):
            if self.monitor:
                self.monitor.stop()
            self.controller.disconnect()
            self.controller.save_config()
            self.logger.close()
            plt.close("all")
            self.destroy()
