#!/usr/bin/env python3

"""
Kinematics 3D Panel — полная визуализация с IK, слайдерами, пресетами и маршрутами.

Переработано в минималистичном ч/б стиле:
  - 6 слайдеров с безопасными диапазонами углов
  - Ввод целевой точки XYZ → обратная кинематика
  - Клик по 3D для выбора точки
  - Пресеты проверенных точек
  - Маршрутные точки (Waypoints) с последовательным обходом
  - Минималистичная ч/б тема
"""

import math
import threading
import time
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

import matplotlib
import numpy as np

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import proj3d

from app.config.constants import (
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    FANUC_TEXT2,
    KINEMA_COLORS,
    MAX_POSITION,
)
from app.controllers.motor_controller import MotorController
from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF

# ── Безопасные диапазоны углов (°) ────────────────────────────────────────
SAFE_ANGLE_LIMITS: list[tuple[float, float]] = [
    (-180, 180),  # J1 база      — полные 360°
    (-180, 180),  # J2 плечо 1   — полные 360°
    (-180, 180),  # J3 плечо 2   — полные 360°
    (-180, 180),  # J4 локоть    — полные 360°
    (-180, 180),  # J5 кисть 1   — полные 360°
    (-180, 180),  # J6 кисть 2   — полные 360°
]

JOINT_NAMES = [
    "База (J1)",
    "Плечо 1 (J2)",
    "Плечо 2 (J3)",
    "Локоть (J4)",
    "Кисть 1 (J5)",
    "Кисть 2 (J6)",
]

