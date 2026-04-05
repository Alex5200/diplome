#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Manual Control Panel Module — FANUC Jog Style

Панель ручного управления суставами робота
с удобным интерфейсом в стиле FANUC Teach Pendant.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, Dict

from app.controllers.motor_controller import MotorController
from app.config.constants import (
    MIN_POSITION, MAX_POSITION, DEFAULT_SPEED,
    FANUC_GREEN, FANUC_ORANGE, FANUC_RED, FANUC_BLUE,
    FANUC_BG, FANUC_PANEL, FANUC_TEXT, FANUC_GRAY
)


class ManualControlPanel(ttk.Frame):
    """
    Панель ручного управления (Jog) в стиле FANUC iPendant.

    Функции:
        - Выбор сустава (J1-J6) с визуальным выделением
        - Jogging кнопки с настраиваемым шагом
        - Точное позиционирование через ввод
        - Регулировка скорости
        - Быстрые команды (home/center/torque)
        - Отображение всех позиций одновременно
    """

    def __init__(self, parent, controller: MotorController,
                 log_callback: Callable, update_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.configure(style='TFrame')
        self.controller = controller
        self.log = log_callback
        self.update_callback = update_callback

        self.selected_joint = 0
        self.jog_step = 100

        # Переменные
        self.joint_var = tk.IntVar(value=0)
        self.speed_var = tk.IntVar(value=DEFAULT_SPEED)
        self.pos_var = tk.IntVar(value=0)
        self.step_var = tk.IntVar(value=100)

        # Виджеты
        self.joint_buttons: Dict[int, tk.Button] = {}
        self.joint_pos_labels: Dict[int, tk.Label] = {}
        self.joint_angle_labels: Dict[int, tk.Label] = {}
        self.speed_label: Optional[ttk.Label] = None
        self.status_label: Optional[tk.Label] = None

        self._create_widgets()
        self._update_all_positions()

    def _create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill='both', expand=True, padx=10, pady=10)

        # === Левая колонка: выбор сустава + позиции ===
        left = ttk.Frame(main)
        left.pack(side='left', fill='both', expand=True, padx=(0, 5))

        # Выбор сустава
        joint_frame = ttk.LabelFrame(left, text="SELECT JOINT")
        joint_frame.pack(fill='x', pady=(0, 5))

        for i in range(6):
            row = tk.Frame(joint_frame, bg=FANUC_PANEL)
            row.pack(fill='x', padx=4, pady=2)

            joint_name = self.controller.get_joint_name(i)

            btn = tk.Button(
                row, text=f"J{i+1}", width=4,
                font=('Consolas', 10, 'bold'),
                bg=FANUC_PANEL, fg=FANUC_TEXT,
                activebackground=FANUC_GREEN,
                bd=0, relief='flat',
                command=lambda idx=i: self.select_joint(idx)
            )
            btn.pack(side='left', padx=2)
            self.joint_buttons[i] = btn

            tk.Label(
                row, text=joint_name, font=('Arial', 9),
                bg=FANUC_PANEL, fg=FANUC_GRAY, width=12, anchor='w'
            ).pack(side='left', padx=4)

            # Позиция (число)
            pos_lbl = tk.Label(
                row, text="----", font=('Consolas', 10),
                bg='#0a0a1a', fg=FANUC_TEXT, width=6,
                relief='sunken', padx=4
            )
            pos_lbl.pack(side='left', padx=2)
            self.joint_pos_labels[i] = pos_lbl

            # Угол
            angle_lbl = tk.Label(
                row, text="0.0", font=('Consolas', 9),
                bg=FANUC_PANEL, fg=FANUC_BLUE, width=7
            )
            angle_lbl.pack(side='left', padx=2)
            self.joint_angle_labels[i] = angle_lbl

        self._update_joint_highlight()

        # === Центральная колонка: Jogging ===
        center = ttk.Frame(main)
        center.pack(side='left', fill='both', expand=True, padx=5)

        jog_frame = ttk.LabelFrame(center, text="JOG CONTROL")
        jog_frame.pack(fill='x', pady=(0, 5))

        # Jog кнопки
        jog_btns = tk.Frame(jog_frame, bg=FANUC_PANEL)
        jog_btns.pack(pady=10)

        tk.Button(
            jog_btns, text=" - ", width=6, height=2,
            font=('Arial', 16, 'bold'),
            bg=FANUC_ORANGE, fg='white', bd=0,
            command=lambda: self.jog(-1)
        ).grid(row=0, column=0, padx=8)

        # Центральный индикатор
        self.jog_indicator = tk.Label(
            jog_btns, text="J1", font=('Consolas', 20, 'bold'),
            bg=FANUC_PANEL, fg=FANUC_GREEN, width=5
        )
        self.jog_indicator.grid(row=0, column=1, padx=10)

        tk.Button(
            jog_btns, text=" + ", width=6, height=2,
            font=('Arial', 16, 'bold'),
            bg=FANUC_GREEN, fg='white', bd=0,
            command=lambda: self.jog(1)
        ).grid(row=0, column=2, padx=8)

        # Шаг
        step_frame = tk.Frame(jog_frame, bg=FANUC_PANEL)
        step_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(
            step_frame, text="STEP:", font=('Consolas', 10, 'bold'),
            bg=FANUC_PANEL, fg=FANUC_TEXT
        ).pack(side='left', padx=5)

        steps = [10, 50, 100, 250, 500, 1000]
        self.step_buttons: Dict[int, tk.Button] = {}

        for step in steps:
            btn = tk.Button(
                step_frame, text=str(step), width=5,
                font=('Consolas', 9, 'bold'),
                bg=FANUC_PANEL if step != 100 else FANUC_BLUE,
                fg=FANUC_TEXT if step != 100 else 'white',
                bd=0, command=lambda s=step: self._set_step(s)
            )
            btn.pack(side='left', padx=2)
            self.step_buttons[step] = btn

        # Целевая позиция
        target_frame = ttk.LabelFrame(center, text="GO TO POSITION")
        target_frame.pack(fill='x', pady=5)

        target_inner = tk.Frame(target_frame, bg=FANUC_PANEL)
        target_inner.pack(fill='x', padx=10, pady=8)

        ttk.Spinbox(
            target_inner, from_=0, to=MAX_POSITION,
            textvariable=2040, width=12,
            font=('Consolas', 14)
        ).pack(side='left', padx=5)

        tk.Button(
            target_inner, text="GO", font=('Arial', 11, 'bold'),
            bg=FANUC_BLUE, fg='white', bd=0, padx=20, pady=4,
            command=self._move_to_position
        ).pack(side='left', padx=10)

        # Статус выбранного сустава
        self.status_label = tk.Label(
            center, text="J1 | POS: 0 | 0.0",
            font=('Consolas', 11, 'bold'),
            bg='#0a0a1a', fg=FANUC_GREEN,
            relief='sunken', padx=10, pady=6
        )
        self.status_label.pack(fill='x', pady=5)

        # === Правая колонка: скорость + команды ===
        right = ttk.Frame(main)
        right.pack(side='left', fill='both', padx=(5, 0))

        # Скорость
        speed_frame = ttk.LabelFrame(right, text="SPEED")
        speed_frame.pack(fill='x', pady=(0, 5))

        speed_scale = ttk.Scale(
            speed_frame, from_=100, to=10000,
            variable=self.speed_var, orient='horizontal',
            command=self._on_speed_change
        )
        speed_scale.pack(fill='x', padx=10, pady=8)

        self.speed_label = tk.Label(
            speed_frame, text=f"{DEFAULT_SPEED}", font=('Consolas', 12, 'bold'),
            bg=FANUC_PANEL, fg=FANUC_GREEN
        )
        self.speed_label.pack(pady=(0, 5))

        # Быстрые команды
        cmd_frame = ttk.LabelFrame(right, text="QUICK COMMANDS")
        cmd_frame.pack(fill='x', pady=5)

        commands = [
            ("HOME (0)", self._go_home, FANUC_BLUE),
            ("CENTER", self._go_center, FANUC_GREEN),
            ("TRQ ON", self._torque_on, '#00aa00'),
            ("TRQ OFF", self._torque_off, FANUC_ORANGE),
        ]

        for text, cmd, color in commands:
            tk.Button(
                cmd_frame, text=text, font=('Arial', 9, 'bold'),
                bg=color, fg='white', bd=0, padx=8, pady=5,
                command=cmd
            ).pack(fill='x', padx=8, pady=2)

    def select_joint(self, joint_idx: int):
        self.selected_joint = joint_idx
        self.joint_var.set(joint_idx)
        self.jog_indicator.config(text=f"J{joint_idx + 1}")
        self._update_joint_highlight()
        self._update_status_display()
        joint_name = self.controller.get_joint_name(joint_idx)
        self.log(f"Selected: J{joint_idx+1} ({joint_name})", 'info')

    def _update_joint_highlight(self):
        for i, btn in self.joint_buttons.items():
            if i == self.selected_joint:
                btn.config(bg=FANUC_GREEN, fg='black')
            else:
                btn.config(bg=FANUC_PANEL, fg=FANUC_TEXT)

    def _set_step(self, step: int):
        self.jog_step = step
        self.step_var.set(step)
        for s, btn in self.step_buttons.items():
            if s == step:
                btn.config(bg=FANUC_BLUE, fg='white')
            else:
                btn.config(bg=FANUC_PANEL, fg=FANUC_TEXT)

    def _on_speed_change(self, value):
        speed = int(float(value))
        self.speed_label.config(text=f"{speed}")
        self.controller.set_manual_speed(speed)

    def jog(self, direction: int):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        current = self.controller.joint_positions.get(motor_id, 2048)
        new_pos = max(0, min(MAX_POSITION, current + direction * self.jog_step))

        self.controller.move_to_position(motor_id, new_pos)
        self.controller.joint_positions[motor_id] = new_pos
        self.pos_var.set(new_pos)
        self._update_status_display()
        self._update_all_positions()

    def _move_to_position(self):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        position = self.pos_var.get()
        self.controller.move_to_position(motor_id, position)
        self.controller.joint_positions[motor_id] = position
        self._update_status_display()
        self._update_all_positions()
        self.log(f"J{self.selected_joint+1} -> {position}", 'info')

    def _go_home(self):
        self.pos_var.set(0)
        self._move_to_position()

    def _go_center(self):
        self.pos_var.set(2048)
        self._move_to_position()

    def _torque_on(self):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        self.controller.toggle_torque(motor_id, True)
        self.log(f"Torque ON: J{self.selected_joint+1}", 'success')

    def _torque_off(self):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        self.controller.toggle_torque(motor_id, False)
        self.log(f"Torque OFF: J{self.selected_joint+1}", 'warning')

    def _update_status_display(self):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        pos = self.controller.joint_positions.get(motor_id, 2048)
        angle = (pos / MAX_POSITION) * 360 - 180
        self.pos_var.set(int(pos))

        if self.status_label:
            name = self.controller.get_joint_name(self.selected_joint)
            self.status_label.config(
                text=f"J{self.selected_joint+1} ({name}) | POS: {int(pos)} | {angle:.1f}"
            )

    def _update_all_positions(self):
        """Обновление отображения всех позиций."""
        for i in range(6):
            motor_id = self.controller.get_motor_id_for_joint(i)
            pos = self.controller.joint_positions.get(motor_id, 2048)
            angle = (pos / MAX_POSITION) * 360 - 180

            if i in self.joint_pos_labels:
                self.joint_pos_labels[i].config(text=f"{int(pos)}")
            if i in self.joint_angle_labels:
                self.joint_angle_labels[i].config(text=f"{angle:.1f}")

    def update_from_monitor(self, motor_data_dict: Dict[int, any]):
        for joint_idx in range(6):
            motor_id = self.controller.get_motor_id_for_joint(joint_idx)
            if motor_id in motor_data_dict:
                data = motor_data_dict[motor_id]
                if data.position is not None:
                    self.controller.joint_positions[motor_id] = data.position

        self._update_all_positions()
        self._update_status_display()
