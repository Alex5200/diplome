#!/usr/bin/env python3

"""
Bottom Monitor Panel Module

Ультракомпактная нижняя панель мониторинга моторов.
Одна строка на мотор: индикатор | имя | pos | temp | load | volt
"""

import tkinter as tk
from tkinter import ttk
from typing import Any

from app.config.constants import (
    FANUC_BG,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    MAX_POSITION,
    NUM_JOINTS,
    TEMP_CRITICAL,
    TEMP_WARNING,
)
from app.controllers.motor_controller import MotorController
from app.models.motor_data import MotorData

MONO = ("SF Mono", 7)
MONO_SM = ("SF Mono", 6)
LABEL_FONT = ("SF Pro", 7, "bold")


class BottomMonitorPanel(ttk.Frame):
    """
    Ультракомпактная панель мониторинга 6 моторов.
    Горизонтальная раскладка: 6 мини-карточек в ряд.

    Пример:
        panel = BottomMonitorPanel(parent, controller)
        panel.pack(fill='x')
        panel.update_data(motor_data_dict)
    """

    def __init__(self, parent: tk.Misc, controller: MotorController):
        super().__init__(parent, style="Dark.TFrame")
        self.controller = controller
        self.motor_widgets: dict[int, dict[str, Any]] = {}
        self._create_widgets()

    def _create_widgets(self):
        # Основная панель — 6 моторов в ряд, без заголовка
        main = tk.Frame(self, bg=FANUC_BG)
        main.pack(fill="x", padx=1, pady=1)

        for i in range(NUM_JOINTS):
            panel = self._create_motor_card(main, i)
            panel.pack(side="left", fill="x", expand=True, padx=1)

    def _lbl(self, parent, text="--", fg=FANUC_TEXT):
        l = tk.Label(parent, text=text, font=MONO_SM, bg=FANUC_PANEL, fg=fg, pady=0)
        l.pack(side="left")
        return l

    def _create_motor_card(self, parent, joint_idx) -> tk.Frame:
        name = self.controller.get_joint_name(joint_idx)
        f = tk.Frame(parent, bg=FANUC_PANEL, bd=1, relief="flat")
        row = tk.Frame(f, bg=FANUC_PANEL)
        row.pack(fill="x", padx=2, pady=1)

        sc = tk.Canvas(row, width=6, height=6, bg=FANUC_PANEL, highlightthickness=0)
        sc.pack(side="left", padx=(0, 2))
        sc.create_oval(0, 0, 6, 6, fill=FANUC_GRAY, outline="")
        tk.Label(
            row,
            text=f"J{joint_idx + 1} {name}",
            font=LABEL_FONT,
            bg=FANUC_PANEL,
            fg=FANUC_GREEN,
            pady=0,
        ).pack(side="left")

        pos = self._lbl(row, "-- (--)")
        self._lbl(row, " ", FANUC_GRAY)
        tmp = self._lbl(row)
        self._lbl(row, "|", FANUC_GRAY)
        ld = self._lbl(row)
        self._lbl(row, "|", FANUC_GRAY)
        vlt = self._lbl(row, fg=FANUC_GRAY)

        self.motor_widgets[joint_idx] = {
            "frame": f,
            "status_canvas": sc,
            "pos_label": pos,
            "temp_label": tmp,
            "load_label": ld,
            "volt_label": vlt,
        }
        return f

    def update_data(self, motor_data_dict: dict[int, MotorData]):
        for joint_idx in range(NUM_JOINTS):
            motor_id = self.controller.get_motor_id_for_joint(joint_idx)

            if motor_id not in motor_data_dict or joint_idx not in self.motor_widgets:
                continue

            data = motor_data_dict[motor_id]
            w = self.motor_widgets[joint_idx]

            # Статус индикатор
            status_color = FANUC_GRAY
            if data.position is not None:
                status_color = FANUC_GREEN
                if data.is_overheating():
                    status_color = FANUC_RED
                elif (data.temperature and data.temperature >= TEMP_WARNING) or (
                    data.load and data.load > 70
                ):
                    status_color = FANUC_ORANGE

            w["status_canvas"].delete("all")
            w["status_canvas"].create_oval(0, 0, 6, 6, fill=status_color, outline="")

            # Позиция + угол
            pos = data.position if data.position is not None else 0
            angle = (pos / MAX_POSITION) * 360 - 180
            w["pos_label"].config(text=f"{pos} ({angle:.0f}\u00b0)")

            # Температура
            temp = data.temperature if data.temperature is not None else 0
            temp_color = FANUC_GREEN
            if temp >= TEMP_CRITICAL:
                temp_color = FANUC_RED
            elif temp >= TEMP_WARNING:
                temp_color = FANUC_ORANGE
            w["temp_label"].config(text=f"{temp}\u00b0C", fg=temp_color)

            # Нагрузка
            load = data.load if data.load is not None else 0
            load_color = FANUC_GREEN if load < 70 else FANUC_ORANGE if load < 90 else FANUC_RED
            w["load_label"].config(text=f"{load}%", fg=load_color)

            # Напряжение
            volt = data.voltage if data.voltage is not None else 0
            w["volt_label"].config(text=f"{volt:.1f}V" if volt > 0 else "--V")

    def clear_data(self):
        for joint_idx in range(NUM_JOINTS):
            if joint_idx in self.motor_widgets:
                w = self.motor_widgets[joint_idx]
                w["pos_label"].config(text="-- (--)")
                w["temp_label"].config(text="--\u00b0C", fg=FANUC_TEXT)
                w["load_label"].config(text="--%", fg=FANUC_TEXT)
                w["volt_label"].config(text="--V")
                w["status_canvas"].delete("all")
                w["status_canvas"].create_oval(0, 0, 6, 6, fill=FANUC_GRAY, outline="")
