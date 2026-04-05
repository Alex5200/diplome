#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Safe Motor Control Visualizer with ST3215 Connection
Безопасная визуализация с подключением к моторам ST3215
с ограниченной скоростью для безопасности.

Поддержка:
- Ручное управление слайдерами (углы суставов)
- Указание целевой точки XYZ → обратная кинематика → движение
- Клик по 3D визуализации для установки целевой точки
- Список точек-маршрутов (waypoints)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import sys
from pathlib import Path
import threading
from typing import Optional, Dict, List, Tuple
import numpy as np

# Добавляем родительскую директорию в path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D, proj3d

from app.models.kinematics import RobotKinematics6DOF, InverseKinematics6DOF
from app.config.constants import (
    MAX_POSITION, MIN_POSITION, KINEMA_COLORS, FANUC_BG, FANUC_PANEL,
    FANUC_GREEN, DEFAULT_SPEED, DEFAULT_ACC, DEFAULT_MOTOR_MAPPING
)

# Прямой импорт стандартной библиотеки ST3215
try:
    from st3215 import ST3215
    ST3215_AVAILABLE = True
except ImportError:
    ST3215_AVAILABLE = False
    print("⚠️ Библиотека st3215 не найдена. Запустите: pip install st3215")


class SafeMotorVisualizer:
    """
    Безопасный визуализатор с прямым подключением к моторам ST3215.

    Использует стандартную библиотеку st3215 напрямую (не через MotorController).

    Возможности:
    - Управление суставами через слайдеры
    - Указание целевой точки XYZ → обратная кинематика → движение
    - Клик по 3D визуализации для быстрого выбора точки
    - Список точек-маршрутов (waypoints) с последовательным обходом

    Меры безопасности:
    - Очень низкая скорость движения (10% от максимальной)
    - Ограничение диапазонов углов для предотвращения столкновений
    - Кнопка экстренной остановки
    - Подтверждение перед движением
    - Визуальная индикация статуса
    """

    JOINT_NAMES = [
        '🏗️ База (J1)',
        '💪 Плечо 1 (J2)',
        '💪 Плечо 2 (J3)',
        '🦾 Локоть (J4)',
        '🖐️ Кисть 1 (J5)',
        '🖐️ Кисть 2 (J6)'
    ]

    # Безопасные диапазоны углов (градусы) для предотвращения столкновений
    # Подход сверху: J2>0 (плечо вверх), J3<0 (предплечье вниз)
    SAFE_ANGLE_LIMITS = [
        (-120, 120),   # База - ограничено для безопасности
        (-30, 90),     # Плечо 1: до 90° вверх, до -30° вниз
        (-120, 30),    # Плечо 2: до -120° вниз (подход сверху), до 30° вверх
        (-90, 90),     # Локоть: компенсация ориентации
        (-90, 90),     # Кисть 1
        (-90, 90),     # Кисть 2
    ]

    # Очень низкая скорость для безопасности (10% от макс)
    SAFE_SPEED = 100  # вместо DEFAULT_SPEED=2400

    def __init__(self):
        """Инициализация визуализатора."""
        self.kinematics = RobotKinematics6DOF()
        self.ik_solver = InverseKinematics6DOF(self.kinematics)
        self.st3215: Optional[ST3215] = None  # Прямой экземпляр ST3215
        self.device = 'COM3'
        self.joint_angles = [0.0] * 6
        self.target_angles = [0.0] * 6
        self.slider_vars = []
        self.position_vars = []
        self.is_connected = False
        self.is_moving = False
        self.found_servos: List[int] = []
        self.torque_states: Dict[int, bool] = {}

        # Целевая точка и маршрутные точки
        self.target_point: Optional[Tuple[float, float, float]] = None
        self.waypoints: List[Tuple[float, float, float]] = []
        self.click_mode = False  # Режим выбора точки кликом

        self._create_window()
        self._create_status_panel()
        self._create_sliders()
        self._create_display()
        self._create_target_panel()
        self._create_buttons()
        self._draw_robot()

    def _create_window(self):
        """Создание главного окна."""
        self.root = tk.Tk()
        self.root.title("🤖 ST3215 Safe Motor Visualizer")
        self.root.geometry("1500x950")
        self.root.configure(bg='#1a1a2e')

        # Главный контейнер
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Обработчик закрытия
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_status_panel(self):
        """Создание панели статуса."""
        status_frame = ttk.LabelFrame(self.main_frame, text="📊 Статус системы")
        status_frame.pack(fill='x', padx=10, pady=5)

        # Статус подключения
        conn_frame = ttk.Frame(status_frame)
        conn_frame.pack(side='left', padx=20)

        self.conn_label = ttk.Label(
            conn_frame,
            text="❌ Отключено",
            font=('Consolas', 12, 'bold'),
            foreground='red'
        )
        self.conn_label.pack()

        # Порт
        port_frame = ttk.Frame(status_frame)
        port_frame.pack(side='left', padx=20)

        ttk.Label(port_frame, text="COM порт:", font=('Consolas', 10)).pack()
        self.port_var = tk.StringVar(value='COM3')
        port_entry = ttk.Entry(port_frame, textvariable=self.port_var, width=10)
        port_entry.pack()

        # Скорость
        speed_frame = ttk.Frame(status_frame)
        speed_frame.pack(side='left', padx=20)

        ttk.Label(speed_frame, text="Скорость:", font=('Consolas', 10)).pack()
        self.speed_var = tk.IntVar(value=self.SAFE_SPEED)
        speed_label = ttk.Label(
            speed_frame,
            textvariable=self.speed_var,
            font=('Consolas', 10, 'bold'),
            foreground='#00ff88'
        )
        speed_label.pack()
        ttk.Label(
            speed_frame,
            text=f"(макс: {DEFAULT_SPEED})",
            font=('Consolas', 8),
            foreground='gray'
        ).pack()

        # Предупреждение
        warning_label = ttk.Label(
            status_frame,
            text="⚠️ БЕЗОПАСНЫЙ РЕЖИМ: Скорость ограничена 10%",
            font=('Consolas', 10, 'bold'),
            foreground='orange'
        )
        warning_label.pack(side='right', padx=20)

    def _create_sliders(self):
        """Создание ползунков для каждого сустава."""
        slider_frame = ttk.LabelFrame(
            self.main_frame,
            text="📐 Углы суставов (градусы) - ST3215 (0-4095) - БЕЗОПАСНЫЕ ДИАПАЗОНЫ",
            padding=5
        )
        slider_frame.pack(fill='x', padx=10, pady=5)

        for i in range(6):
            frame = ttk.Frame(slider_frame)
            frame.pack(fill='x', pady=2)

            # Название сустава
            name_label = ttk.Label(
                frame,
                text=self.JOINT_NAMES[i],
                width=25,
                font=('Consolas', 10)
            )
            name_label.pack(side='left', padx=5)

            # Отображение пределов
            min_angle, max_angle = self.SAFE_ANGLE_LIMITS[i]
            limits_label = ttk.Label(
                frame,
                text=f"[{min_angle}°; {max_angle}°]",
                width=15,
                font=('Consolas', 8),
                foreground='orange'
            )
            limits_label.pack(side='left', padx=5)

            # Переменная для угла
            var = tk.DoubleVar(value=0.0)
            self.slider_vars.append(var)

            # Переменная для позиции
            pos_var = tk.StringVar(value="2048")
            self.position_vars.append(pos_var)

            # Ползунок с ограниченными пределами
            slider = ttk.Scale(
                frame,
                from_=min_angle,
                to=max_angle,
                variable=var,
                orient='horizontal',
                length=350,
                command=lambda v, idx=i: self._on_slider_change(idx)
            )
            slider.pack(side='left', padx=10)

            # Поле ввода угла
            angle_entry = ttk.Spinbox(
                frame,
                from_=min_angle,
                to=max_angle,
                textvariable=var,
                width=8,
                command=lambda idx=i: self._on_entry_change(idx)
            )
            angle_entry.pack(side='left', padx=5)
            angle_entry.bind('<Return>', lambda e, idx=i: self._on_entry_change(idx))

            # Поле позиции мотора
            pos_label = ttk.Label(
                frame,
                textvariable=pos_var,
                width=12,
                font=('Consolas', 9),
                foreground='#00ff88'
            )
            pos_label.pack(side='left', padx=10)

            # Кнопка движения для конкретного сустава
            move_btn = ttk.Button(
                frame,
                text="➡️",
                width=3,
                command=lambda idx=i: self._move_joint(idx)
            )
            move_btn.pack(side='left', padx=5)

    def _create_display(self):
        """Создание 3D визуализации и дисплея координат."""
        display_frame = ttk.Frame(self.main_frame)
        display_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # 3D график
        viz_frame = ttk.LabelFrame(display_frame, text="🔬 3D Визуализация (клик = выбор точки)")
        viz_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        self.figure = plt.Figure(figsize=(8, 6), dpi=100, facecolor=FANUC_BG)
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax.set_facecolor(FANUC_PANEL)

        self.canvas = FigureCanvasTkAgg(self.figure, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        # Подключение событий мыши для клика по 3D
        self.canvas.mpl_connect('button_press_event', self._on_3d_click)

        # Панель информации
        info_frame = ttk.LabelFrame(display_frame, text="📊 Координаты и статус")
        info_frame.pack(side='right', fill='y', padx=5, pady=5)

        # Текстовая информация
        self.info_text = tk.Text(
            info_frame,
            width=35,
            height=20,
            bg='#16213e',
            fg='#ffffff',
            font=('Consolas', 9)
        )
        self.info_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Скроллбар
        scrollbar = ttk.Scrollbar(
            info_frame,
            orient='vertical',
            command=self.info_text.yview
        )
        scrollbar.pack(side='right', fill='y')
        self.info_text.configure(yscrollcommand=scrollbar.set)

    def _create_target_panel(self):
        """Создание панели целевой точки и маршрутных точек."""
        target_outer = ttk.Frame(self.main_frame)
        target_outer.pack(fill='x', padx=10, pady=5)

        # --- Левая часть: ввод целевой точки ---
        target_frame = ttk.LabelFrame(target_outer, text="🎯 Целевая точка (XYZ мм)", padding=5)
        target_frame.pack(side='left', fill='x', expand=True, padx=(0, 5))

        input_row = ttk.Frame(target_frame)
        input_row.pack(fill='x', pady=2)

        # X
        ttk.Label(input_row, text="X:", font=('Consolas', 10, 'bold'),
                   foreground='#FF6B6B').pack(side='left', padx=2)
        self.target_x_var = tk.DoubleVar(value=100.0)
        ttk.Spinbox(input_row, from_=-400, to=400, textvariable=self.target_x_var,
                     width=8, increment=5.0).pack(side='left', padx=2)

        # Y
        ttk.Label(input_row, text="Y:", font=('Consolas', 10, 'bold'),
                   foreground='#4ECDC4').pack(side='left', padx=(10, 2))
        self.target_y_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(input_row, from_=-400, to=400, textvariable=self.target_y_var,
                     width=8, increment=5.0).pack(side='left', padx=2)

        # Z
        ttk.Label(input_row, text="Z:", font=('Consolas', 10, 'bold'),
                   foreground='#45B7D1').pack(side='left', padx=(10, 2))
        self.target_z_var = tk.DoubleVar(value=150.0)
        ttk.Spinbox(input_row, from_=-100, to=400, textvariable=self.target_z_var,
                     width=8, increment=5.0).pack(side='left', padx=2)

        # Кнопки
        btn_row = ttk.Frame(target_frame)
        btn_row.pack(fill='x', pady=2)

        ttk.Button(btn_row, text="🧮 Рассчитать IK",
                    command=self._solve_ik_for_target).pack(side='left', padx=3)
        ttk.Button(btn_row, text="🎯 Двигать к точке",
                    command=self._move_to_target_point).pack(side='left', padx=3)
        ttk.Button(btn_row, text="📌 Показать на 3D",
                    command=self._show_target_on_3d).pack(side='left', padx=3)

        # Режим клика
        self.click_mode_var = tk.BooleanVar(value=False)
        click_cb = ttk.Checkbutton(
            btn_row, text="🖱️ Клик по 3D = выбор точки",
            variable=self.click_mode_var,
            command=self._toggle_click_mode
        )
        click_cb.pack(side='left', padx=10)

        # Статус IK
        self.ik_status_var = tk.StringVar(value="")
        ttk.Label(target_frame, textvariable=self.ik_status_var,
                   font=('Consolas', 9), foreground='#00ff88').pack(fill='x', pady=2)

        # --- Панель проверенных точек ---
        preset_frame = ttk.LabelFrame(target_outer, text="✅ Проверенные точки (IK работает)", padding=5)
        preset_frame.pack(side='left', fill='both', expand=True, padx=(5, 0))

        preset_list_frame = ttk.Frame(preset_frame)
        preset_list_frame.pack(fill='both', expand=True)

        self.preset_listbox = tk.Listbox(
            preset_list_frame, height=4, width=35,
            bg='#16213e', fg='#00ff88', font=('Consolas', 9),
            selectmode=tk.SINGLE
        )
        self.preset_listbox.pack(side='left', fill='both', expand=True)

        preset_scroll = ttk.Scrollbar(preset_list_frame, orient='vertical',
                                       command=self.preset_listbox.yview)
        preset_scroll.pack(side='right', fill='y')
        self.preset_listbox.configure(yscrollcommand=preset_scroll.set)
        self.preset_listbox.bind('<<ListboxSelect>>', self._on_preset_select)

        preset_btn_row = ttk.Frame(preset_frame)
        preset_btn_row.pack(fill='x', pady=2)

        ttk.Button(preset_btn_row, text="➕ Сохранить текущую",
                    command=self._save_preset_point).pack(side='left', padx=2)
        ttk.Button(preset_btn_row, text="➖ Удалить",
                    command=self._remove_preset_point).pack(side='left', padx=2)
        ttk.Button(preset_btn_row, text="🗑️ Очистить",
                    command=self._clear_preset_points).pack(side='left', padx=2)
        ttk.Button(preset_btn_row, text="🎯 Применить",
                    command=self._apply_preset_point).pack(side='left', padx=5)

        # Предустановленные рабочие точки
        self.preset_points = [
            (100, 0, 150, "Центр передняя"),
            (150, 0, 100, "Дальняя низ"),
            (80, 50, 120, "Средняя левая"),
            (80, -50, 120, "Средняя правая"),
            (120, 0, 180, "Верхняя точка"),
        ]
        self._refresh_preset_list()

        # --- Правая часть: список маршрутных точек ---
        wp_frame = ttk.LabelFrame(target_outer, text="📍 Маршрутные точки (Waypoints)", padding=5)
        wp_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))

        # Список точек
        wp_list_frame = ttk.Frame(wp_frame)
        wp_list_frame.pack(fill='both', expand=True)

        self.wp_listbox = tk.Listbox(
            wp_list_frame, height=4, width=40,
            bg='#16213e', fg='#ffffff', font=('Consolas', 9),
            selectmode=tk.SINGLE
        )
        self.wp_listbox.pack(side='left', fill='both', expand=True)

        wp_scroll = ttk.Scrollbar(wp_list_frame, orient='vertical',
                                   command=self.wp_listbox.yview)
        wp_scroll.pack(side='right', fill='y')
        self.wp_listbox.configure(yscrollcommand=wp_scroll.set)
        self.wp_listbox.bind('<Double-1>', self._on_waypoint_double_click)

        # Кнопки маршрутных точек
        wp_btn_row = ttk.Frame(wp_frame)
        wp_btn_row.pack(fill='x', pady=2)

        ttk.Button(wp_btn_row, text="➕ Добавить",
                    command=self._add_waypoint).pack(side='left', padx=2)
        ttk.Button(wp_btn_row, text="➖ Удалить",
                    command=self._remove_waypoint).pack(side='left', padx=2)
        ttk.Button(wp_btn_row, text="🗑️ Очистить",
                    command=self._clear_waypoints).pack(side='left', padx=2)
        ttk.Button(wp_btn_row, text="▶️ Обход всех",
                    command=self._run_waypoints).pack(side='left', padx=5)
        ttk.Button(wp_btn_row, text="🎯 К выбранной",
                    command=self._go_to_selected_waypoint).pack(side='left', padx=2)

    def _create_buttons(self):
        """Создание кнопок управления."""
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill='x', padx=10, pady=5)

        # Кнопки подключения
        ttk.Button(
            btn_frame,
            text="🔌 Подключить",
            command=self._connect
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="🔌 Отключить",
            command=self._disconnect
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="🔍 Сканировать моторы",
            command=self._scan_motors
        ).pack(side='left', padx=5)

        # Разделитель
        ttk.Separator(btn_frame, orient='vertical').pack(side='left', padx=20, fill='y')

        # Кнопки управления
        ttk.Button(
            btn_frame,
            text="🔄 Обновить 3D",
            command=self._update_visualization
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="🏠 Сброс (0°)",
            command=self._reset_angles
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="📍 Применить все",
            command=self._apply_all_angles
        ).pack(side='left', padx=5)

        # Разделитель
        ttk.Separator(btn_frame, orient='vertical').pack(side='left', padx=20, fill='y')

        # Кнопка экстренной остановки
        self.emergency_btn = ttk.Button(
            btn_frame,
            text="🛑 ЭКСТРЕННАЯ ОСТАНОВКА",
            command=self._emergency_stop
        )
        self.emergency_btn.pack(side='right', padx=10)

        # Кнопка выхода
        ttk.Button(
            btn_frame,
            text="❌ Выход",
            command=self.root.quit
        ).pack(side='right', padx=5)

    # ============================
    # Обработка слайдеров
    # ============================

    def _on_slider_change(self, idx):
        """Обработка изменения ползунка."""
        try:
            angle = self.slider_vars[idx].get()
            self.joint_angles[idx] = angle
            self.target_angles[idx] = angle
            self._update_position_display(idx)
            self._draw_robot()
            self._update_info()
        except Exception as e:
            print(f"Error in slider change: {e}")

    def _on_entry_change(self, idx):
        """Обработка ввода в поле угла."""
        try:
            angle = self.slider_vars[idx].get()
            min_a, max_a = self.SAFE_ANGLE_LIMITS[idx]
            angle = max(min_a, min(max_a, angle))
            self.slider_vars[idx].set(angle)
            self.joint_angles[idx] = angle
            self.target_angles[idx] = angle
            self._update_position_display(idx)
            self._draw_robot()
            self._update_info()
        except Exception as e:
            print(f"Error in entry change: {e}")

    def _update_position_display(self, idx):
        """Обновление отображения позиции мотора."""
        angle = self.joint_angles[idx]
        position = RobotKinematics6DOF.angle_to_motor_position(angle)
        self.position_vars[idx].set(f"POS: {position}")

    # ============================
    # Маппинг и инверсия моторов
    # ============================

    def _get_motor_id_for_joint(self, joint_index: int) -> int:
        """Получение ID мотора для сустава (из конфигурации)."""
        key = f'joint_{joint_index}'
        if key in DEFAULT_MOTOR_MAPPING:
            return DEFAULT_MOTOR_MAPPING[key]['motor_id']
        return joint_index + 1

    def _is_joint_inverted(self, joint_index: int) -> bool:
        """Проверка, инвертирован ли сустав."""
        key = f'joint_{joint_index}'
        if key in DEFAULT_MOTOR_MAPPING:
            return DEFAULT_MOTOR_MAPPING[key].get('inverted', False)
        return False

    def _apply_inversion(self, position: int, joint_index: int) -> int:
        """Применение инверсии позиции если мотор установлен в обратном направлении.

        Инверсия зеркалит позицию относительно центра (2048):
        position -> MAX_POSITION - position
        Т.е. 0 <-> 4095, 1024 <-> 3071, 2048 остаётся на месте.
        """
        if self._is_joint_inverted(joint_index):
            return MAX_POSITION - position
        return position

    # ============================
    # Целевая точка и IK
    # ============================

    def _solve_ik_for_target(self):
        """Решение обратной кинематики для целевой точки XYZ."""
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()

        self.target_point = (x, y, z)

        # Проверка досягаемости
        distance = math.sqrt(x**2 + y**2 + z**2)
        max_reach = self.kinematics.get_total_reach()
        if distance > max_reach:
            self.ik_status_var.set(
                f"❌ Точка ({x:.0f}, {y:.0f}, {z:.0f}) за пределами досягаемости! "
                f"D={distance:.0f} > {max_reach:.0f} мм"
            )
            self._draw_robot()  # Всё равно покажем маркер
            return None

        # Решение IK
        self.ik_status_var.set("⏳ Решение обратной кинематики...")
        self.root.update_idletasks()

        angles = self.ik_solver.solve(x, y, z, max_iterations=200, tolerance=1.0)

        if angles is None:
            self.ik_status_var.set(
                f"❌ IK не сошлась для ({x:.0f}, {y:.0f}, {z:.0f}). "
                f"Попробуйте другую точку."
            )
            self._draw_robot()
            return None

        # Проверка и обрезка по безопасным пределам
        clamped = False
        for i in range(6):
            min_a, max_a = self.SAFE_ANGLE_LIMITS[i]
            if angles[i] < min_a or angles[i] > max_a:
                angles[i] = max(min_a, min(max_a, angles[i]))
                clamped = True

        # Проверяем точность после обрезки
        result_pos = self.kinematics.get_end_effector_position(angles)
        error = math.sqrt(
            (result_pos[0] - x)**2 +
            (result_pos[1] - y)**2 +
            (result_pos[2] - z)**2
        )

        # Обновление слайдеров
        for i in range(6):
            self.slider_vars[i].set(round(angles[i], 1))
            self.joint_angles[i] = angles[i]
            self.target_angles[i] = angles[i]
            self._update_position_display(i)

        # Статус
        clamp_warn = " (углы обрезаны!)" if clamped else ""
        self.ik_status_var.set(
            f"✅ IK решена! Точка ({x:.0f}, {y:.0f}, {z:.0f}) → "
            f"ошибка: {error:.1f} мм{clamp_warn}"
        )

        self._draw_robot()
        self._update_info()
        return angles

    def _show_target_on_3d(self):
        """Показать целевую точку на 3D без решения IK."""
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()
        self.target_point = (x, y, z)
        self._draw_robot()
        self.ik_status_var.set(f"📌 Целевая точка: ({x:.0f}, {y:.0f}, {z:.0f}) мм")

    def _move_to_target_point(self):
        """Решить IK и отправить команды на моторы."""
        angles = self._solve_ik_for_target()
        if angles is None:
            return

        if not self.is_connected:
            messagebox.showinfo(
                "IK решена",
                "Углы рассчитаны и установлены на слайдерах.\n\n"
                "Для отправки на моторы подключитесь!"
            )
            return

        # Отправка на моторы
        self._apply_all_angles()

    def _toggle_click_mode(self):
        """Переключение режима выбора точки кликом."""
        self.click_mode = self.click_mode_var.get()
        if self.click_mode:
            self.ik_status_var.set("🖱️ Кликните по 3D визуализации для выбора точки")
        else:
            self.ik_status_var.set("")

    def _on_3d_click(self, event):
        """Обработка клика по 3D визуализации."""
        if not self.click_mode:
            return

        if event.inaxes != self.ax:
            return

        # Получаем 2D координаты клика в пикселях дисплея
        x2d, y2d = event.x, event.y

        # Проецируем точки пространства на экран для определения ближайшей
        # Используем метод: перебираем сетку точек в рабочем пространстве,
        # проецируем на экран и находим ближайшую к клику

        target_z = self.target_z_var.get()  # Используем текущий Z из поля ввода
        best_point = None
        best_dist = float('inf')

        max_reach = self.kinematics.get_total_reach()

        # Сетка точек на плоскости z=target_z
        grid_step = max_reach / 10
        for gx in np.arange(-max_reach, max_reach + grid_step, grid_step):
            for gy in np.arange(-max_reach, max_reach + grid_step, grid_step):
                # Проецируем 3D точку на экран
                x2, y2, _ = proj3d.proj_transform(gx, gy, target_z, self.ax.get_proj())
                # Конвертируем в пиксели дисплея
                coords = self.ax.transData.transform((x2, y2))
                sx, sy = coords[0], coords[1]

                dist = math.sqrt((sx - x2d)**2 + (sy - y2d)**2)
                if dist < best_dist:
                    best_dist = dist
                    best_point = (gx, gy, target_z)

        if best_point is not None:
            # Уточнение: более мелкая сетка вокруг найденной точки
            cx, cy = best_point[0], best_point[1]
            fine_step = grid_step / 10
            for gx in np.arange(cx - grid_step, cx + grid_step + fine_step, fine_step):
                for gy in np.arange(cy - grid_step, cy + grid_step + fine_step, fine_step):
                    x2, y2, _ = proj3d.proj_transform(gx, gy, target_z, self.ax.get_proj())
                    coords = self.ax.transData.transform((x2, y2))
                    sx, sy = coords[0], coords[1]

                    dist = math.sqrt((sx - x2d)**2 + (sy - y2d)**2)
                    if dist < best_dist:
                        best_dist = dist
                        best_point = (gx, gy, target_z)

            # Обновляем поля ввода
            self.target_x_var.set(round(best_point[0], 1))
            self.target_y_var.set(round(best_point[1], 1))
            self.target_z_var.set(round(best_point[2], 1))

            self.target_point = best_point
            self.ik_status_var.set(
                f"🖱️ Выбрана точка: ({best_point[0]:.1f}, {best_point[1]:.1f}, {best_point[2]:.1f}) мм"
            )
            self._draw_robot()

    # ============================
    # Маршрутные точки (Waypoints)
    # ============================

    def _add_waypoint(self):
        """Добавить текущую целевую точку в список маршрутных точек."""
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()
        wp = (x, y, z)
        self.waypoints.append(wp)
        idx = len(self.waypoints)
        self.wp_listbox.insert(tk.END, f"  #{idx}: ({x:.1f}, {y:.1f}, {z:.1f}) мм")
        self._draw_robot()
        self.ik_status_var.set(f"📌 Точка #{idx} добавлена: ({x:.0f}, {y:.0f}, {z:.0f})")

    def _remove_waypoint(self):
        """Удалить выбранную маршрутную точку."""
        sel = self.wp_listbox.curselection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите точку для удаления!")
            return
        idx = sel[0]
        self.waypoints.pop(idx)
        self._refresh_waypoint_list()
        self._draw_robot()

    def _clear_waypoints(self):
        """Очистить все маршрутные точки."""
        self.waypoints.clear()
        self.wp_listbox.delete(0, tk.END)
        self._draw_robot()
        self.ik_status_var.set("🗑️ Все маршрутные точки удалены")

    def _refresh_waypoint_list(self):
        """Обновить отображение списка маршрутных точек."""
        self.wp_listbox.delete(0, tk.END)
        for i, (x, y, z) in enumerate(self.waypoints):
            self.wp_listbox.insert(tk.END, f"  #{i+1}: ({x:.1f}, {y:.1f}, {z:.1f}) мм")

    def _on_waypoint_double_click(self, event):
        """Двойной клик по маршрутной точке — установить как целевую."""
        sel = self.wp_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        x, y, z = self.waypoints[idx]
        self.target_x_var.set(x)
        self.target_y_var.set(y)
        self.target_z_var.set(z)
        self.target_point = (x, y, z)
        self._draw_robot()
        self.ik_status_var.set(f"🎯 Выбрана точка #{idx+1}: ({x:.0f}, {y:.0f}, {z:.0f})")

    def _go_to_selected_waypoint(self):
        """Решить IK и двигать к выбранной маршрутной точке."""
        sel = self.wp_listbox.curselection()
        if not sel:
            messagebox.showwarning("Предупреждение", "Выберите точку из списка!")
            return
        idx = sel[0]
        x, y, z = self.waypoints[idx]
        self.target_x_var.set(x)
        self.target_y_var.set(y)
        self.target_z_var.set(z)
        self._move_to_target_point()

    def _run_waypoints(self):
        """Последовательный обход всех маршрутных точек."""
        if not self.waypoints:
            messagebox.showwarning("Предупреждение", "Список маршрутных точек пуст!")
            return

        wp_text = "\n".join([
            f"  #{i+1}: ({x:.0f}, {y:.0f}, {z:.0f}) мм"
            for i, (x, y, z) in enumerate(self.waypoints)
        ])

        if not messagebox.askyesno(
            "Обход маршрутных точек",
            f"Последовательно двигать к {len(self.waypoints)} точкам?\n\n"
            f"{wp_text}\n\n"
            f"⚠️ Скорость: {self.SAFE_SPEED} (безопасная)\n"
            f"🛑 Нажмите ЭКСТРЕННУЮ ОСТАНОВКУ при необходимости!"
        ):
            return

        # Запуск в отдельном потоке чтобы не блокировать UI
        thread = threading.Thread(target=self._run_waypoints_thread, daemon=True)
        thread.start()

    def _run_waypoints_thread(self):
        """Поток последовательного обхода маршрутных точек."""
        self.is_moving = True
        total = len(self.waypoints)

        for i, (x, y, z) in enumerate(self.waypoints):
            if not self.is_moving:
                # Остановлено экстренной остановкой
                break

            # Обновляем UI из потока
            self.root.after(0, lambda idx=i, xx=x, yy=y, zz=z: self._waypoint_step(idx, xx, yy, zz, total))

            # Решаем IK
            self.target_point = (x, y, z)
            distance = math.sqrt(x**2 + y**2 + z**2)
            max_reach = self.kinematics.get_total_reach()

            if distance > max_reach:
                self.root.after(0, lambda idx=i: self.info_text.insert(
                    tk.END, f"❌ Точка #{idx+1} за пределами досягаемости\n"))
                continue

            angles = self.ik_solver.solve(x, y, z, max_iterations=200, tolerance=1.0)
            if angles is None:
                self.root.after(0, lambda idx=i: self.info_text.insert(
                    tk.END, f"❌ IK не решена для точки #{idx+1}\n"))
                continue

            # Обрезка по безопасным пределам
            for j in range(6):
                min_a, max_a = self.SAFE_ANGLE_LIMITS[j]
                angles[j] = max(min_a, min(max_a, angles[j]))

            # Обновляем слайдеры
            self.root.after(0, lambda a=angles[:]: self._update_sliders_from_angles(a))

            # Отправляем на моторы если подключены
            if self.is_connected and self.st3215:
                for j in range(6):
                    motor_id = self._get_motor_id_for_joint(j)
                    position = RobotKinematics6DOF.angle_to_motor_position(angles[j])
                    position = self._apply_inversion(position, j)
                    try:
                        self.st3215.MoveTo(
                            motor_id, position,
                            speed=self.SAFE_SPEED, acc=DEFAULT_ACC
                        )
                    except Exception as e:
                        self.root.after(0, lambda idx=i, err=e: self.info_text.insert(
                            tk.END, f"❌ Точка #{idx+1} J{j+1} ошибка: {err}\n"))

                # Ждём пока моторы доедут (примерная оценка)
                import time
                time.sleep(2.0)

            self.root.after(0, lambda idx=i: self.info_text.insert(
                tk.END, f"✅ Точка #{idx+1} достигнута\n"))

        self.is_moving = False
        self.root.after(0, lambda: self.ik_status_var.set(
            f"✅ Обход маршрута завершён ({total} точек)"))

    def _waypoint_step(self, idx, x, y, z, total):
        """Обновление UI при переходе к следующей маршрутной точке."""
        self.target_x_var.set(x)
        self.target_y_var.set(y)
        self.target_z_var.set(z)
        self.ik_status_var.set(
            f"▶️ Точка {idx+1}/{total}: ({x:.0f}, {y:.0f}, {z:.0f}) мм")
        self.wp_listbox.selection_clear(0, tk.END)
        self.wp_listbox.selection_set(idx)
        self.wp_listbox.see(idx)

    def _update_sliders_from_angles(self, angles):
        """Обновить слайдеры из массива углов (вызывается из UI потока)."""
        for i in range(6):
            self.slider_vars[i].set(round(angles[i], 1))
            self.joint_angles[i] = angles[i]
            self.target_angles[i] = angles[i]
            self._update_position_display(i)
        self._draw_robot()
        self._update_info()

    # ============================
    # Проверенные точки (пресеты)
    # ============================

    def _refresh_preset_list(self):
        """Обновить список проверенных точек."""
        self.preset_listbox.delete(0, tk.END)
        for i, (x, y, z, name) in enumerate(self.preset_points):
            self.preset_listbox.insert(
                tk.END, f"#{i+1} {name}: ({x:.0f}, {y:.0f}, {z:.0f})")

    def _on_preset_select(self, event):
        """Обработчик выбора проверенной точки."""
        sel = self.preset_listbox.curselection()
        if sel:
            idx = sel[0]
            x, y, z, name = self.preset_points[idx]
            self.target_x_var.set(x)
            self.target_y_var.set(y)
            self.target_z_var.set(z)
            self.target_point = (x, y, z)
            self._draw_robot()
            self.ik_status_var.set(f"📌 Выбрана точка: {name}")

    def _save_preset_point(self):
        """Сохранить текущую успешную точку в пресеты."""
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()

        # Проверяем IK
        angles = self.ik_solver.solve(x, y, z, max_iterations=200, tolerance=1.0)
        if angles is None:
            messagebox.showwarning(
                "IK не решена",
                f"Для точки ({x:.0f}, {y:.0f}, {z:.0f})\nобратная кинематика не сходится!"
            )
            return

        # Проверяем пределы
        for i in range(6):
            min_a, max_a = self.SAFE_ANGLE_LIMITS[i]
            if angles[i] < min_a or angles[i] > max_a:
                if not messagebox.askyesno(
                    "Вне пределов",
                    f"Угол J{i+1} = {angles[i]:.1f}° вне безопасного диапазона [{min_a}°, {max_a}°]\n"
                    f"Сохранить несмотря на это?"
                ):
                    return

        name = f"Точка #{len(self.preset_points)+1}"
        self.preset_points.append((x, y, z, name))
        self._refresh_preset_list()
        self.ik_status_var.set(f"✅ Точка сохранена: {name}")

    def _remove_preset_point(self):
        """Удалить выбранную точку из пресетов."""
        sel = self.preset_listbox.curselection()
        if sel:
            idx = sel[0]
            removed = self.preset_points.pop(idx)
            self._refresh_preset_list()
            self.ik_status_var.set(f"🗑️ Удалена точка: {removed[3]}")

    def _clear_preset_points(self):
        """Очистить все пресеты."""
        if messagebox.askyesno("Подтверждение", "Удалить все проверенные точки?"):
            self.preset_points = []
            self._refresh_preset_list()
            self.ik_status_var.set("")

    def _apply_preset_point(self):
        """Применить выбранную точку (решить IK и установить углы)."""
        sel = self.preset_listbox.curselection()
        if not sel:
            messagebox.showinfo("Инфо", "Выберите точку из списка")
            return

        idx = sel[0]
        x, y, z, name = self.preset_points[idx]

        self.target_x_var.set(x)
        self.target_y_var.set(y)
        self.target_z_var.set(z)
        self.target_point = (x, y, z)

        # Решаем IK
        angles = self.ik_solver.solve(x, y, z, max_iterations=200, tolerance=1.0)
        if angles is None:
            self.ik_status_var.set(f"❌ IK не решена для {name}")
            self._draw_robot()
            return

        # Обрезка по пределам
        clamped = False
        for i in range(6):
            min_a, max_a = self.SAFE_ANGLE_LIMITS[i]
            if angles[i] < min_a or angles[i] > max_a:
                angles[i] = max(min_a, min(max_a, angles[i]))
                clamped = True

        # Проверка точности
        result_pos = self.kinematics.get_end_effector_position(angles)
        error = math.sqrt(
            (result_pos[0] - x)**2 +
            (result_pos[1] - y)**2 +
            (result_pos[2] - z)**2
        )

        # Обновляем слайдеры
        for i in range(6):
            self.slider_vars[i].set(round(angles[i], 1))
            self.joint_angles[i] = angles[i]
            self.target_angles[i] = angles[i]
            self._update_position_display(i)

        clamp_warn = " (обрезано)" if clamped else ""
        self.ik_status_var.set(f"✅ {name}: ошибка {error:.1f} мм{clamp_warn}")
        self._draw_robot()
        self._update_info()

    # ============================
    # Подключение ST3215
    # ============================

    def _connect(self):
        """Подключение к моторам через ST3215."""
        if self.is_connected:
            messagebox.showinfo("Инфо", "Уже подключено!")
            return

        if not ST3215_AVAILABLE:
            messagebox.showerror(
                "Ошибка",
                "Библиотека st3215 не найдена!\n\n"
                "Установите: pip install st3215"
            )
            return

        port = self.port_var.get()
        self.device = port

        # Попытка подключения через ST3215
        try:
            self.st3215 = ST3215(device=self.device)
            self.is_connected = True
            self.conn_label.configure(
                text="✅ Подключено",
                foreground='#00ff88'
            )
            messagebox.showinfo(
                "Успех",
                f"Подключено к {port}\n\n"
                f"⚠️ БЕЗОПАСНЫЙ РЕЖИМ:\n"
                f"- Скорость: {self.SAFE_SPEED} (10%)\n"
                f"- Углы ограничены\n"
                f"- Нажмите 'Сканировать моторы' для проверки"
            )
        except Exception as e:
            messagebox.showerror("Ошибка подключения", str(e))
            self.st3215 = None

    def _disconnect(self):
        """Отключение от моторов."""
        if self.st3215:
            try:
                if hasattr(self.st3215, 'portHandler'):
                    self.st3215.portHandler.closePort()
            except Exception as e:
                print(f"⚠️ Ошибка закрытия порта: {e}")
        self.st3215 = None
        self.is_connected = False
        self.conn_label.configure(
            text="❌ Отключено",
            foreground='red'
        )

    def _scan_motors(self):
        """Сканирование подключенных моторов через ST3215."""
        if not self.is_connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь!")
            return

        if not self.st3215:
            messagebox.showwarning("Предупреждение", "ST3215 не инициализирован!")
            return

        try:
            self.found_servos = self.st3215.ListServos()
            if self.found_servos:
                messagebox.showinfo(
                    "Найдены моторы",
                    f"Найдено: {len(self.found_servos)}\n"
                    f"IDs: {self.found_servos}"
                )
            else:
                messagebox.showwarning("Моторы не найдены", "Проверьте подключение!")
        except Exception as e:
            messagebox.showerror("Ошибка сканирования", str(e))

    # ============================
    # Движение моторов
    # ============================

    def _move_joint(self, idx):
        """Движение конкретного сустава."""
        if not self.is_connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь!")
            return

        if self.is_moving:
            messagebox.showwarning("Предупреждение", "Движение уже выполняется!")
            return

        angle = self.target_angles[idx]
        motor_id = self._get_motor_id_for_joint(idx)
        position = RobotKinematics6DOF.angle_to_motor_position(angle)
        position = self._apply_inversion(position, idx)

        # Подтверждение
        inv_mark = " (инв.)" if self._is_joint_inverted(idx) else ""
        if not messagebox.askyesno(
            "Подтверждение",
            f"Двигать {self.JOINT_NAMES[idx]}?{inv_mark}\n"
            f"Угол: {angle:.1f}°\n"
            f"Позиция: {position}\n"
            f"Мотор ID: {motor_id}\n"
            f"Скорость: {self.SAFE_SPEED}"
        ):
            return

        # Движение с безопасной скоростью через ST3215
        self.is_moving = True
        try:
            self.st3215.MoveTo(
                motor_id,
                position,
                speed=self.SAFE_SPEED,
                acc=DEFAULT_ACC
            )
            messagebox.showinfo("Успех", f"{self.JOINT_NAMES[idx]} движется!")
        except Exception as e:
            messagebox.showerror("Ошибка движения", str(e))
        finally:
            self.is_moving = False

    def _apply_all_angles(self):
        """Применение всех углов к моторам."""
        if not self.is_connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь!")
            return

        if self.is_moving:
            messagebox.showwarning("Предупреждение", "Движение уже выполняется!")
            return

        # Подтверждение
        angles_text = "\n".join([
            f"  {self.JOINT_NAMES[i]}: {self.target_angles[i]:.1f}°"
            for i in range(6)
        ])

        if not messagebox.askyesno(
            "Подтверждение движения",
            f"Применить все углы?\n\n"
            f"⚠️ Безопасная скорость: {self.SAFE_SPEED}\n\n"
            f"{angles_text}\n\n"
            f"🛑 Нажмите ЭКСТРЕННУЮ ОСТАНОВКУ при необходимости!"
        ):
            return

        # Движение всех суставов
        self.is_moving = True
        moved_count = 0

        for i in range(6):
            motor_id = self._get_motor_id_for_joint(i)
            position = RobotKinematics6DOF.angle_to_motor_position(self.target_angles[i])
            position = self._apply_inversion(position, i)

            try:
                self.st3215.MoveTo(
                    motor_id,
                    position,
                    speed=self.SAFE_SPEED,
                    acc=DEFAULT_ACC
                )
                moved_count += 1
                self.info_text.insert(tk.END, f"✅ J{i+1} -> {position}\n")
            except Exception as e:
                self.info_text.insert(tk.END, f"❌ J{i+1} ошибка: {e}\n")

        self.info_text.insert(tk.END, f"\nДвигается: {moved_count}/6 суставов\n")
        self.is_moving = False

        if moved_count > 0:
            messagebox.showinfo(
                "В процессе",
                f"Отправлены команды для {moved_count}/6 суставов\n"
                f"Скорость: {self.SAFE_SPEED} (безопасная)"
            )

    def _reset_angles(self):
        """Сброс всех углов к нулю."""
        for i in range(6):
            self.slider_vars[i].set(0.0)
            self.joint_angles[i] = 0.0
            self.target_angles[i] = 0.0
            self._update_position_display(i)
        self._draw_robot()
        self._update_info()

    def _emergency_stop(self):
        """Экстренная остановка всех моторов."""
        # Сразу останавливаем обход маршрута
        self.is_moving = False

        if not self.is_connected:
            messagebox.showwarning("Предупреждение", "Не подключено!")
            return

        if messagebox.askyesno(
            "🛑 ЭКСТРЕННАЯ ОСТАНОВКА",
            "Остановить ВСЕ моторы?\n\nЭто отключит момент!"
        ):
            try:
                # Остановка всех найденных серво через ST3215
                for motor_id in self.found_servos:
                    self.st3215.StopServo(motor_id)
                # Если серво не были просканированы, останавливаем по маппингу
                if not self.found_servos:
                    for i in range(6):
                        motor_id = self._get_motor_id_for_joint(i)
                        self.st3215.StopServo(motor_id)
                self.conn_label.configure(
                    text="⚠️ ОСТАНОВЛЕНО",
                    foreground='orange'
                )
                messagebox.showinfo("Остановлено", "Все моторы остановлены!")
            except Exception as e:
                messagebox.showerror("Ошибка остановки", str(e))

    def _update_visualization(self):
        """Обновление визуализации из ползунков."""
        for i in range(6):
            self.joint_angles[i] = self.slider_vars[i].get()
            self._update_position_display(i)
        self._draw_robot()
        self._update_info()

    # ============================
    # 3D отрисовка
    # ============================

    def _draw_robot(self):
        """Отрисовка 3D модели робота с целевой точкой и маршрутными точками."""
        if not hasattr(self, 'ax') or not hasattr(self, 'figure') or not hasattr(self, 'canvas'):
            return

        self.ax.clear()
        self.ax.set_facecolor(FANUC_PANEL)

        # Расчет позиций через кинематическую модель
        joint_positions = self.kinematics.get_all_joint_positions(self.joint_angles)

        x_points = [p[0] for p in joint_positions]
        y_points = [p[1] for p in joint_positions]
        z_points = [p[2] for p in joint_positions]

        # Настройка осей
        max_reach = self.kinematics.get_total_reach()
        self.ax.set_xlim(-max_reach, max_reach)
        self.ax.set_ylim(-max_reach, max_reach)
        self.ax.set_zlim(-max_reach/2, max_reach + 50)
        self.ax.set_xlabel('X (мм)', color='white')
        self.ax.set_ylabel('Y (мм)', color='white')
        self.ax.set_zlabel('Z (мм)', color='white')

        title = f'Робот ST3215 (Reach={max_reach}мм)'
        if self.click_mode:
            title += ' [РЕЖИМ КЛИКА]'
        self.ax.set_title(title, color='white', fontsize=12)

        # Стиль осей
        self.ax.xaxis.pane.fill = False
        self.ax.yaxis.pane.fill = False
        self.ax.zaxis.pane.fill = False
        self.ax.xaxis.pane.set_edgecolor('#666666')
        self.ax.yaxis.pane.set_edgecolor('#666666')
        self.ax.zaxis.pane.set_edgecolor('#666666')
        self.ax.tick_params(colors='white')

        # Отрисовка рабочей зоны (окружность на Z=0)
        theta = np.linspace(0, 2 * np.pi, 64)
        self.ax.plot(
            max_reach * np.cos(theta),
            max_reach * np.sin(theta),
            np.zeros(64),
            color='#333366', linewidth=0.5, linestyle='--', alpha=0.5
        )

        # Отрисовка линий робота
        self.ax.plot(
            x_points, y_points, z_points,
            color=FANUC_GREEN, linewidth=3, marker='o', markersize=8
        )

        # Отрисовка суставов
        for i, (x, y, z) in enumerate(zip(x_points, y_points, z_points)):
            color = KINEMA_COLORS[i % len(KINEMA_COLORS)]
            self.ax.scatter([x], [y], [z], color=color, s=150, edgecolors='white', linewidth=1)

            # Подпись сустава
            label = f'J{i}' if i > 0 else 'Base'
            self.ax.text(x, y, z + 5, label, color='white', fontsize=8)

        # Позиция инструмента (end effector)
        end_pos = self.kinematics.get_end_effector_position(self.joint_angles)
        self.ax.scatter(
            [end_pos[0]], [end_pos[1]], [end_pos[2]],
            color='red', s=200, marker='x', linewidth=3
        )

        # --- Целевая точка (большой маркер) ---
        if self.target_point is not None:
            tx, ty, tz = self.target_point
            # Маркер цели
            self.ax.scatter(
                [tx], [ty], [tz],
                color='#FF00FF', s=300, marker='*', linewidth=2,
                edgecolors='white', zorder=10, label='Цель'
            )
            # Вертикальная линия от пола до точки
            self.ax.plot(
                [tx, tx], [ty, ty], [0, tz],
                color='#FF00FF', linewidth=1, linestyle=':', alpha=0.6
            )
            # Подпись
            self.ax.text(
                tx, ty, tz + 10,
                f'({tx:.0f}, {ty:.0f}, {tz:.0f})',
                color='#FF00FF', fontsize=8, fontweight='bold'
            )
            # Линия от end-effector до цели
            self.ax.plot(
                [end_pos[0], tx], [end_pos[1], ty], [end_pos[2], tz],
                color='#FF00FF', linewidth=1, linestyle='--', alpha=0.4
            )

        # --- Маршрутные точки ---
        if self.waypoints:
            wp_x = [p[0] for p in self.waypoints]
            wp_y = [p[1] for p in self.waypoints]
            wp_z = [p[2] for p in self.waypoints]

            # Маркеры точек
            self.ax.scatter(
                wp_x, wp_y, wp_z,
                color='#FFD700', s=120, marker='D', edgecolors='white',
                linewidth=1, zorder=9, label='Waypoints'
            )

            # Линии маршрута между точками
            if len(self.waypoints) > 1:
                self.ax.plot(
                    wp_x, wp_y, wp_z,
                    color='#FFD700', linewidth=1.5, linestyle='-', alpha=0.7
                )

            # Номера точек
            for i, (wx, wy, wz) in enumerate(self.waypoints):
                self.ax.text(
                    wx, wy, wz + 8, f'#{i+1}',
                    color='#FFD700', fontsize=8, fontweight='bold'
                )

        # Легенда если есть маркеры
        if self.target_point or self.waypoints:
            self.ax.legend(
                loc='upper left', fontsize=8,
                facecolor='#16213e', edgecolor='#666666',
                labelcolor='white'
            )

        self.figure.tight_layout()
        self.canvas.draw()

    def _update_info(self):
        """Обновление информационной панели."""
        positions = self.kinematics.get_all_joint_positions(self.joint_angles)
        end_pos = self.kinematics.get_end_effector_position(self.joint_angles)
        orientation = self.kinematics.get_end_effector_orientation(self.joint_angles)

        self.info_text.delete('1.0', tk.END)

        # Статус подключения
        status = "✅ Подключено" if self.is_connected else "❌ Отключено"
        self.info_text.insert(tk.END, f"=== СТАТУС: {status} ===\n\n")

        # Углы и позиции моторов
        self.info_text.insert(tk.END, "=== УГЛЫ И ПОЗИЦИИ ===\n\n")
        for i in range(6):
            angle = self.joint_angles[i]
            pos = RobotKinematics6DOF.angle_to_motor_position(angle)
            min_a, max_a = self.SAFE_ANGLE_LIMITS[i]
            name = self.JOINT_NAMES[i].split('(')[0].strip()
            self.info_text.insert(
                tk.END,
                f"{name}: {angle:+6.1f}° [{min_a:+d};{max_a:+d}] | POS: {pos:4d}\n"
            )

        # Координаты суставов
        self.info_text.insert(tk.END, "\n=== КООРДИНАТЫ (мм) ===\n\n")
        self.info_text.insert(tk.END, f"{'База':<10} (  0.0,   0.0,   0.0)\n")
        for i, pos in enumerate(positions[1:], 1):
            self.info_text.insert(
                tk.END,
                f"{'J'+str(i):<10} ({pos[0]:6.1f}, {pos[1]:6.1f}, {pos[2]:6.1f})\n"
            )

        # Позиция инструмента
        self.info_text.insert(tk.END, "\n=== ИНСТРУМЕНТ ===\n\n")
        self.info_text.insert(
            tk.END,
            f"Position: ({end_pos[0]:6.1f}, {end_pos[1]:6.1f}, {end_pos[2]:6.1f}) мм\n"
        )

        # Ориентация
        roll, pitch, yaw = orientation
        self.info_text.insert(
            tk.END,
            f"Orientation:\n"
            f"  Roll:  {math.degrees(roll):6.1f}°\n"
            f"  Pitch: {math.degrees(pitch):6.1f}°\n"
            f"  Yaw:   {math.degrees(yaw):6.1f}°\n"
        )

        # Расстояние
        distance = math.sqrt(end_pos[0]**2 + end_pos[1]**2 + end_pos[2]**2)
        self.info_text.insert(
            tk.END,
            f"\nDistance from base: {distance:.1f} мм\n"
            f"Max reach: {self.kinematics.get_total_reach():.1f} мм\n"
        )

        # Целевая точка
        if self.target_point:
            tx, ty, tz = self.target_point
            target_dist = math.sqrt(
                (end_pos[0] - tx)**2 +
                (end_pos[1] - ty)**2 +
                (end_pos[2] - tz)**2
            )
            self.info_text.insert(
                tk.END,
                f"\n=== ЦЕЛЕВАЯ ТОЧКА ===\n\n"
                f"Target: ({tx:.1f}, {ty:.1f}, {tz:.1f}) мм\n"
                f"Error:  {target_dist:.1f} мм\n"
            )

        # Маршрутные точки
        if self.waypoints:
            self.info_text.insert(tk.END, f"\n=== WAYPOINTS ({len(self.waypoints)}) ===\n\n")
            for i, (wx, wy, wz) in enumerate(self.waypoints):
                self.info_text.insert(tk.END, f"#{i+1}: ({wx:.0f}, {wy:.0f}, {wz:.0f})\n")

    def _on_closing(self):
        """Обработчик закрытия окна."""
        self.is_moving = False  # Остановить обход маршрута
        if self.is_connected:
            if messagebox.askyesno(
                "Закрытие",
                "Отключить моторы перед закрытием?"
            ):
                # Остановка всех серво
                try:
                    for motor_id in self.found_servos:
                        self.st3215.StopServo(motor_id)
                    if not self.found_servos:
                        for i in range(6):
                            self.st3215.StopServo(self._get_motor_id_for_joint(i))
                except Exception:
                    pass
                self._disconnect()
        self.root.destroy()

    def run(self):
        """Запуск приложения."""
        print("🚀 Запуск Safe Motor Visualizer...")
        print(f"\n⚠️ БЕЗОПАСНЫЙ РЕЖИМ:")
        print(f"  - Скорость: {self.SAFE_SPEED} (10% от макс)")
        print(f"  - Углы ограничены безопасными диапазонами")
        print(f"  - Требуется подтверждение перед движением")
        print(f"\nДлины звеньев: L0={self.kinematics.L0}, L1={self.kinematics.L1}, "
              f"L2={self.kinematics.L2}, L3={self.kinematics.L3}, "
              f"L4={self.kinematics.L4}, L5={self.kinematics.L5} мм")
        print(f"Максимальная досягаемость: {self.kinematics.get_total_reach()} мм")
        print(f"\n🎯 Новые функции:")
        print(f"  - Ввод целевой точки XYZ → обратная кинематика")
        print(f"  - Клик по 3D визуализации (включите галочку)")
        print(f"  - Маршрутные точки (waypoints) с последовательным обходом")
        print("\n" + "=" * 70)
        self.root.mainloop()


def main():
    """Точка входа."""
    print("\n" + "=" * 70)
    print("🤖 ST3215 Safe Motor Visualizer")
    print("=" * 70)
    print("\n⚠️ БЕЗОПАСНЫЙ РЕЖИМ:")
    print("  - Скорость ограничена: 500 (10% от макс)")
    print("  - Углы ограничены для предотвращения столкновений")
    print("  - Требуется подтверждение перед движением")
    print("  - Кнопка экстренной остановки")
    print("\n🎯 Целевые точки:")
    print("  - Введите XYZ координаты и нажмите 'Рассчитать IK'")
    print("  - Включите 'Клик по 3D' для выбора точки мышью")
    print("  - Добавьте точки в маршрут и запустите обход")
    print("\nДлины звеньев (мм):")
    print("  L0 (База)       = 19")
    print("  L1 (Плечо 1)    = 134")
    print("  L2 (Плечо 2)    = 95")
    print("  L3 (Локоть)     = 34")
    print("  L4 (Запястье 1) = 35")
    print("  L5 (Запястье 2) = 0")
    print("\nМаксимальная досягаемость: 317 мм")
    print("\n" + "=" * 70 + "\n")

    app = SafeMotorVisualizer()
    app.run()


if __name__ == '__main__':
    main()
