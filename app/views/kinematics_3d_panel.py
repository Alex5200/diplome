#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kinematics 3D Panel — полная визуализация с IK, слайдерами, пресетами и маршрутами.

Переработано по образцу safe_motor_visualizer.py:
  - 6 слайдеров с безопасными диапазонами углов
  - Ввод целевой точки XYZ → обратная кинематика
  - Клик по 3D для выбора точки
  - Пресеты проверенных точек
  - Маршрутные точки (Waypoints) с последовательным обходом
  - Светлая тема (light theme)
"""

import math
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import proj3d  # noqa: F401

from app.controllers.motor_controller import MotorController
from app.models.kinematics import RobotKinematics6DOF, InverseKinematics6DOF
from app.config.constants import (
    MAX_POSITION, MIN_POSITION,
    KINEMA_COLORS,
    LIGHT_BG, LIGHT_PANEL, LIGHT_BORDER, LIGHT_TEXT, LIGHT_TEXT2,
    LIGHT_GREEN, LIGHT_ORANGE, LIGHT_RED, LIGHT_BLUE, LIGHT_ACCENT,
    LIGHT_HOVER, LIGHT_SELECT,
    DEFAULT_MOTOR_MAPPING,
)

# ── Безопасные диапазоны углов (°) ────────────────────────────────────────
SAFE_ANGLE_LIMITS: List[Tuple[float, float]] = [
    (-180, 180),   # J1 база      — полные 360°
    (-180, 180),   # J2 плечо 1   — полные 360°
    (-180, 180),   # J3 плечо 2   — полные 360°
    (-180, 180),   # J4 локоть    — полные 360°
    (-180, 180),   # J5 кисть 1   — полные 360°
    (-180, 180),   # J6 кисть 2   — полные 360°
]

JOINT_NAMES = [
    '🏗️ База (J1)',
    '💪 Плечо 1 (J2)',
    '💪 Плечо 2 (J3)',
    '🦾 Локоть (J4)',
    '🖐️ Кисть 1 (J5)',
    '🖐️ Кисть 2 (J6)',
]

# Цвета 3D-графика (белый фон matplotlib)
PLOT_BG  = "#ffffff"
PLOT_AX  = "#f8f8f8"
LINK_COL = "#0078d7"       # синий
EE_COL   = "#cf222e"       # красный — конечный эффектор
TGT_COL  = "#e65100"       # оранжевый — целевая точка
WP_COL   = "#8250df"       # фиолетовый — waypoints


class Kinematics3DPanel(ttk.Frame):
    """
    Панель 3D-визуализации кинематики с полным набором управления.

    Встраивается как ttk.Frame в главное окно (вкладка «3D View»).
    Работает автономно: не требует подключённого контроллера для
    визуализации, использует его только для отправки команд моторам.
    """

    def __init__(
        self,
        parent: tk.Misc,
        controller: MotorController,
        log_callback: Callable[[str, str], None],
    ):
        super().__init__(parent)
        self.controller = controller
        self.log = log_callback

        self._kin = RobotKinematics6DOF()
        self._ik  = InverseKinematics6DOF(self._kin)

        # Состояние суставов
        self.joint_angles: List[float] = [0.0] * 6
        self.slider_vars:   List[tk.DoubleVar] = []
        self.position_vars: List[tk.StringVar] = []

        # Целевая точка и маршруты
        self.target_point: Optional[Tuple[float, float, float]] = None
        self.waypoints:    List[Tuple[float, float, float]] = []
        self.preset_points: List[Tuple[float, float, float, str]] = [
            (100, 0,   150, "Центр передняя"),
            (150, 0,   100, "Дальняя низ"),
            (80,  50,  120, "Средняя левая"),
            (80, -50,  120, "Средняя правая"),
            (120, 0,   180, "Верхняя точка"),
        ]
        self.click_mode = False
        self._wp_running = False
        self.ik_target_reachable: bool = False   # True → целевая точка зелёная
        self._pending_draw: bool = False          # троттлинг перерисовки
        self._live_mode: bool = True              # следить за реальными позициями моторов

        # Траектория EE от текущей позиции до IK-цели (строится если ошибка < 15 мм)
        self.ik_path: Optional[List[Tuple[float, float, float]]] = None

        # matplotlib
        self.figure: Optional[plt.Figure] = None
        self.ax = None
        self.canvas: Optional[FigureCanvasTkAgg] = None

        self._build_ui()
        self._refresh_preset_list()
        self._draw_robot()

    # ──────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Sliders row (top) ──────────────────────────────────────────
        sliders_lf = ttk.LabelFrame(
            self,
            text="📐 Углы суставов — безопасные диапазоны",
            padding=6,
        )
        sliders_lf.pack(fill='x', padx=8, pady=(6, 2))
        self._build_sliders(sliders_lf)

        # ── Middle: 3D plot + info ─────────────────────────────────────
        mid = ttk.Frame(self)
        mid.pack(fill='both', expand=True, padx=8, pady=2)
        self._build_3d(mid)
        self._build_info(mid)

        # ── Bottom panels: target / presets / waypoints ────────────────
        bot = ttk.Frame(self)
        bot.pack(fill='x', padx=8, pady=(2, 6))
        self._build_target_panel(bot)
        self._build_presets_panel(bot)
        self._build_waypoints_panel(bot)

        # ── Action buttons (bottom strip) ──────────────────────────────
        self._build_action_bar()

    # ── Sliders ───────────────────────────────────────────────────────────

    def _build_sliders(self, parent: ttk.Frame) -> None:
        for i in range(6):
            row = ttk.Frame(parent)
            row.pack(fill='x', pady=1)

            min_a, max_a = SAFE_ANGLE_LIMITS[i]

            ttk.Label(row, text=JOINT_NAMES[i], width=20,
                      font=("Segoe UI", 9)).pack(side='left', padx=(0, 4))

            ttk.Label(row, text=f"[{min_a}°..{max_a}°]", width=14,
                      foreground=LIGHT_ORANGE,
                      font=("Segoe UI", 8)).pack(side='left', padx=2)

            var = tk.DoubleVar(value=0.0)
            self.slider_vars.append(var)

            slider = ttk.Scale(
                row, from_=min_a, to=max_a,
                variable=var, orient='horizontal', length=340,
                command=lambda v, idx=i: self._on_slider(idx),
            )
            slider.pack(side='left', padx=6)

            spinbox = ttk.Spinbox(
                row, from_=min_a, to=max_a,
                textvariable=var, width=7,
                command=lambda idx=i: self._on_entry(idx),
            )
            spinbox.pack(side='left', padx=2)
            spinbox.bind('<Return>', lambda e, idx=i: self._on_entry(idx))

            pos_var = tk.StringVar(value="POS: 2048")
            self.position_vars.append(pos_var)

            ttk.Label(row, textvariable=pos_var, width=13,
                      foreground=LIGHT_BLUE,
                      font=("Consolas", 9)).pack(side='left', padx=6)

            ttk.Button(row, text="▶", width=3,
                       command=lambda idx=i: self._send_joint(idx),
                       style="Accent.TButton").pack(side='left', padx=2)

    # ── 3D plot ───────────────────────────────────────────────────────────

    def _build_3d(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="🔬 3D Визуализация  (клик в режиме ✏️ = выбор точки)")
        lf.pack(side='left', fill='both', expand=True, padx=(0, 4))

        self.figure = plt.Figure(figsize=(7, 5), dpi=96, facecolor=PLOT_BG)
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax.set_facecolor(PLOT_AX)

        self.canvas = FigureCanvasTkAgg(self.figure, master=lf)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.canvas.mpl_connect('button_press_event', self._on_3d_click)

        cam_bar = ttk.Frame(lf)
        cam_bar.pack(fill='x', pady=3)

        ttk.Button(cam_bar, text="🔄 Камера",
                   command=self._reset_camera).pack(side='left', padx=4)

        ttk.Button(cam_bar, text="🏠 В ноль",
                   command=self._go_home).pack(side='left', padx=4)

        # Live-индикатор: мигает когда 3D обновляется от моторов
        self._live_var = tk.StringVar(value="⚫ live")
        self._live_label = ttk.Label(cam_bar, textvariable=self._live_var,
                                     foreground=LIGHT_TEXT2, font=("Segoe UI", 8, "bold"))
        self._live_label.pack(side='left', padx=8)

        self._live_toggle_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cam_bar, text="отслеживать моторы",
                        variable=self._live_toggle_var,
                        command=self._on_live_toggle).pack(side='left', padx=2)

        ttk.Label(cam_bar, text="ЛКМ — поворот  |  Колесо — масштаб",
                  foreground=LIGHT_TEXT2, font=("Segoe UI", 8)).pack(side='right', padx=8)

    # ── Info panel ────────────────────────────────────────────────────────

    def _build_info(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="📊 Координаты и статус")
        lf.pack(side='right', fill='y', padx=(4, 0))

        self.info_text = tk.Text(
            lf, width=34, height=18,
            bg=LIGHT_PANEL, fg=LIGHT_TEXT,
            font=("Consolas", 9),
            relief='flat', bd=1,
            wrap='word',
        )
        self.info_text.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        sb = ttk.Scrollbar(lf, orient='vertical', command=self.info_text.yview)
        sb.pack(side='right', fill='y')
        self.info_text.configure(yscrollcommand=sb.set)

        # Color tags
        self.info_text.tag_configure("ok",   foreground=LIGHT_GREEN)
        self.info_text.tag_configure("err",  foreground=LIGHT_RED)
        self.info_text.tag_configure("warn", foreground=LIGHT_ORANGE)
        self.info_text.tag_configure("head", foreground=LIGHT_ACCENT, font=("Consolas", 9, "bold"))

    # ── Target panel ──────────────────────────────────────────────────────

    def _build_target_panel(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="🎯 Целевая точка (мм)", padding=4)
        lf.pack(side='left', fill='both', expand=True, padx=(0, 4))

        xyz_row = ttk.Frame(lf)
        xyz_row.pack(fill='x', pady=2)

        for label, attr, default, color in [
            ("X:", "target_x_var",  100.0, LIGHT_RED),
            ("Y:", "target_y_var",    0.0, LIGHT_GREEN),
            ("Z:", "target_z_var",  150.0, LIGHT_BLUE),
        ]:
            ttk.Label(xyz_row, text=label, foreground=color,
                      font=("Segoe UI", 10, "bold")).pack(side='left', padx=(8, 1))
            var = tk.DoubleVar(value=default)
            setattr(self, attr, var)
            ttk.Spinbox(xyz_row, from_=-400, to=400,
                        textvariable=var, width=7,
                        increment=5.0).pack(side='left', padx=1)

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill='x', pady=2)
        ttk.Button(btn_row, text="🧮 Решить IK",
                   command=self._solve_ik).pack(side='left', padx=2)
        ttk.Button(btn_row, text="🎯 Двигать к точке",
                   command=self._move_to_target,
                   style="Accent.TButton").pack(side='left', padx=2)
        ttk.Button(btn_row, text="📌 Показать на 3D",
                   command=self._show_target).pack(side='left', padx=2)

        click_row = ttk.Frame(lf)
        click_row.pack(fill='x', pady=1)
        self.click_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(click_row, text="✏️ Клик по 3D = выбор точки",
                        variable=self.click_mode_var,
                        command=self._toggle_click_mode).pack(side='left', padx=2)

        self.ik_status_var = tk.StringVar(value="")
        ttk.Label(lf, textvariable=self.ik_status_var,
                  foreground=LIGHT_GREEN, wraplength=340,
                  font=("Segoe UI", 9)).pack(fill='x', pady=2)

    # ── Presets ───────────────────────────────────────────────────────────

    def _build_presets_panel(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="✅ Проверенные точки", padding=4)
        lf.pack(side='left', fill='both', expand=True, padx=(0, 4))

        listbox_frame = ttk.Frame(lf)
        listbox_frame.pack(fill='both', expand=True)

        self.preset_listbox = tk.Listbox(
            listbox_frame, height=5, width=32,
            bg=LIGHT_PANEL, fg=LIGHT_TEXT,
            selectbackground=LIGHT_SELECT, selectforeground=LIGHT_TEXT,
            font=("Consolas", 9), relief='flat', bd=1,
        )
        self.preset_listbox.pack(side='left', fill='both', expand=True)
        sb = ttk.Scrollbar(listbox_frame, orient='vertical',
                           command=self.preset_listbox.yview)
        sb.pack(side='right', fill='y')
        self.preset_listbox.configure(yscrollcommand=sb.set)
        self.preset_listbox.bind('<<ListboxSelect>>', self._on_preset_select)

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill='x', pady=2)
        ttk.Button(btn_row, text="➕", width=3,
                   command=self._save_preset).pack(side='left', padx=1)
        ttk.Button(btn_row, text="➖", width=3,
                   command=self._remove_preset).pack(side='left', padx=1)
        ttk.Button(btn_row, text="🗑️", width=3,
                   command=self._clear_presets).pack(side='left', padx=1)
        ttk.Button(btn_row, text="🎯 Применить",
                   command=self._apply_preset,
                   style="Accent.TButton").pack(side='left', padx=4)

    # ── Waypoints ─────────────────────────────────────────────────────────

    def _build_waypoints_panel(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="📍 Маршрутные точки", padding=4)
        lf.pack(side='left', fill='both', expand=True)

        listbox_frame = ttk.Frame(lf)
        listbox_frame.pack(fill='both', expand=True)

        self.wp_listbox = tk.Listbox(
            listbox_frame, height=5, width=36,
            bg=LIGHT_PANEL, fg=LIGHT_TEXT,
            selectbackground=LIGHT_SELECT, selectforeground=LIGHT_TEXT,
            font=("Consolas", 9), relief='flat', bd=1,
        )
        self.wp_listbox.pack(side='left', fill='both', expand=True)
        sb = ttk.Scrollbar(listbox_frame, orient='vertical',
                           command=self.wp_listbox.yview)
        sb.pack(side='right', fill='y')
        self.wp_listbox.configure(yscrollcommand=sb.set)
        self.wp_listbox.bind('<Double-1>', self._on_wp_double_click)

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill='x', pady=2)
        ttk.Button(btn_row, text="➕", width=3,
                   command=self._add_waypoint).pack(side='left', padx=1)
        ttk.Button(btn_row, text="➖", width=3,
                   command=self._remove_waypoint).pack(side='left', padx=1)
        ttk.Button(btn_row, text="🗑️", width=3,
                   command=self._clear_waypoints).pack(side='left', padx=1)
        ttk.Button(btn_row, text="▶️ Обход всех",
                   command=self._run_waypoints,
                   style="Accent.TButton").pack(side='left', padx=4)
        ttk.Button(btn_row, text="🎯 К выбранной",
                   command=self._go_to_selected_wp).pack(side='left', padx=1)

    # ── Action bar ────────────────────────────────────────────────────────

    def _build_action_bar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill='x', padx=8, pady=(0, 6))

        ttk.Button(bar, text="🔄 Обновить 3D",
                   command=self._update_viz).pack(side='left', padx=4)
        ttk.Button(bar, text="🏠 Сброс углов",
                   command=self._reset_angles).pack(side='left', padx=4)
        ttk.Button(bar, text="📤 Применить все углы к роботу",
                   command=self._apply_all,
                   style="Accent.TButton").pack(side='left', padx=4)
        ttk.Button(bar, text="🛑 СТОП",
                   command=self._emergency_stop,
                   style="Danger.TButton").pack(side='right', padx=4)

    # ──────────────────────────────────────────────────────────────────────
    # Slider / entry handlers
    # ──────────────────────────────────────────────────────────────────────

    def _on_slider(self, idx: int) -> None:
        angle = self.slider_vars[idx].get()
        self.joint_angles[idx] = angle
        self._update_pos_display(idx)
        self.ik_path = None          # ручное движение сбрасывает путь
        self._draw_robot()
        self._update_info()

    def _on_entry(self, idx: int) -> None:
        try:
            angle = self.slider_vars[idx].get()
            min_a, max_a = SAFE_ANGLE_LIMITS[idx]
            angle = max(min_a, min(max_a, angle))
            self.slider_vars[idx].set(angle)
            self.joint_angles[idx] = angle
            self._update_pos_display(idx)
            self._draw_robot()
            self._update_info()
        except Exception:
            pass

    def _update_pos_display(self, idx: int) -> None:
        angle = self.joint_angles[idx]
        pos = int((angle + 180.0) / 360.0 * MAX_POSITION)
        pos = max(0, min(MAX_POSITION, pos))
        self.position_vars[idx].set(f"POS: {pos}")

    # ──────────────────────────────────────────────────────────────────────
    # Motor helpers
    # ──────────────────────────────────────────────────────────────────────

    def _get_motor_id(self, joint_idx: int) -> int:
        key = f'joint_{joint_idx}'
        # Читаем из живого маппинга контроллера (обновляется через Setup)
        return self.controller.motor_mapping.get(key, {}).get('motor_id', joint_idx + 1)

    def _is_inverted(self, joint_idx: int) -> bool:
        key = f'joint_{joint_idx}'
        return self.controller.motor_mapping.get(key, {}).get('inverted', False)

    def _angle_to_position(self, angle: float, joint_idx: int) -> int:
        pos = int((angle + 180.0) / 360.0 * MAX_POSITION)
        pos = max(0, min(MAX_POSITION, pos))
        if self._is_inverted(joint_idx):
            pos = MAX_POSITION - pos
        return pos

    def _send_joint(self, idx: int) -> None:
        if not self.controller.connected:
            messagebox.showwarning("Нет подключения", "Сначала подключитесь к роботу!")
            return
        motor_id = self._get_motor_id(idx)
        pos = self._angle_to_position(self.joint_angles[idx], idx)
        inv_note = " (инв.)" if self._is_inverted(idx) else ""
        if messagebox.askyesno(
            "Подтверждение",
            f"Двигать {JOINT_NAMES[idx]}{inv_note}?\n"
            f"Угол: {self.joint_angles[idx]:.1f}°  →  позиция: {pos}",
        ):
            self.controller.move_motor(motor_id, pos)
            self.log(f"Двинул J{idx+1} → {self.joint_angles[idx]:.1f}° (pos={pos})", "info")

    # ──────────────────────────────────────────────────────────────────────
    # IK & target
    # ──────────────────────────────────────────────────────────────────────

    def _solve_ik(self) -> Optional[List[float]]:
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()
        self.target_point = (x, y, z)

        dist = math.sqrt(x**2 + y**2 + z**2)
        max_r = self._kin.get_total_reach()
        if dist > max_r:
            self.ik_status_var.set(
                f"❌ ({x:.0f},{y:.0f},{z:.0f}) за пределами досягаемости "
                f"(D={dist:.0f} > {max_r:.0f} мм)"
            )
            self._draw_robot()
            return None

        self.ik_status_var.set("⏳ Решение IK…")
        self.update_idletasks()

        result = self._ik.solve(x, y, z, max_iterations=300, tolerance=1.0)
        if result is None:
            self.ik_status_var.set(f"❌ IK не сошлась для ({x:.0f},{y:.0f},{z:.0f})")
            self._draw_robot()
            return None

        # Поддерживаем оба формата: (angles, error) и просто angles
        if isinstance(result, tuple) and len(result) == 2:
            angles, _ = result
        else:
            angles = result

        clamped = False
        for i in range(6):
            min_a, max_a = SAFE_ANGLE_LIMITS[i]
            if angles[i] < min_a or angles[i] > max_a:
                angles[i] = max(min_a, min(max_a, angles[i]))
                clamped = True

        result_pos = self._kin.get_end_effector_position(angles)
        error = math.sqrt(
            (result_pos[0] - x)**2 +
            (result_pos[1] - y)**2 +
            (result_pos[2] - z)**2
        )

        # Сохраняем начальные углы до обновления слайдеров — для построения пути
        start_angles = list(self.joint_angles)

        for i in range(6):
            self.slider_vars[i].set(round(angles[i], 1))
            self.joint_angles[i] = angles[i]
            self._update_pos_display(i)

        # Строим EE-траекторию интерполяцией в суставном пространстве
        if error < 15.0:
            self.ik_path = self._compute_ik_path(start_angles, angles, steps=40)
        else:
            self.ik_path = None

        clamp_note = "  (углы обрезаны!)" if clamped else ""
        path_note  = "  📍 путь построен" if self.ik_path else ""
        self.ik_status_var.set(
            f"✅ IK решена  |  ошибка: {error:.2f} мм{clamp_note}{path_note}"
        )
        self._draw_robot()
        self._update_info()
        return angles

    def _show_target(self) -> None:
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()
        self.target_point = (x, y, z)
        self.ik_target_reachable = False   # неизвестно — сбрасываем до явного решения IK
        self._draw_robot()
        self.ik_status_var.set(f"📌 Целевая точка: ({x:.0f},{y:.0f},{z:.0f}) мм")

    def _move_to_target(self) -> None:
        angles = self._solve_ik()
        if angles is None:
            return
        if not self.controller.connected:
            messagebox.showinfo(
                "IK решена",
                "Углы рассчитаны и установлены на слайдерах.\n"
                "Подключитесь к роботу для отправки команд.",
            )
            return
        self._apply_all()

    def _toggle_click_mode(self) -> None:
        self.click_mode = self.click_mode_var.get()
        if self.click_mode:
            self.ik_status_var.set("✏️ Кликните по 3D для выбора точки (Z = из поля)")
        else:
            self.ik_status_var.set("")

    def _on_3d_click(self, event) -> None:
        if not self.click_mode or event.inaxes != self.ax:
            return

        x2d, y2d = event.x, event.y
        target_z = self.target_z_var.get()
        max_r = self._kin.get_total_reach()

        best_point = None
        best_dist  = float('inf')
        grid_step  = max_r / 10

        for gx in np.arange(-max_r, max_r + grid_step, grid_step):
            for gy in np.arange(-max_r, max_r + grid_step, grid_step):
                x2, y2, _ = proj3d.proj_transform(gx, gy, target_z, self.ax.get_proj())
                try:
                    coords = self.ax.transData.transform((x2, y2))
                    sx, sy = coords[0], coords[1]
                except Exception:
                    continue
                d = math.sqrt((sx - x2d)**2 + (sy - y2d)**2)
                if d < best_dist:
                    best_dist  = d
                    best_point = (gx, gy, target_z)

        if best_point:
            # Уточнение мелкой сеткой
            cx, cy = best_point[0], best_point[1]
            fine   = grid_step / 10
            for gx in np.arange(cx - grid_step, cx + grid_step + fine, fine):
                for gy in np.arange(cy - grid_step, cy + grid_step + fine, fine):
                    x2, y2, _ = proj3d.proj_transform(gx, gy, target_z, self.ax.get_proj())
                    try:
                        coords = self.ax.transData.transform((x2, y2))
                        sx, sy = coords[0], coords[1]
                    except Exception:
                        continue
                    d = math.sqrt((sx - x2d)**2 + (sy - y2d)**2)
                    if d < best_dist:
                        best_dist  = d
                        best_point = (gx, gy, target_z)

            self.target_x_var.set(round(best_point[0], 1))
            self.target_y_var.set(round(best_point[1], 1))
            self.target_z_var.set(round(best_point[2], 1))
            self.target_point = best_point
            self.ik_status_var.set(
                f"✏️ Выбрана точка: ({best_point[0]:.1f},{best_point[1]:.1f},{best_point[2]:.1f}) мм"
            )

            # Решаем IK — если достижима, цель становится зелёной, двигаться не начинаем
            angles = self._solve_ik()
            self.ik_target_reachable = (angles is not None)
            self._draw_robot()

    # ──────────────────────────────────────────────────────────────────────
    # Presets
    # ──────────────────────────────────────────────────────────────────────

    def _refresh_preset_list(self) -> None:
        self.preset_listbox.delete(0, tk.END)
        for i, (x, y, z, name) in enumerate(self.preset_points):
            self.preset_listbox.insert(
                tk.END, f"#{i+1} {name}: ({x:.0f},{y:.0f},{z:.0f})"
            )

    def _on_preset_select(self, _event) -> None:
        sel = self.preset_listbox.curselection()
        if sel:
            x, y, z, name = self.preset_points[sel[0]]
            self.target_x_var.set(x)
            self.target_y_var.set(y)
            self.target_z_var.set(z)
            self.target_point = (x, y, z)
            self._draw_robot()
            self.ik_status_var.set(f"📌 {name}")

    def _save_preset(self) -> None:
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()
        result = self._ik.solve(x, y, z, max_iterations=200, tolerance=1.0)
        if result is None:
            messagebox.showwarning("IK не решена",
                                   f"Точка ({x:.0f},{y:.0f},{z:.0f}) не достижима!")
            return
        name = f"Точка #{len(self.preset_points)+1}"
        self.preset_points.append((x, y, z, name))
        self._refresh_preset_list()
        self.ik_status_var.set(f"✅ Сохранено: {name}")

    def _remove_preset(self) -> None:
        sel = self.preset_listbox.curselection()
        if sel:
            removed = self.preset_points.pop(sel[0])
            self._refresh_preset_list()
            self.ik_status_var.set(f"🗑️ Удалено: {removed[3]}")

    def _clear_presets(self) -> None:
        if messagebox.askyesno("Очистить", "Удалить все проверенные точки?"):
            self.preset_points.clear()
            self._refresh_preset_list()
            self.ik_status_var.set("")

    def _apply_preset(self) -> None:
        sel = self.preset_listbox.curselection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите точку из списка")
            return
        x, y, z, name = self.preset_points[sel[0]]
        self.target_x_var.set(x)
        self.target_y_var.set(y)
        self.target_z_var.set(z)
        self.target_point = (x, y, z)
        self._solve_ik()

    # ──────────────────────────────────────────────────────────────────────
    # Waypoints
    # ──────────────────────────────────────────────────────────────────────

    def _add_waypoint(self) -> None:
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()
        self.waypoints.append((x, y, z))
        n = len(self.waypoints)
        self.wp_listbox.insert(tk.END, f"#{n}: ({x:.1f},{y:.1f},{z:.1f}) мм")
        self._draw_robot()
        self.ik_status_var.set(f"📌 Точка #{n} добавлена")

    def _remove_waypoint(self) -> None:
        sel = self.wp_listbox.curselection()
        if not sel:
            messagebox.showwarning("Выбор", "Выберите точку для удаления")
            return
        self.waypoints.pop(sel[0])
        self._refresh_waypoint_list()
        self._draw_robot()

    def _clear_waypoints(self) -> None:
        self.waypoints.clear()
        self.wp_listbox.delete(0, tk.END)
        self._draw_robot()
        self.ik_status_var.set("🗑️ Маршрут очищен")

    def _refresh_waypoint_list(self) -> None:
        self.wp_listbox.delete(0, tk.END)
        for i, (x, y, z) in enumerate(self.waypoints):
            self.wp_listbox.insert(tk.END, f"#{i+1}: ({x:.1f},{y:.1f},{z:.1f}) мм")

    def _on_wp_double_click(self, _event) -> None:
        sel = self.wp_listbox.curselection()
        if sel:
            x, y, z = self.waypoints[sel[0]]
            self.target_x_var.set(x)
            self.target_y_var.set(y)
            self.target_z_var.set(z)
            self.target_point = (x, y, z)
            self._draw_robot()

    def _go_to_selected_wp(self) -> None:
        sel = self.wp_listbox.curselection()
        if not sel:
            messagebox.showwarning("Выбор", "Выберите точку из списка!")
            return
        x, y, z = self.waypoints[sel[0]]
        self.target_x_var.set(x)
        self.target_y_var.set(y)
        self.target_z_var.set(z)
        self._move_to_target()

    def _run_waypoints(self) -> None:
        if not self.waypoints:
            messagebox.showwarning("Маршрут пуст", "Добавьте точки в маршрут!")
            return
        lines = "\n".join(
            f"  #{i+1}: ({x:.0f},{y:.0f},{z:.0f}) мм"
            for i, (x, y, z) in enumerate(self.waypoints)
        )
        if not messagebox.askyesno(
            "Обход маршрута",
            f"Последовательно двигать к {len(self.waypoints)} точкам?\n\n{lines}\n\n"
            "⚠️ Убедитесь что путь свободен!",
        ):
            return
        self._wp_running = True
        t = threading.Thread(target=self._run_waypoints_thread, daemon=True)
        t.start()

    def _run_waypoints_thread(self) -> None:
        total = len(self.waypoints)
        for i, (x, y, z) in enumerate(self.waypoints):
            if not self._wp_running:
                break
            self.after(0, lambda ix=i, lx=x, ly=y, lz=z:
                self._waypoint_step_ui(ix, lx, ly, lz, total))

            result = self._ik.solve(x, y, z, max_iterations=300, tolerance=1.0)
            if result is None:
                self.after(0, lambda ix=i: self._info_append(
                    f"❌ IK не решена для точки #{ix+1}\n", "err"))
                continue

            if isinstance(result, tuple) and len(result) == 2:
                angles, _ = result
            else:
                angles = result

            for j in range(6):
                mn, mx = SAFE_ANGLE_LIMITS[j]
                angles[j] = max(mn, min(mx, angles[j]))

            self.after(0, lambda a=angles[:]: self._update_sliders_from_angles(a))

            if self.controller.connected:
                for j in range(6):
                    motor_id = self._get_motor_id(j)
                    pos = self._angle_to_position(angles[j], j)
                    try:
                        self.controller.move_motor(motor_id, pos)
                    except Exception as e:
                        self.after(0, lambda ix=i, err=str(e): self._info_append(
                            f"❌ #{ix+1} J{j+1}: {err}\n", "err"))
                time.sleep(2.0)

            self.after(0, lambda ix=i: self._info_append(
                f"✅ Точка #{ix+1} достигнута\n", "ok"))

        self._wp_running = False
        self.after(0, lambda: self.ik_status_var.set(
            f"✅ Обход завершён ({total} точек)"))

    def _waypoint_step_ui(self, idx: int, x, y, z, total: int) -> None:
        self.target_x_var.set(x)
        self.target_y_var.set(y)
        self.target_z_var.set(z)
        self.ik_status_var.set(f"▶️ Точка {idx+1}/{total}: ({x:.0f},{y:.0f},{z:.0f}) мм")
        self.wp_listbox.selection_clear(0, tk.END)
        self.wp_listbox.selection_set(idx)
        self.wp_listbox.see(idx)

    def _update_sliders_from_angles(self, angles: List[float]) -> None:
        for i in range(6):
            self.slider_vars[i].set(round(angles[i], 1))
            self.joint_angles[i] = angles[i]
            self._update_pos_display(i)
        self._draw_robot()
        self._update_info()

    def _info_append(self, text: str, tag: str = "") -> None:
        self.info_text.insert(tk.END, text, tag)
        self.info_text.see(tk.END)

    # ──────────────────────────────────────────────────────────────────────
    # Action bar handlers
    # ──────────────────────────────────────────────────────────────────────

    def _update_viz(self) -> None:
        for i in range(6):
            try:
                self.joint_angles[i] = self.slider_vars[i].get()
            except Exception:
                pass
        self._draw_robot()

    def _reset_angles(self) -> None:
        for i in range(6):
            self.slider_vars[i].set(0.0)
            self.joint_angles[i] = 0.0
            self._update_pos_display(i)
        self._draw_robot()
        self.log("Углы сброшены в 0°", "info")

    def _apply_all(self, confirm: bool = True) -> None:
        if not self.controller.connected:
            messagebox.showwarning("Нет подключения", "Сначала подключитесь к роботу!")
            return
        if confirm and not messagebox.askyesno("Подтверждение", "Применить все углы к реальному роботу?"):
            return
        for i in range(6):
            motor_id = self._get_motor_id(i)
            pos = self._angle_to_position(self.joint_angles[i], i)
            self.controller.move_motor(motor_id, pos)
        self.log("Все углы применены к роботу", "success")

    def _emergency_stop(self) -> None:
        self._wp_running = False
        if self.controller.connected:
            self.controller.emergency_stop_all()
        self.log("🛑 ЭКСТРЕННАЯ ОСТАНОВКА", "error")

    def _reset_camera(self) -> None:
        if self.ax:
            self.ax.view_init(elev=25, azim=45)
            self.canvas.draw()

    # ──────────────────────────────────────────────────────────────────────
    # 3D drawing
    # ──────────────────────────────────────────────────────────────────────

    def _compute_ik_path(
        self,
        start: List[float],
        end: List[float],
        steps: int = 40,
    ) -> List[Tuple[float, float, float]]:
        """Линейная интерполяция в суставном пространстве → список EE-позиций."""
        path = []
        for k in range(steps + 1):
            t = k / steps
            interp = [start[j] + (end[j] - start[j]) * t for j in range(6)]
            pos = self._kin.get_end_effector_position(interp)
            path.append(tuple(pos))
        return path

    def _draw_robot(self) -> None:
        if not self.ax or not self.figure or not self.canvas:
            return

        self.ax.clear()
        self.ax.set_facecolor(PLOT_AX)
        self.figure.set_facecolor(PLOT_BG)

        joint_pos = self._kin.get_all_joint_positions(self.joint_angles)
        xs = [p[0] for p in joint_pos]
        ys = [p[1] for p in joint_pos]
        zs = [p[2] for p in joint_pos]

        max_r = self._kin.get_total_reach()
        self.ax.set_xlim(-max_r, max_r)
        self.ax.set_ylim(-max_r, max_r)
        self.ax.set_zlim(-max_r * 0.3, max_r + 50)
        self.ax.set_xlabel("X (мм)", color=LIGHT_TEXT2)
        self.ax.set_ylabel("Y (мм)", color=LIGHT_TEXT2)
        self.ax.set_zlabel("Z (мм)", color=LIGHT_TEXT2)
        self.ax.set_title("Кинематика робота", color=LIGHT_TEXT, fontsize=10)

        # Оси — светлый стиль
        for pane in (self.ax.xaxis.pane, self.ax.yaxis.pane, self.ax.zaxis.pane):
            pane.fill = False
            pane.set_edgecolor(LIGHT_BORDER)
        self.ax.tick_params(colors=LIGHT_TEXT2, labelsize=7)

        # Линия-рабочий объём (полусфера)
        theta = np.linspace(0, np.pi, 30)
        phi   = np.linspace(0, 2 * np.pi, 30)
        t, p  = np.meshgrid(theta, phi)
        wx = max_r * np.sin(t) * np.cos(p)
        wy = max_r * np.sin(t) * np.sin(p)
        wz = max_r * np.cos(t)
        self.ax.plot_surface(wx, wy, wz, alpha=0.04, color=LIGHT_BLUE, linewidth=0)

        # Звенья робота
        self.ax.plot(xs, ys, zs,
                     color=LINK_COL, linewidth=3, zorder=5)

        # Суставы
        for i, (x, y, z) in enumerate(zip(xs, ys, zs)):
            self.ax.scatter([x], [y], [z],
                            color=KINEMA_COLORS[i % len(KINEMA_COLORS)],
                            s=80, zorder=6)
            name = 'База' if i == 0 else f"J{i}"
            self.ax.text(x, y, z + 8, name,
                         color=LIGHT_TEXT2, fontsize=7)

        # Конечный эффектор
        ee = self._kin.get_end_effector_position(self.joint_angles)
        self.ax.scatter([ee[0]], [ee[1]], [ee[2]],
                        color=EE_COL, s=120, marker='*', zorder=7)
        self.ax.text(ee[0], ee[1], ee[2] + 10,
                     f"EE ({ee[0]:.0f},{ee[1]:.0f},{ee[2]:.0f})",
                     color=EE_COL, fontsize=8)

        # Целевая точка
        if self.target_point:
            tx, ty, tz = self.target_point
            # Зелёный — IK решена, оранжевый — недостижимо
            tgt_color = LIGHT_GREEN if self.ik_target_reachable else TGT_COL
            self.ax.scatter([tx], [ty], [tz],
                            color=tgt_color, s=160, marker='X', zorder=7)
            self.ax.text(tx, ty, tz + 10,
                         f"{'✅' if self.ik_target_reachable else '❌'} "
                         f"({tx:.0f},{ty:.0f},{tz:.0f})",
                         color=tgt_color, fontsize=8, fontweight='bold')
            # Линия от EE до цели
            self.ax.plot([ee[0], tx], [ee[1], ty], [ee[2], tz],
                         color=tgt_color, linewidth=1, linestyle='--', alpha=0.5)

        # Waypoints
        if self.waypoints:
            wx_arr = [p[0] for p in self.waypoints]
            wy_arr = [p[1] for p in self.waypoints]
            wz_arr = [p[2] for p in self.waypoints]
            self.ax.scatter(wx_arr, wy_arr, wz_arr,
                            color=WP_COL, s=60, marker='D', alpha=0.7, zorder=6)
            self.ax.plot(wx_arr, wy_arr, wz_arr,
                         color=WP_COL, linewidth=1, linestyle=':', alpha=0.5)
            for i, (px, py, pz) in enumerate(self.waypoints):
                self.ax.text(px, py, pz + 8, f"#{i+1}",
                             color=WP_COL, fontsize=7)

        # IK-путь (рисуется только если ошибка была < 15 мм)
        if self.ik_path and len(self.ik_path) >= 2:
            px = [p[0] for p in self.ik_path]
            py = [p[1] for p in self.ik_path]
            pz = [p[2] for p in self.ik_path]
            # Градиент: от синего (старт) к зелёному (цель) через промежуточные точки
            n = len(self.ik_path)
            for k in range(n - 1):
                t = k / (n - 1)
                r = 0.0
                g = t
                b = 1.0 - t
                self.ax.plot(
                    [px[k], px[k+1]],
                    [py[k], py[k+1]],
                    [pz[k], pz[k+1]],
                    color=(r, g, b), linewidth=2, alpha=0.75, zorder=4,
                )
            # Маркеры начала и конца пути
            self.ax.scatter([px[0]],  [py[0]],  [pz[0]],
                            color='#0078d7', s=60, marker='o', zorder=8, label='старт пути')
            self.ax.scatter([px[-1]], [py[-1]], [pz[-1]],
                            color='#1a7f37', s=80, marker='*', zorder=8, label='конец пути')

        self.figure.tight_layout(pad=1.0)
        self.canvas.draw()

    # ──────────────────────────────────────────────────────────────────────
    # Info text update
    # ──────────────────────────────────────────────────────────────────────

    def _update_info(self) -> None:
        ee = self._kin.get_end_effector_position(self.joint_angles)
        lines = [
            ("══ Текущее положение ══\n", "head"),
        ]
        for i, angle in enumerate(self.joint_angles):
            pos = int((angle + 180.0) / 360.0 * MAX_POSITION)
            lines.append((f"  J{i+1}: {angle:+7.1f}°  pos={pos}\n", ""))
        lines += [
            ("\n══ Конечный эффектор ══\n", "head"),
            (f"  X: {ee[0]:7.1f} мм\n", ""),
            (f"  Y: {ee[1]:7.1f} мм\n", ""),
            (f"  Z: {ee[2]:7.1f} мм\n", ""),
        ]
        if self.target_point:
            tx, ty, tz = self.target_point
            err = math.sqrt((ee[0]-tx)**2 + (ee[1]-ty)**2 + (ee[2]-tz)**2)
            lines += [
                ("\n══ Целевая точка ══\n", "head"),
                (f"  X: {tx:7.1f}  Y: {ty:7.1f}  Z: {tz:7.1f}\n", ""),
                (f"  Ошибка: {err:.2f} мм\n",
                 "ok" if err < 5 else "warn" if err < 20 else "err"),
            ]
        self.info_text.delete("1.0", tk.END)
        for text, tag in lines:
            self.info_text.insert(tk.END, text, tag)

    # ──────────────────────────────────────────────────────────────────────
    # External API (called from main_window.py)
    # ──────────────────────────────────────────────────────────────────────

    @property
    def kinematics(self) -> RobotKinematics6DOF:
        """Публичный алиас для совместимости с main_window.py."""
        return self._kin

    def _on_live_toggle(self) -> None:
        self._live_mode = self._live_toggle_var.get()
        if not self._live_mode:
            self._live_var.set("⚫ live")
            self._live_label.configure(foreground=LIGHT_TEXT2)

    def _go_home(self) -> None:
        """Сброс всех суставов в 0° — на визуализации и на роботе если подключён."""
        for i in range(6):
            self.slider_vars[i].set(0.0)
            self.joint_angles[i] = 0.0
            self._update_pos_display(i)
        self.ik_path = None
        self._draw_robot()
        self.log("🏠 Сброс в нулевые позиции", "info")

        if self.controller.connected:
            if messagebox.askyesno("В ноль", "Отправить команду HOME на все моторы?"):
                for i in range(6):
                    motor_id = self._get_motor_id(i)
                    # Позиция 0° = 2048
                    home_pos = MAX_POSITION // 2
                    if self._is_inverted(i):
                        home_pos = MAX_POSITION - home_pos
                    self.controller.move_motor(motor_id, home_pos)
                self.log("🏠 HOME отправлен на все моторы", "success")

    def _schedule_draw(self) -> None:
        """Планирует одну перерисовку через 50 мс (троттлинг)."""
        if not self._pending_draw:
            self._pending_draw = True
            self.after(50, self._deferred_draw)

    def _deferred_draw(self) -> None:
        self._pending_draw = False
        self._draw_robot()

    def update_from_monitor(self, motor_data_dict: Dict) -> None:
        """Обновить углы из реальных позиций моторов и перерисовать 3D."""
        if not self._live_mode:
            return

        updated = False
        for joint_idx in range(6):
            motor_id = self._get_motor_id(joint_idx)
            if motor_id not in motor_data_dict:
                continue
            data = motor_data_dict[motor_id]
            if data.position is None:
                continue

            raw_pos = data.position
            # Снимаем инверсию: если мотор стоит зеркально — отражаем позицию назад
            real_pos = (MAX_POSITION - raw_pos) if self._is_inverted(joint_idx) else raw_pos
            angle = (real_pos / MAX_POSITION) * 360.0 - 180.0
            angle = round(angle, 1)

            if abs(self.joint_angles[joint_idx] - angle) > 0.2:   # порог 0.2° чтобы не мигать
                self.slider_vars[joint_idx].set(angle)
                self.joint_angles[joint_idx] = angle
                self._update_pos_display(joint_idx)
                updated = True

        if updated:
            # Зелёный пульс на индикаторе live
            self._live_var.set("🟢 live")
            self._live_label.configure(foreground=LIGHT_GREEN)
            self.after(400, lambda: (
                self._live_var.set("⚫ live"),
                self._live_label.configure(foreground=LIGHT_TEXT2),
            ))
            self._schedule_draw()
            self._update_info()