# Цвета 3D-графика (минималистичная ч/б)
PLOT_BG = FANUC_BG
PLOT_AX = FANUC_PANEL
LINK_COL = FANUC_GREEN  # белый — звенья
EE_COL = FANUC_GREEN  # белый — конечный эффектор
TGT_COL = FANUC_BLUE  # светло-серый — целевая точка
WP_COL = FANUC_GRAY  # серый — waypoints


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
        self._ik = InverseKinematics6DOF(self._kin)

        # Состояние суставов
        self.joint_angles: list[float] = [0.0] * 6
        self.slider_vars: list[tk.DoubleVar] = []
        self.position_vars: list[tk.StringVar] = []

        # Целевая точка и маршруты
        self.target_point: tuple[float, float, float] | None = None
        self.waypoints: list[tuple[float, float, float]] = []
        self.preset_points: list[tuple[float, float, float, str]] = [
            (100, 0, 150, "Центр передняя"),
            (150, 0, 100, "Дальняя низ"),
            (80, 50, 120, "Средняя левая"),
            (80, -50, 120, "Средняя правая"),
            (120, 0, 180, "Верхняя точка"),
        ]
        self.click_mode = False
        self._wp_running = False
        self.ik_target_reachable: bool = False
        self._pending_draw: bool = False
        self._live_mode: bool = True

        # Траектория EE от текущей позиции до IK-цели
        self.ik_path: list[tuple[float, float, float]] | None = None

        # matplotlib
        self.figure: plt.Figure | None = None
        self.ax = None
        self.canvas: FigureCanvasTkAgg | None = None

        self._build_ui()
        self._refresh_preset_list()
        self._draw_robot()

    # ──────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.configure(style="Dark.TFrame")

        # ── Sliders row (top) ──────────────────────────────────────────
        sliders_lf = ttk.LabelFrame(
            self,
            text="Углы суставов",
            padding=6,
            style="Dark.TLabelframe",
        )
        sliders_lf.pack(fill="x", padx=8, pady=(6, 2))
        self._build_sliders(sliders_lf)

        # ── Middle: 3D plot + info ─────────────────────────────────────
        mid = ttk.Frame(self, style="Dark.TFrame")
        mid.pack(fill="both", expand=True, padx=8, pady=2)
        self._build_3d(mid)
        self._build_info(mid)

        # ── Bottom panels: target / presets / waypoints ────────────────
        bot = ttk.Frame(self, style="Dark.TFrame")
        bot.pack(fill="x", padx=8, pady=(2, 6))
        self._build_target_panel(bot)
        self._build_presets_panel(bot)
        self._build_waypoints_panel(bot)

        # ── Action buttons (bottom strip) ──────────────────────────────
        self._build_action_bar()

    # ── Sliders ───────────────────────────────────────────────────────────

    def _build_sliders(self, parent: ttk.Frame) -> None:
        for i in range(6):
            row = ttk.Frame(parent, style="Dark.TFrame")
            row.pack(fill="x", pady=1)

            min_a, max_a = SAFE_ANGLE_LIMITS[i]

            ttk.Label(
                row,
                text=JOINT_NAMES[i],
                width=18,
                font=("SF Pro", 10, "bold"),
                foreground=FANUC_GREEN,
                background=FANUC_PANEL,
            ).pack(side="left", padx=(0, 4))

            ttk.Label(
                row,
                text=f"[{min_a}..{max_a}]",
                width=12,
                foreground=FANUC_ORANGE,
                font=("SF Mono", 8),
                background=FANUC_PANEL,
            ).pack(side="left", padx=2)

            var = tk.DoubleVar(value=0.0)
            self.slider_vars.append(var)

            slider = ttk.Scale(
                row,
                from_=min_a,
                to=max_a,
                variable=var,
                orient="horizontal",
                length=300,
                command=lambda v, idx=i: self._on_slider(idx),
                style="Dark.Horizontal.TScale",
            )
            slider.pack(side="left", padx=6)

            spinbox = ttk.Spinbox(
                row,
                from_=min_a,
                to=max_a,
                textvariable=var,
                width=6,
                command=lambda idx=i: self._on_entry(idx),
                font=("SF Mono", 9),
            )
            spinbox.pack(side="left", padx=2)
            spinbox.bind("<Return>", lambda e, idx=i: self._on_entry(idx))

            pos_var = tk.StringVar(value="POS: 2048")
            self.position_vars.append(pos_var)

            ttk.Label(
                row,
                textvariable=pos_var,
                width=12,
                foreground=FANUC_BLUE,
                font=("SF Mono", 9),
                background=FANUC_PANEL,
            ).pack(side="left", padx=6)

            ttk.Button(
                row,
                text=">",
                width=2,
                command=lambda idx=i: self._send_joint(idx),
                style="Accent.TButton",
            ).pack(side="left", padx=2)

    # ── 3D plot ───────────────────────────────────────────────────────────

    def _build_3d(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(
            parent,
            text="3D Визуализация",
            padding=4,
            style="Dark.TLabelframe",
        )
        lf.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.figure = plt.figure(figsize=(7, 5), dpi=96, facecolor=PLOT_BG)
        self.ax = self.figure.add_subplot(111, projection="3d")
        self.ax.set_facecolor(PLOT_AX)

        self.canvas = FigureCanvasTkAgg(self.figure, master=lf)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect("button_press_event", self._on_3d_click)

        cam_bar = ttk.Frame(lf, style="Dark.TFrame")
        cam_bar.pack(fill="x", pady=3)

        ttk.Button(
            cam_bar,
            text="Reset",
            command=self._reset_camera,
            style="Dark.TButton",
        ).pack(side="left", padx=4)

        ttk.Button(
            cam_bar,
            text="Home",
            command=self._go_home,
            style="Dark.TButton",
        ).pack(side="left", padx=4)

        # Live-индикатор
        self._live_var = tk.StringVar(value="LIVE")
        self._live_label = ttk.Label(
            cam_bar,
            textvariable=self._live_var,
            foreground=FANUC_GREEN,
            font=("SF Mono", 8, "bold"),
            background=FANUC_PANEL,
        )
        self._live_label.pack(side="left", padx=8)

        self._live_toggle_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            cam_bar,
            text="track motors",
            variable=self._live_toggle_var,
            command=self._on_live_toggle,
            style="Dark.TCheckbutton",
        ).pack(side="left", padx=2)

        ttk.Label(
            cam_bar,
            text="LMB: rotate | Wheel: zoom",
            foreground=FANUC_RED,
            font=("SF Pro", 8),
            background=FANUC_PANEL,
        ).pack(side="right", padx=8)

    # ── Info panel ────────────────────────────────────────────────────────

    def _build_info(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(
            parent,
            text="Coordinates",
            padding=4,
            style="Dark.TLabelframe",
        )
        lf.pack(side="right", fill="y", padx=(4, 0))

        self.info_text = tk.Text(
            lf,
            width=32,
            height=18,
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
            font=("SF Mono", 9),
            relief="flat",
            bd=1,
            insertbackground=FANUC_GREEN,
        )
        self.info_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        sb = ttk.Scrollbar(lf, orient="vertical", command=self.info_text.yview)
        sb.pack(side="right", fill="y")
        self.info_text.configure(yscrollcommand=sb.set)

        # Color tags
        self.info_text.tag_configure("ok", foreground=FANUC_GREEN)
        self.info_text.tag_configure("err", foreground=FANUC_RED)
        self.info_text.tag_configure("warn", foreground=FANUC_ORANGE)
        self.info_text.tag_configure("head", foreground=FANUC_GREEN, font=("SF Mono", 9, "bold"))

    # ── Target panel ──────────────────────────────────────────────────────

    def _build_target_panel(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(
            parent,
            text="Target Point (mm)",
            padding=4,
            style="Dark.TLabelframe",
        )
        lf.pack(side="left", fill="both", expand=True, padx=(0, 4))

        xyz_row = ttk.Frame(lf, style="Dark.TFrame")
        xyz_row.pack(fill="x", pady=2)

        for label, attr, default, color in [
            ("X:", "target_x_var", 100.0, FANUC_GREEN),
            ("Y:", "target_y_var", 0.0, FANUC_BLUE),
            ("Z:", "target_z_var", 150.0, FANUC_ORANGE),
        ]:
            ttk.Label(
                xyz_row,
                text=label,
                foreground=color,
                font=("SF Pro", 10, "bold"),
                background=FANUC_PANEL,
            ).pack(side="left", padx=(8, 1))
            var = tk.DoubleVar(value=default)
            setattr(self, attr, var)
            ttk.Spinbox(
                xyz_row,
                from_=-400,
                to=400,
                textvariable=var,
                width=6,
                increment=5.0,
                font=("SF Mono", 9),
            ).pack(side="left", padx=1)

        btn_row = ttk.Frame(lf, style="Dark.TFrame")
        btn_row.pack(fill="x", pady=2)
        ttk.Button(
            btn_row,
            text="Solve IK",
            command=self._solve_ik,
            style="Dark.TButton",
        ).pack(side="left", padx=2)
        ttk.Button(
            btn_row,
            text="Move",
            command=self._move_to_target,
            style="Accent.TButton",
        ).pack(side="left", padx=2)
        ttk.Button(
            btn_row,
            text="Show",
            command=self._show_target,
            style="Dark.TButton",
        ).pack(side="left", padx=2)

        click_row = ttk.Frame(lf, style="Dark.TFrame")
        click_row.pack(fill="x", pady=1)
        self.click_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            click_row,
            text="Click on 3D to select",
            variable=self.click_mode_var,
            command=self._toggle_click_mode,
            style="Dark.TCheckbutton",
        ).pack(side="left", padx=2)

        self.ik_status_var = tk.StringVar(value="")
        ttk.Label(
            lf,
            textvariable=self.ik_status_var,
            foreground=FANUC_GREEN,
            wraplength=340,
            font=("SF Pro", 9),
            background=FANUC_PANEL,
        ).pack(fill="x", pady=2)

    # ── Presets ───────────────────────────────────────────────────────────

    def _build_presets_panel(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(
            parent,
            text="Presets",
            padding=4,
            style="Dark.TLabelframe",
        )
        lf.pack(side="left", fill="both", expand=True, padx=(0, 4))

        listbox_frame = ttk.Frame(lf, style="Dark.TFrame")
        listbox_frame.pack(fill="both", expand=True)

        self.preset_listbox = tk.Listbox(
            listbox_frame,
            height=5,
            width=30,
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
            selectbackground=FANUC_GREEN,
            selectforeground=FANUC_BG,
            font=("SF Mono", 9),
            relief="flat",
            bd=1,
            highlightthickness=0,
        )
        self.preset_listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.preset_listbox.yview)
        sb.pack(side="right", fill="y")
        self.preset_listbox.configure(yscrollcommand=sb.set)
        self.preset_listbox.bind("<<ListboxSelect>>", self._on_preset_select)

        btn_row = ttk.Frame(lf, style="Dark.TFrame")
        btn_row.pack(fill="x", pady=2)
        ttk.Button(
            btn_row, text="+", width=2, command=self._save_preset, style="Dark.TButton"
        ).pack(side="left", padx=1)
        ttk.Button(
            btn_row,
            text="-",
            width=2,
            command=self._remove_preset,
            style="Dark.TButton",
        ).pack(side="left", padx=1)
        ttk.Button(
            btn_row,
            text="Clear",
            width=5,
            command=self._clear_presets,
            style="Dark.TButton",
        ).pack(side="left", padx=1)
        ttk.Button(
            btn_row,
            text="Apply",
            command=self._apply_preset,
            style="Accent.TButton",
        ).pack(side="left", padx=4)

    # ── Waypoints ─────────────────────────────────────────────────────────

    def _build_waypoints_panel(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(
            parent,
            text="Waypoints",
            padding=4,
            style="Dark.TLabelframe",
        )
        lf.pack(side="left", fill="both", expand=True)

        listbox_frame = ttk.Frame(lf, style="Dark.TFrame")
        listbox_frame.pack(fill="both", expand=True)

        self.wp_listbox = tk.Listbox(
            listbox_frame,
            height=5,
            width=34,
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
            selectbackground=FANUC_GREEN,
            selectforeground=FANUC_BG,
            font=("SF Mono", 9),
            relief="flat",
            bd=1,
            highlightthickness=0,
        )
        self.wp_listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.wp_listbox.yview)
        sb.pack(side="right", fill="y")
        self.wp_listbox.configure(yscrollcommand=sb.set)
        self.wp_listbox.bind("<Double-1>", self._on_wp_double_click)

        btn_row = ttk.Frame(lf, style="Dark.TFrame")
        btn_row.pack(fill="x", pady=2)
        ttk.Button(
            btn_row, text="+", width=2, command=self._add_waypoint, style="Dark.TButton"
        ).pack(side="left", padx=1)
        ttk.Button(
            btn_row,
            text="-",
            width=2,
            command=self._remove_waypoint,
            style="Dark.TButton",
        ).pack(side="left", padx=1)
        ttk.Button(
            btn_row,
            text="Clear",
            width=5,
            command=self._clear_waypoints,
            style="Dark.TButton",
        ).pack(side="left", padx=1)
        ttk.Button(
            btn_row,
            text="Run All",
            command=self._run_waypoints,
            style="Accent.TButton",
        ).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Go", command=self._go_to_selected_wp, style="Dark.TButton").pack(
            side="left", padx=1
        )

    # ── Action bar ───────────────────────────────────────────────────────

    def _build_action_bar(self) -> None:
        bar = ttk.Frame(self, style="Dark.TFrame")
        bar.pack(fill="x", padx=8, pady=(0, 6))

        ttk.Button(bar, text="Refresh", command=self._update_viz, style="Dark.TButton").pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Reset", command=self._reset_angles, style="Dark.TButton").pack(
            side="left", padx=4
        )
        ttk.Button(
            bar,
            text="Apply All",
            command=self._apply_all,
            style="Accent.TButton",
        ).pack(side="left", padx=4)
        ttk.Button(bar, text="STOP", command=self._emergency_stop, style="Danger.TButton").pack(
            side="right", padx=4
        )

    # ──────────────────────────────────────────────────────────────────────
    # Slider / entry handlers
    # ──────────────────────────────────────────────────────────────────────

    def _on_slider(self, idx: int) -> None:
        angle = self.slider_vars[idx].get()
        self.joint_angles[idx] = angle
        self._update_pos_display(idx)
        self.ik_path = None
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
        key = f"joint_{joint_idx}"
        return self.controller.motor_mapping.get(key, {}).get("motor_id", joint_idx + 1)

    def _is_inverted(self, joint_idx: int) -> bool:
        key = f"joint_{joint_idx}"
        return self.controller.motor_mapping.get(key, {}).get("inverted", False)

    def _angle_to_position(self, angle: float, joint_idx: int) -> int:
        pos = int((angle + 180.0) / 360.0 * MAX_POSITION)
        pos = max(0, min(MAX_POSITION, pos))
        if self._is_inverted(joint_idx):
            pos = MAX_POSITION - pos
        return pos

    def _send_joint(self, idx: int) -> None:
        if not self.controller.connected:
            messagebox.showwarning("No Connection", "Connect to robot first!")
            return
        motor_id = self._get_motor_id(idx)
        pos = self._angle_to_position(self.joint_angles[idx], idx)
        inv_note = " (inv.)" if self._is_inverted(idx) else ""
        if messagebox.askyesno(
            "Confirm",
            f"Move {JOINT_NAMES[idx]}{inv_note}?\n"
            f"Angle: {self.joint_angles[idx]:.1f}  ->  pos: {pos}",
        ):
            self.controller.move_motor(motor_id, pos)
            self.log(f"J{idx + 1} -> {self.joint_angles[idx]:.1f} (pos={pos})", "info")

    # ──────────────────────────────────────────────────────────────────────
    # IK & target
    # ──────────────────────────────────────────────────────────────────────

    def _solve_ik(self) -> list[float] | None:
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()
        self.target_point = (x, y, z)

        dist = math.sqrt(x**2 + y**2 + z**2)
        max_r = self._kin.get_total_reach()
        if dist > max_r:
            self.ik_status_var.set(
                f"OUT OF REACH: ({x:.0f},{y:.0f},{z:.0f}) D={dist:.0f} > {max_r:.0f}"
            )
            self._draw_robot()
            return None

        self.ik_status_var.set("Solving IK...")
        self.update_idletasks()

        result = self._ik.solve(x, y, z, max_iterations=300, tolerance=1.0)
        if result is None:
            self.ik_status_var.set(f"IK FAILED for ({x:.0f},{y:.0f},{z:.0f})")
            self._draw_robot()
            return None

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
            (result_pos[0] - x) ** 2 + (result_pos[1] - y) ** 2 + (result_pos[2] - z) ** 2
        )

        start_angles = list(self.joint_angles)

        for i in range(6):
            self.slider_vars[i].set(round(angles[i], 1))
            self.joint_angles[i] = angles[i]
            self._update_pos_display(i)

        if error < 15.0:
            self.ik_path = self._compute_ik_path(start_angles, angles, steps=40)
        else:
            self.ik_path = None

        clamp_note = " (clamped)" if clamped else ""
        path_note = " [path]" if self.ik_path else ""
        self.ik_status_var.set(f"IK OK | error: {error:.2f}mm{clamp_note}{path_note}")
        self._draw_robot()
        self._update_info()
        return angles

    def _show_target(self) -> None:
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()
        self.target_point = (x, y, z)
        self.ik_target_reachable = False
        self._draw_robot()
        self.ik_status_var.set(f"Target: ({x:.0f},{y:.0f},{z:.0f})")

    def _move_to_target(self) -> None:
        angles = self._solve_ik()
        if angles is None:
            return
        if not self.controller.connected:
            messagebox.showinfo(
                "IK Solved",
                "Angles calculated.\nConnect to robot to send commands.",
            )
            return
        self._apply_all()

    def _toggle_click_mode(self) -> None:
        self.click_mode = self.click_mode_var.get()
        if self.click_mode:
            self.ik_status_var.set("Click on 3D to select point (Z from field)")
        else:
            self.ik_status_var.set("")

    def _on_3d_click(self, event) -> None:
        if not self.click_mode or event.inaxes != self.ax:
            return

        x2d, y2d = event.x, event.y
        target_z = self.target_z_var.get()
        max_r = self._kin.get_total_reach()

        best_point = None
        best_dist = float("inf")
        grid_step = max_r / 10

        for gx in np.arange(-max_r, max_r + grid_step, grid_step):
            for gy in np.arange(-max_r, max_r + grid_step, grid_step):
                x2, y2, _ = proj3d.proj_transform(gx, gy, target_z, self.ax.get_proj())
                try:
                    coords = self.ax.transData.transform((x2, y2))
                    sx, sy = coords[0], coords[1]
                except Exception:
                    continue
                d = math.sqrt((sx - x2d) ** 2 + (sy - y2d) ** 2)
                if d < best_dist:
                    best_dist = d
                    best_point = (gx, gy, target_z)

        if best_point:
            cx, cy = best_point[0], best_point[1]
            fine = grid_step / 10
            for gx in np.arange(cx - grid_step, cx + grid_step + fine, fine):
                for gy in np.arange(cy - grid_step, cy + grid_step + fine, fine):
                    x2, y2, _ = proj3d.proj_transform(gx, gy, target_z, self.ax.get_proj())
                    try:
                        coords = self.ax.transData.transform((x2, y2))
                        sx, sy = coords[0], coords[1]
                    except Exception:
                        continue
                    d = math.sqrt((sx - x2d) ** 2 + (sy - y2d) ** 2)
                    if d < best_dist:
                        best_dist = d
                        best_point = (gx, gy, target_z)

            self.target_x_var.set(round(best_point[0], 1))
            self.target_y_var.set(round(best_point[1], 1))
            self.target_z_var.set(round(best_point[2], 1))
            self.target_point = best_point
            self.ik_status_var.set(
                f"Selected: ({best_point[0]:.1f},{best_point[1]:.1f},{best_point[2]:.1f})"
            )

            angles = self._solve_ik()
            self.ik_target_reachable = angles is not None
            self._draw_robot()

    # ──────────────────────────────────────────────────────────────────────
    # Presets
    # ──────────────────────────────────────────────────────────────────────

    def _refresh_preset_list(self) -> None:
        self.preset_listbox.delete(0, tk.END)
        for i, (x, y, z, name) in enumerate(self.preset_points):
            self.preset_listbox.insert(tk.END, f"#{i + 1} {name}: ({x:.0f},{y:.0f},{z:.0f})")

    def _on_preset_select(self, _event) -> None:
        sel = self.preset_listbox.curselection()
        if sel:
            x, y, z, name = self.preset_points[sel[0]]
            self.target_x_var.set(x)
            self.target_y_var.set(y)
            self.target_z_var.set(z)
            self.target_point = (x, y, z)
            self._draw_robot()
            self.ik_status_var.set(f"Preset: {name}")

    def _save_preset(self) -> None:
        x = self.target_x_var.get()
        y = self.target_y_var.get()
        z = self.target_z_var.get()
        result = self._ik.solve(x, y, z, max_iterations=200, tolerance=1.0)
        if result is None:
            messagebox.showwarning(
                "IK Failed", f"Point ({x:.0f},{y:.0f},{z:.0f}) is not reachable!"
            )
            return
        name = f"Point #{len(self.preset_points) + 1}"
        self.preset_points.append((x, y, z, name))
        self._refresh_preset_list()
        self.ik_status_var.set(f"Saved: {name}")

    def _remove_preset(self) -> None:
        sel = self.preset_listbox.curselection()
        if sel:
            removed = self.preset_points.pop(sel[0])
            self._refresh_preset_list()
            self.ik_status_var.set(f"Removed: {removed[3]}")

    def _clear_presets(self) -> None:
        if messagebox.askyesno("Clear", "Remove all presets?"):
            self.preset_points.clear()
            self._refresh_preset_list()
            self.ik_status_var.set("")

    def _apply_preset(self) -> None:
        sel = self.preset_listbox.curselection()
        if not sel:
            messagebox.showinfo("Select", "Choose a point from the list")
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
        self.wp_listbox.insert(tk.END, f"#{n}: ({x:.1f},{y:.1f},{z:.1f})")
        self._draw_robot()
        self.ik_status_var.set(f"Waypoint #{n} added")

    def _remove_waypoint(self) -> None:
        sel = self.wp_listbox.curselection()
        if not sel:
            messagebox.showwarning("Select", "Choose a point to remove")
            return
        self.waypoints.pop(sel[0])
        self._refresh_waypoint_list()
        self._draw_robot()

    def _clear_waypoints(self) -> None:
        self.waypoints.clear()
        self.wp_listbox.delete(0, tk.END)
        self._draw_robot()
        self.ik_status_var.set("Route cleared")

    def _refresh_waypoint_list(self) -> None:
        self.wp_listbox.delete(0, tk.END)
        for i, (x, y, z) in enumerate(self.waypoints):
            self.wp_listbox.insert(tk.END, f"#{i + 1}: ({x:.1f},{y:.1f},{z:.1f})")

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
            messagebox.showwarning("Select", "Choose a point!")
            return
        x, y, z = self.waypoints[sel[0]]
        self.target_x_var.set(x)
        self.target_y_var.set(y)
        self.target_z_var.set(z)
        self._move_to_target()

    def _run_waypoints(self) -> None:
        if not self.waypoints:
            messagebox.showwarning("Route empty", "Add points to route!")
            return
        lines = "\n".join(
            f"  #{i + 1}: ({x:.0f},{y:.0f},{z:.0f})" for i, (x, y, z) in enumerate(self.waypoints)
        )
        if not messagebox.askyesno(
            "Run Route",
            f"Move to {len(self.waypoints)} points?\n\n{lines}\n\nWARNING: Ensure path is clear!",
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
            self.after(
                0,
                lambda ix=i, lx=x, ly=y, lz=z: self._waypoint_step_ui(ix, lx, ly, lz, total),
            )

            result = self._ik.solve(x, y, z, max_iterations=300, tolerance=1.0)
            if result is None:
                self.after(
                    0,
                    lambda ix=i: self._info_append(f"! IK failed for point #{ix + 1}\n", "err"),
                )
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
                        self.after(
                            0,
                            lambda ix=i, err=str(e): self._info_append(
                                f"! #{ix + 1} J{j + 1}: {err}\n", "err"
                            ),
                        )
                time.sleep(2.0)

            self.after(
                0,
                lambda ix=i: self._info_append(f"+ Point #{ix + 1} reached\n", "ok"),
            )

        self._wp_running = False
        self.after(0, lambda: self.ik_status_var.set(f"Done ({total} points)"))

    def _waypoint_step_ui(self, idx: int, x, y, z, total: int) -> None:
        self.target_x_var.set(x)
        self.target_y_var.set(y)
        self.target_z_var.set(z)
        self.ik_status_var.set(f"-> Point {idx + 1}/{total}: ({x:.0f},{y:.0f},{z:.0f})")
        self.wp_listbox.selection_clear(0, tk.END)
        self.wp_listbox.selection_set(idx)
        self.wp_listbox.see(idx)

    def _update_sliders_from_angles(self, angles: list[float]) -> None:
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
        self.log("Angles reset to 0", "info")

    def _apply_all(self, confirm: bool = True) -> None:
        if not self.controller.connected:
            messagebox.showwarning("No Connection", "Connect to robot first!")
            return
        if confirm and not messagebox.askyesno("Confirm", "Apply all angles to robot?"):
            return
        for i in range(6):
            motor_id = self._get_motor_id(i)
            pos = self._angle_to_position(self.joint_angles[i], i)
            self.controller.move_motor(motor_id, pos)
        self.log("All angles applied", "success")

    def _emergency_stop(self) -> None:
        self._wp_running = False
        if self.controller.connected:
            self.controller.emergency_stop_all()
        self.log("EMERGENCY STOP", "error")

    def _reset_camera(self) -> None:
        if self.ax:
            self.ax.view_init(elev=25, azim=45)
            self.canvas.draw()

    # ──────────────────────────────────────────────────────────────────────
    # 3D drawing
    # ──────────────────────────────────────────────────────────────────────

    def _compute_ik_path(
        self,
        start: list[float],
        end: list[float],
        steps: int = 40,
    ) -> list[tuple[float, float, float]]:
        """Linear interpolation in joint space -> list of EE positions."""
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
        self.ax.set_xlabel("X (mm)", color=FANUC_TEXT2)
        self.ax.set_ylabel("Y (mm)", color=FANUC_TEXT2)
        self.ax.set_zlabel("Z (mm)", color=FANUC_TEXT2)
        self.ax.set_title("Robot Kinematics", color=FANUC_GREEN, fontsize=10)

        # Axes
        for pane in (self.ax.xaxis.pane, self.ax.yaxis.pane, self.ax.zaxis.pane):
            pane.fill = False
            pane.set_edgecolor(FANUC_GRAY)
        self.ax.tick_params(colors=FANUC_TEXT2, labelsize=7)

        # Work volume (sphere) - wireframe for visibility
        theta = np.linspace(0, np.pi, 20)
        phi = np.linspace(0, 2 * np.pi, 20)
        t, p = np.meshgrid(theta, phi)
        wx = max_r * np.sin(t) * np.cos(p)
        wy = max_r * np.sin(t) * np.sin(p)
        wz = max_r * np.cos(t)
        self.ax.plot_wireframe(wx, wy, wz, alpha=0.1, color=FANUC_GREEN, linewidth=0.5)

        # Robot links
        self.ax.plot(xs, ys, zs, color=LINK_COL, linewidth=3, zorder=5)

        # Joints
        for i, (x, y, z) in enumerate(zip(xs, ys, zs)):
            self.ax.scatter(
                [x],
                [y],
                [z],
                color=KINEMA_COLORS[i % len(KINEMA_COLORS)],
                s=80,
                zorder=6,
            )
            name = "Base" if i == 0 else f"J{i}"
            self.ax.text(x, y, z + 8, name, color=FANUC_TEXT2, fontsize=7)

        # End effector
        ee = self._kin.get_end_effector_position(self.joint_angles)
        self.ax.scatter([ee[0]], [ee[1]], [ee[2]], color=EE_COL, s=120, marker="*", zorder=7)
        self.ax.text(
            ee[0],
            ee[1],
            ee[2] + 10,
            f"EE ({ee[0]:.0f},{ee[1]:.0f},{ee[2]:.0f})",
            color=EE_COL,
            fontsize=8,
        )

        # Target point
        if self.target_point:
            tx, ty, tz = self.target_point
            tgt_color = FANUC_GREEN if self.ik_target_reachable else TGT_COL
            self.ax.scatter([tx], [ty], [tz], color=tgt_color, s=160, marker="X", zorder=7)
            self.ax.text(
                tx,
                ty,
                tz + 10,
                f"{'OK' if self.ik_target_reachable else '?'} ({tx:.0f},{ty:.0f},{tz:.0f})",
                color=tgt_color,
                fontsize=8,
                fontweight="bold",
            )
            # Line from EE to target
            self.ax.plot(
                [ee[0], tx],
                [ee[1], ty],
                [ee[2], tz],
                color=tgt_color,
                linewidth=1,
                linestyle="--",
                alpha=1.0,
            )

        # Waypoints
        if self.waypoints:
            wx_arr = [p[0] for p in self.waypoints]
            wy_arr = [p[1] for p in self.waypoints]
            wz_arr = [p[2] for p in self.waypoints]
            self.ax.scatter(
                wx_arr,
                wy_arr,
                wz_arr,
                color=WP_COL,
                s=60,
                marker="D",
                alpha=0.7,
                zorder=6,
            )
            self.ax.plot(
                wx_arr,
                wy_arr,
                wz_arr,
                color=WP_COL,
                linewidth=1,
                linestyle=":",
                alpha=1.0,
            )
            for i, (px, py, pz) in enumerate(self.waypoints):
                self.ax.text(px, py, pz + 8, f"#{i + 1}", color=WP_COL, fontsize=7)

        # IK path
        if self.ik_path and len(self.ik_path) >= 2:
            px = [p[0] for p in self.ik_path]
            py = [p[1] for p in self.ik_path]
            pz = [p[2] for p in self.ik_path]
            n = len(self.ik_path)
            for k in range(n - 1):
                t = k / (n - 1)
                r = t
                g = t
                b = t
                self.ax.plot(
                    [px[k], px[k + 1]],
                    [py[k], py[k + 1]],
                    [pz[k], pz[k + 1]],
                    color=(r, g, b),
                    linewidth=2,
                    alpha=1.0,
                    zorder=4,
                )
            self.ax.scatter(
                [px[0]],
                [py[0]],
                [pz[0]],
                color=FANUC_GREEN,
                s=60,
                marker="o",
                zorder=8,
            )
            self.ax.scatter(
                [px[-1]],
                [py[-1]],
                [pz[-1]],
                color=FANUC_GREEN,
                s=80,
                marker="*",
                zorder=8,
            )

        self.figure.tight_layout(pad=1.0)
        self.canvas.draw()

    # ──────────────────────────────────────────────────────────────────────
    # Info text update
    # ──────────────────────────────────────────────────────────────────────

    def _update_info(self) -> None:
        ee = self._kin.get_end_effector_position(self.joint_angles)
        lines = [
            ("== Current Position ==\n", "head"),
        ]
        for i, angle in enumerate(self.joint_angles):
            pos = int((angle + 180.0) / 360.0 * MAX_POSITION)
            lines.append((f"  J{i + 1}: {angle:+7.1f}  pos={pos}\n", ""))
        lines += [
            ("\n== End Effector ==\n", "head"),
            (f"  X: {ee[0]:7.1f} mm\n", ""),
            (f"  Y: {ee[1]:7.1f} mm\n", ""),
            (f"  Z: {ee[2]:7.1f} mm\n", ""),
        ]
        if self.target_point:
            tx, ty, tz = self.target_point
            err = math.sqrt((ee[0] - tx) ** 2 + (ee[1] - ty) ** 2 + (ee[2] - tz) ** 2)
            lines += [
                ("\n== Target ==\n", "head"),
                (f"  X: {tx:7.1f}  Y: {ty:7.1f}  Z: {tz:7.1f}\n", ""),
                (
                    f"  Error: {err:.2f} mm\n",
                    "ok" if err < 5 else "warn" if err < 20 else "err",
                ),
            ]
        self.info_text.delete("1.0", tk.END)
        for text, tag in lines:
            self.info_text.insert(tk.END, text, tag)

    # ──────────────────────────────────────────────────────────────────────
    # External API
    # ──────────────────────────────────────────────────────────────────────

    @property
    def kinematics(self) -> RobotKinematics6DOF:
        return self._kin

    def _on_live_toggle(self) -> None:
        self._live_mode = self._live_toggle_var.get()
        if not self._live_mode:
            self._live_var.set("OFF")
            self._live_label.configure(foreground=FANUC_RED)

    def _go_home(self) -> None:
        """Reset all joints to 0."""
        for i in range(6):
            self.slider_vars[i].set(0.0)
            self.joint_angles[i] = 0.0
            self._update_pos_display(i)
        self.ik_path = None
        self._draw_robot()
        self.log("Home position", "info")

        if self.controller.connected:
            if messagebox.askyesno("Home", "Send HOME command to all motors?"):
                for i in range(6):
                    motor_id = self._get_motor_id(i)
                    home_pos = MAX_POSITION // 2
                    if self._is_inverted(i):
                        home_pos = MAX_POSITION - home_pos
                    self.controller.move_motor(motor_id, home_pos)
