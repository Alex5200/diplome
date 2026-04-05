#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kinematics 3D Visualization Panel Module

Панель 3D визуализации кинематики робота-манипулятора.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, List
import math

# matplotlib для 3D визуализации
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from app.controllers.motor_controller import MotorController
from app.models.kinematics import RobotKinematics6DOF
from app.config.constants import (
    MAX_POSITION, FANUC_GREEN, FANUC_BG, FANUC_PANEL, KINEMA_COLORS,
    FANUC_TEXT, FANUC_ORANGE, FANUC_BLUE
)


class Kinematics3DPanel(ttk.Frame):
    """
    Панель 3D визуализации кинематики робота.

    Предоставляет:
        - 3D отображение положения робота
        - Ручную установку углов суставов
        - Применение углов к реальному роботу
        - Автоматическое обновление от монитора

    Пример использования:
        panel = Kinematics3DPanel(parent, controller, log_callback)
        panel.pack(fill='both', expand=True)
    """

    def __init__(
        self,
        parent: tk.Misc,
        controller: MotorController,
        log_callback: Callable[[str, str], None]
    ):
        """
        Инициализация панели 3D визуализации.

        Args:
            parent: Родительский виджет
            controller: Контроллер моторов
            log_callback: Функция для логирования событий
        """
        super().__init__(parent)
        self.controller = controller
        self.log = log_callback

        # Углы суставов в градусах
        self.joint_angles: List[float] = [0.0] * 6

        # Кинематическая модель
        self.kinematics = RobotKinematics6DOF()

        # matplotlib компоненты
        self.figure: Optional[plt.Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.ax: Optional[Axes3D] = None

        # Переменные для ввода углов
        self.angle_vars: List[tk.DoubleVar] = []
        self.angle_labels: List[ttk.Label] = []

        self._create_widgets()
        self._update_joint_names()
        self._draw_robot()

    def _create_widgets(self) -> None:
        """Создание виджетов панели в стиле FANUC."""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # === Левая и правая панели ===
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side='left', fill='both', expand=True, padx=5)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side='right', fill='y', padx=5)

        # === 3D Визуализация (LEFT) ===
        viz_frame = ttk.LabelFrame(left_frame, text="🔬 3D ВИЗУАЛИЗАЦИЯ")
        viz_frame.pack(fill='both', expand=True, padx=0, pady=5)

        self.figure = plt.Figure(figsize=(8, 6), dpi=100, facecolor=FANUC_BG)
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax.set_facecolor(FANUC_PANEL)

        self.canvas = FigureCanvasTkAgg(self.figure, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        # Кнопки управления камерой
        cam_frame = tk.Frame(viz_frame, bg=FANUC_PANEL)
        cam_frame.pack(fill='x', padx=5, pady=5)

        tk.Button(
            cam_frame, text="🔄 СБРОС",
            font=('Arial', 9, 'bold'),
            bg=FANUC_BLUE, fg='white',
            bd=0, padx=10, pady=3,
            command=self._reset_camera
        ).pack(side='left', padx=2)

        tk.Label(
            cam_frame, text="| ВРАЩЕНИЕ: ЛКМ | МАСШТАБ: Колесо |",
            font=('Arial', 8),
            bg=FANUC_PANEL, fg=FANUC_GREEN
        ).pack(side='left', padx=10)

        # === Панель управления (RIGHT) ===
        control_frame = ttk.LabelFrame(right_frame, text="📐 УГЛЫ СУСТАВОВ (°)")
        control_frame.pack(fill='y', expand=True, padx=0, pady=5)

        for i in range(6):
            row_frame = tk.Frame(control_frame, bg=FANUC_PANEL)
            row_frame.pack(fill='x', padx=5, pady=3)

            joint_name = self.controller.get_joint_name(i)
            label = tk.Label(
                row_frame, text=f"J{i + 1} {joint_name}:",
                font=('Arial', 9, 'bold'),
                bg=FANUC_PANEL, fg=FANUC_GREEN,
                width=15, anchor='w'
            )
            label.pack(side='left', padx=2)
            self.angle_labels.append(label)

            angle_var = tk.DoubleVar(value=0.0)
            self.angle_vars.append(angle_var)

            entry = ttk.Spinbox(
                row_frame, from_=-180, to=180,
                textvariable=angle_var, width=8,
                font=('Consolas', 10)
            )
            entry.pack(side='left', padx=2)

            tk.Button(
                row_frame, text="OK", width=4,
                font=('Arial', 8, 'bold'),
                bg=FANUC_ORANGE, fg='white',
                bd=0, command=lambda idx=i: self._apply_angle(idx)
            ).pack(side='left', padx=2)

        # === Кнопки действий ===
        btn_frame = tk.Frame(right_frame, bg=FANUC_PANEL)
        btn_frame.pack(fill='x', padx=5, pady=10)

        tk.Button(
            btn_frame, text="🔄 3D",
            font=('Arial', 9, 'bold'),
            bg=FANUC_GREEN, fg='white',
            bd=0, padx=10, pady=5,
            command=self._update_visualization
        ).pack(side='left', padx=2, expand=True, fill='x')

        tk.Button(
            btn_frame, text="🏠 СБРОС",
            font=('Arial', 9, 'bold'),
            bg=FANUC_BLUE, fg='white',
            bd=0, padx=10, pady=5,
            command=self._reset_angles
        ).pack(side='left', padx=2, expand=True, fill='x')

        tk.Button(
            btn_frame, text="📤 ПРИМЕНИТЬ",
            font=('Arial', 9, 'bold'),
            bg=FANUC_ORANGE, fg='white',
            bd=0, padx=10, pady=5,
            command=self._apply_all_angles
        ).pack(side='left', padx=2, expand=True, fill='x')

        # === Информация о позиции ===
        info_frame = ttk.LabelFrame(right_frame, text="📍 ПОЗИЦИЯ ИНСТРУМЕНТА")
        info_frame.pack(fill='x', padx=5, pady=5)

        self.tool_pos_label = tk.Label(
            info_frame, text="X: 0.0\nY: 0.0\nZ: 0.0",
            font=('Consolas', 10),
            bg=FANUC_PANEL, fg=FANUC_TEXT,
            justify='left', padx=10, pady=10
        )
        self.tool_pos_label.pack(fill='x', padx=5, pady=5)

    def _update_joint_names(self) -> None:
        """Обновление имен суставов на интерфейсе."""
        for i in range(6):
            joint_name = self.controller.get_joint_name(i)
            if i < len(self.angle_labels):
                self.angle_labels[i].config(text=f"J{i + 1} ({joint_name}):")

    def _apply_angle(self, idx: int) -> None:
        """
        Применение угла к конкретному суставу.

        Args:
            idx: Индекс сустава (0-5)
        """
        motor_id = self.controller.get_motor_id_for_joint(idx)
        angle = self.angle_vars[idx].get()

        # Конвертация градусов в позицию (0-4095)
        position = int((angle + 180) / 360 * MAX_POSITION)
        position = max(0, min(MAX_POSITION, position))

        self.controller.move_to_position(motor_id, position)
        self.controller.joint_positions[motor_id] = position

        self.log(
            f"🔄 {self.controller.get_joint_name(idx)} → {angle}° (ID={motor_id}, поз={position})",
            'info'
        )

    def _apply_all_angles(self) -> None:
        """Применение всех углов к роботу."""
        if not self.controller.connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь!")
            return

        if messagebox.askyesno("Подтверждение", "Применить все углы?"):
            for i in range(6):
                self._apply_angle(i)
            self.log("🔄 Все углы применены", 'success')

    def _reset_angles(self) -> None:
        """Сброс всех углов к нулю."""
        for i in range(6):
            self.angle_vars[i].set(0.0)
            self.joint_angles[i] = 0.0
        self._update_visualization()
        self.log("🏠 Углы сброшены", 'info')

    def _reset_camera(self) -> None:
        """Сброс позиции камеры к значению по умолчанию."""
        if self.ax:
            self.ax.view_init(elev=30, azim=45)
            self.figure.canvas.draw()
            self.log("📷 Камера сброшена", 'info')

    def _update_visualization(self) -> None:
        """Обновление 3D визуализации на основе введенных углов."""
        for i in range(6):
            try:
                self.joint_angles[i] = self.angle_vars[i].get()
            except Exception:
                self.joint_angles[i] = 0.0

        self._update_joint_names()
        self._draw_robot()

    def _draw_robot(self) -> None:
        """Отрисовка 3D модели робота."""
        if not self.ax or not self.figure or not self.canvas:
            return

        self.ax.clear()
        self.ax.set_facecolor(FANUC_PANEL)

        # Расчет позиций суставов через кинематическую модель
        joint_positions = self.kinematics.get_all_joint_positions(self.joint_angles)

        # Извлечение координат
        x_points = [p[0] for p in joint_positions]
        y_points = [p[1] for p in joint_positions]
        z_points = [p[2] for p in joint_positions]

        # Настройка осей с учетом рабочей зоны
        max_reach = self.kinematics.get_total_reach()
        self.ax.set_xlim(-max_reach, max_reach)
        self.ax.set_ylim(-max_reach, max_reach)
        self.ax.set_zlim(-max_reach/2, max_reach + 50)
        self.ax.set_xlabel('X (мм)')
        self.ax.set_ylabel('Y (мм)')
        self.ax.set_zlabel('Z (мм)')
        self.ax.set_title(f'Робот манипулятор (L={max_reach}мм)', color='white')

        # Стиль осей
        self.ax.xaxis.pane.fill = False
        self.ax.yaxis.pane.fill = False
        self.ax.zaxis.pane.fill = False
        self.ax.xaxis.pane.set_edgecolor('#666666')
        self.ax.yaxis.pane.set_edgecolor('#666666')
        self.ax.zaxis.pane.set_edgecolor('#666666')
        self.ax.tick_params(colors='white')

        # Отрисовка робота
        self.ax.plot(
            x_points, y_points, z_points,
            color=FANUC_GREEN, linewidth=3, marker='o', markersize=8
        )

        # Отрисовка суставов
        for i, (x, y, z) in enumerate(zip(x_points, y_points, z_points)):
            self.ax.scatter(
                [x], [y], [z],
                color=KINEMA_COLORS[i % len(KINEMA_COLORS)], s=100
            )
            joint_name = self.controller.get_joint_name(i) if i > 0 else 'База'
            self.ax.text(x, y, z + 10, f'J{i} {joint_name}', color='white', fontsize=9)

        # Отображение позиции инструмента
        end_pos = self.kinematics.get_end_effector_position(self.joint_angles)
        self.ax.scatter(
            [end_pos[0]], [end_pos[1]], [end_pos[2]],
            color='red', s=150, marker='x'
        )
        self.ax.text(
            end_pos[0], end_pos[1], end_pos[2] + 10,
            f'Инструмент\n({end_pos[0]:.0f}, {end_pos[1]:.0f}, {end_pos[2]:.0f})',
            color='red', fontsize=9
        )

        # Обновление метки позиции инструмента
        if hasattr(self, 'tool_pos_label'):
            self.tool_pos_label.config(
                text=f"X: {end_pos[0]:.1f} мм\nY: {end_pos[1]:.1f} мм\nZ: {end_pos[2]:.1f} мм"
            )

        self.figure.tight_layout()
        self.canvas.draw()

    def update_from_monitor(self, motor_data_dict: dict) -> None:
        """
        Обновление углов от монитора моторов.

        Args:
            motor_data_dict: Словарь данных моторов {motor_id: MotorData}
        """
        for joint_idx in range(6):
            motor_id = self.controller.get_motor_id_for_joint(joint_idx)
            if motor_id in motor_data_dict:
                data = motor_data_dict[motor_id]
                if data.position is not None:
                    # Конвертация позиции в градусы
                    angle = (data.position / MAX_POSITION) * 360 - 180
                    self.angle_vars[joint_idx].set(angle)
                    self.joint_angles[joint_idx] = angle

        self._draw_robot()
