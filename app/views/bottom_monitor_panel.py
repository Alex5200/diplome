#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bottom Monitor Panel Module

Нижняя панель мониторинга моторов в стиле FANUC iPendant.
Компактный дизайн с цветовыми индикаторами.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict

from app.controllers.motor_controller import MotorController
from app.models.motor_data import MotorData
from app.config.constants import (
    FANUC_BG, FANUC_PANEL, FANUC_GREEN, FANUC_ORANGE,
    FANUC_RED, FANUC_BLUE, FANUC_TEXT, FANUC_GRAY,
    TEMP_WARNING, TEMP_CRITICAL, MAX_POSITION
)


class BottomMonitorPanel(ttk.Frame):
    """
    Компактная панель мониторинга 6 моторов.

    Для каждого мотора показывает:
        - Статус (цветной индикатор)
        - Позиция (бар + число)
        - Температура (цвет по порогу)
        - Нагрузка (бар)
        - Напряжение

    Пример:
        panel = BottomMonitorPanel(parent, controller)
        panel.pack(fill='x')
        panel.update_data(motor_data_dict)
    """

    def __init__(self, parent: tk.Misc, controller: MotorController):
        super().__init__(parent)
        self.controller = controller
        self.motor_widgets: Dict[int, Dict[str, any]] = {}
        self._create_widgets()

    def _create_widgets(self):
        # Заголовок
        header = tk.Frame(self, bg='#0a0a1a', height=26)
        header.pack(fill='x')
        header.pack_propagate(False)

        tk.Label(
            header, text="MOTOR STATUS",
            font=('Consolas', 10, 'bold'), bg='#0a0a1a', fg=FANUC_GREEN
        ).pack(side='left', padx=10)

        # Легенда
        for label, color in [("OK", FANUC_GREEN), ("WARN", FANUC_ORANGE), ("ERR", FANUC_RED)]:
            tk.Label(
                header, text=f" {label}", font=('Consolas', 8),
                bg='#0a0a1a', fg=color
            ).pack(side='right', padx=4)

        # Основная панель — 6 моторов в ряд
        main = tk.Frame(self, bg=FANUC_BG)
        main.pack(fill='both', expand=True, padx=2, pady=2)

        for i in range(6):
            panel = self._create_motor_panel(main, i)
            panel.pack(side='left', fill='both', expand=True, padx=2)

    def _create_motor_panel(self, parent, joint_idx) -> tk.Frame:
        joint_name = self.controller.get_joint_name(joint_idx)

        frame = tk.Frame(parent, bg=FANUC_PANEL, bd=1, relief='solid')

        # Заголовок с индикатором
        header_frame = tk.Frame(frame, bg=FANUC_PANEL)
        header_frame.pack(fill='x', padx=3, pady=(3, 1))

        # Статус-индикатор (круг)
        status_canvas = tk.Canvas(
            header_frame, width=10, height=10,
            bg=FANUC_PANEL, highlightthickness=0
        )
        status_canvas.pack(side='left', padx=(2, 4))
        status_canvas.create_oval(1, 1, 9, 9, fill=FANUC_GRAY, outline='')

        tk.Label(
            header_frame, text=f"J{joint_idx+1}",
            font=('Consolas', 9, 'bold'), bg=FANUC_PANEL, fg=FANUC_GREEN
        ).pack(side='left')

        tk.Label(
            header_frame, text=f"({joint_name})",
            font=('Arial', 7), bg=FANUC_PANEL, fg=FANUC_GRAY
        ).pack(side='left', padx=3)

        # Данные
        data_frame = tk.Frame(frame, bg=FANUC_PANEL)
        data_frame.pack(fill='both', expand=True, padx=4, pady=2)

        # Позиция
        pos_label = tk.Label(
            data_frame, text="POS: --", font=('Consolas', 8),
            bg=FANUC_PANEL, fg=FANUC_TEXT, anchor='w'
        )
        pos_label.pack(fill='x')

        pos_bar = tk.Canvas(data_frame, height=6, bg='#0a0a1a', highlightthickness=0)
        pos_bar.pack(fill='x', pady=1)

        # Температура
        temp_label = tk.Label(
            data_frame, text="TMP: --", font=('Consolas', 8),
            bg=FANUC_PANEL, fg=FANUC_TEXT, anchor='w'
        )
        temp_label.pack(fill='x')

        # Нагрузка
        load_label = tk.Label(
            data_frame, text="LOAD: --", font=('Consolas', 8),
            bg=FANUC_PANEL, fg=FANUC_TEXT, anchor='w'
        )
        load_label.pack(fill='x')

        load_bar = tk.Canvas(data_frame, height=6, bg='#0a0a1a', highlightthickness=0)
        load_bar.pack(fill='x', pady=1)

        # Напряжение
        volt_label = tk.Label(
            data_frame, text="V: --", font=('Consolas', 7),
            bg=FANUC_PANEL, fg=FANUC_GRAY, anchor='w'
        )
        volt_label.pack(fill='x')

        self.motor_widgets[joint_idx] = {
            'frame': frame,
            'status_canvas': status_canvas,
            'pos_label': pos_label,
            'pos_bar': pos_bar,
            'temp_label': temp_label,
            'load_label': load_label,
            'load_bar': load_bar,
            'volt_label': volt_label,
        }

        return frame

    def _draw_bar(self, canvas: tk.Canvas, value: float, max_val: float, color: str):
        canvas.delete('all')
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w > 1 and max_val > 0:
            fill_w = int((value / max_val) * w)
            canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline='')

    def update_data(self, motor_data_dict: Dict[int, MotorData]):
        for joint_idx in range(6):
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
                elif (data.temperature and data.temperature >= TEMP_WARNING) or \
                     (data.load and data.load > 70):
                    status_color = FANUC_ORANGE

            w['status_canvas'].delete('all')
            w['status_canvas'].create_oval(1, 1, 9, 9, fill=status_color, outline='')

            # Позиция
            pos = data.position if data.position is not None else 0
            angle = (pos / MAX_POSITION) * 360 - 180
            w['pos_label'].config(text=f"POS: {pos} ({angle:.0f})")
            self._draw_bar(w['pos_bar'], pos, MAX_POSITION, FANUC_BLUE)

            # Температура
            temp = data.temperature if data.temperature is not None else 0
            temp_color = FANUC_GREEN
            if temp >= TEMP_CRITICAL:
                temp_color = FANUC_RED
            elif temp >= TEMP_WARNING:
                temp_color = FANUC_ORANGE
            w['temp_label'].config(text=f"TMP: {temp}C", fg=temp_color)

            # Нагрузка
            load = data.load if data.load is not None else 0
            load_color = FANUC_GREEN if load < 70 else FANUC_ORANGE if load < 90 else FANUC_RED
            w['load_label'].config(text=f"LOAD: {load}%", fg=load_color)
            self._draw_bar(w['load_bar'], load, 100, load_color)

            # Напряжение
            volt = data.voltage if data.voltage is not None else 0
            w['volt_label'].config(text=f"V: {volt:.1f}V" if volt else "V: --")

    def clear_data(self):
        for joint_idx in range(6):
            if joint_idx in self.motor_widgets:
                w = self.motor_widgets[joint_idx]
                w['pos_label'].config(text="POS: --")
                w['temp_label'].config(text="TMP: --", fg=FANUC_TEXT)
                w['load_label'].config(text="LOAD: --", fg=FANUC_TEXT)
                w['volt_label'].config(text="V: --")
                w['pos_bar'].delete('all')
                w['load_bar'].delete('all')
                w['status_canvas'].delete('all')
                w['status_canvas'].create_oval(1, 1, 9, 9, fill=FANUC_GRAY, outline='')
