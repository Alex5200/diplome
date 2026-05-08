#!/usr/bin/env python3
"""Manual Control Panel — CustomTkinter edition."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

import customtkinter as ctk

from app.config.constants import (
    DEFAULT_SPEED,
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_TEXT,
    FANUC_TEXT2,
    MAX_POSITION,
)
from app.controllers.motor_controller import MotorController

# ── Colour aliases ────────────────────────────────────────────────────────────
_ACCENT = "#7dd3c0"  # teal accent
_ACCENT_H = "#5bb8a4"  # teal hover
_JOINT_ACT = "#7dd3c0"  # selected joint bg
_JOINT_IDLE = FANUC_PANEL
_STEP_ACT = FANUC_BLUE
_STEP_IDLE = FANUC_PANEL


def _card(parent, title: str, title_color: str = _ACCENT, **kw) -> ctk.CTkFrame:
    """Convenience: returns a titled card frame (CTkFrame + label inside)."""
    card = ctk.CTkFrame(
        parent, fg_color=FANUC_PANEL, corner_radius=10, border_width=1, border_color="#e8e4e0", **kw
    )
    ctk.CTkLabel(
        card,
        text=title,
        font=ctk.CTkFont("Segoe UI", 9, "bold"),
        text_color=title_color,
        anchor="w",
    ).pack(anchor="w", padx=12, pady=(8, 2))
    return card


class ManualControlPanel(ctk.CTkFrame):
    """Minimalist Jog Control Panel — CTk."""

    def __init__(
        self,
        parent,
        controller: MotorController,
        log_callback: Callable,
        update_callback: Callable | None = None,
    ):
        super().__init__(parent, fg_color=FANUC_BG, corner_radius=0)
        self.controller = controller
        self.log = log_callback
        self.update_callback = update_callback

        self.selected_joint = 0
        self.jog_step = 100

        self.joint_var = tk.IntVar(value=0)
        self.speed_var = tk.IntVar(value=DEFAULT_SPEED)
        self.pos_var = tk.IntVar(value=0)
        self.target_var = tk.IntVar(value=2048)

        self.joint_buttons: dict[int, ctk.CTkButton] = {}
        self.joint_pos_labels: dict[int, ctk.CTkLabel] = {}
        self.joint_angle_labels: dict[int, ctk.CTkLabel] = {}
        self.step_btns: dict[int, ctk.CTkButton] = {}
        self.speed_label: ctk.CTkLabel | None = None
        self.status_label: ctk.CTkLabel | None = None
        self.jog_ind: ctk.CTkLabel | None = None

        self._create_widgets()
        self._update_all_positions()

    # ─────────────────────────────────────────────────────────────────────────
    # Layout
    # ─────────────────────────────────────────────────────────────────────────
    def _create_widgets(self):
        main = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        main.pack(fill="both", expand=True, padx=16, pady=12)

        # ── Left: joint list ─────────────────────────────────────────────────
        left = ctk.CTkFrame(main, fg_color=FANUC_BG, corner_radius=0)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        joints_card = _card(left, "JOINTS")
        joints_card.pack(fill="x", pady=(0, 8))

        for i in range(6):
            name = self.controller.get_joint_name(i)
            row = ctk.CTkFrame(joints_card, fg_color=FANUC_PANEL, corner_radius=0, height=36)
            row.pack(fill="x", padx=10, pady=2)
            row.pack_propagate(False)

            btn = ctk.CTkButton(
                row,
                text=f"J{i + 1}",
                width=38,
                height=28,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                fg_color=_JOINT_IDLE,
                text_color=FANUC_TEXT,
                hover_color=_ACCENT,
                corner_radius=6,
                border_width=1,
                border_color="#d0ccc8",
                command=lambda idx=i: self.select_joint(idx),
            )
            btn.pack(side="left", padx=(2, 4), pady=4)
            self.joint_buttons[i] = btn

            ctk.CTkLabel(
                row,
                text=name,
                font=ctk.CTkFont("Segoe UI", 9),
                text_color=FANUC_TEXT2,
                width=80,
                anchor="w",
            ).pack(side="left", padx=2)

            pos_lbl = ctk.CTkLabel(
                row,
                text="----",
                font=ctk.CTkFont("Consolas", 10),
                text_color=FANUC_TEXT,
                fg_color="#f0ece8",
                corner_radius=4,
                width=50,
                height=22,
            )
            pos_lbl.pack(side="left", padx=2)
            self.joint_pos_labels[i] = pos_lbl

            ang_lbl = ctk.CTkLabel(
                row,
                text="0.0°",
                font=ctk.CTkFont("Consolas", 9),
                text_color=FANUC_ORANGE,
                width=50,
            )
            ang_lbl.pack(side="left", padx=2)
            self.joint_angle_labels[i] = ang_lbl

        self._update_joint_highlight()

        # ── Center: jog controls ─────────────────────────────────────────────
        center = ctk.CTkFrame(main, fg_color=FANUC_BG, corner_radius=0)
        center.pack(side="left", fill="both", expand=True, padx=8)

        jog_card = _card(center, "JOG CONTROL")
        jog_card.pack(fill="x", pady=(0, 8))

        btn_row = ctk.CTkFrame(jog_card, fg_color=FANUC_PANEL, corner_radius=0)
        btn_row.pack(pady=12)

        ctk.CTkButton(
            btn_row,
            text="−",
            width=80,
            height=60,
            font=ctk.CTkFont("Segoe UI", 24, "bold"),
            fg_color=FANUC_ORANGE,
            text_color=FANUC_TEXT,
            hover_color="#d4995a",
            corner_radius=10,
            command=lambda: self.jog(-1),
        ).grid(row=0, column=0, padx=12)

        self.jog_ind = ctk.CTkLabel(
            btn_row,
            text="J1",
            width=64,
            font=ctk.CTkFont("Consolas", 26, "bold"),
            text_color=_ACCENT,
            fg_color=FANUC_PANEL,
        )
        self.jog_ind.grid(row=0, column=1, padx=16)

        ctk.CTkButton(
            btn_row,
            text="+",
            width=80,
            height=60,
            font=ctk.CTkFont("Segoe UI", 24, "bold"),
            fg_color=_ACCENT,
            text_color=FANUC_TEXT,
            hover_color=_ACCENT_H,
            corner_radius=10,
            command=lambda: self.jog(1),
        ).grid(row=0, column=2, padx=12)

        # Step buttons
        step_row = ctk.CTkFrame(jog_card, fg_color=FANUC_PANEL, corner_radius=0)
        step_row.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            step_row,
            text="STEP",
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=FANUC_TEXT2,
        ).pack(side="left", padx=6)

        for step in [10, 50, 100, 250, 500, 1000]:
            is_default = step == 100
            b = ctk.CTkButton(
                step_row,
                text=str(step),
                width=44,
                height=28,
                font=ctk.CTkFont("Segoe UI", 9),
                fg_color=_STEP_ACT if is_default else _STEP_IDLE,
                text_color=FANUC_TEXT,
                hover_color=_ACCENT,
                corner_radius=6,
                border_width=1,
                border_color="#d0ccc8",
                command=lambda s=step: self._set_step(s),
            )
            b.pack(side="left", padx=2)
            self.step_btns[step] = b

        # Go To target
        goto_card = _card(center, "GO TO POSITION")
        goto_card.pack(fill="x", pady=(0, 8))

        goto_row = ctk.CTkFrame(goto_card, fg_color=FANUC_PANEL, corner_radius=0)
        goto_row.pack(fill="x", padx=10, pady=8)

        ttk.Spinbox(
            goto_row,
            from_=0,
            to=MAX_POSITION,
            textvariable=self.target_var,
            width=10,
            font=("Consolas", 13),
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            goto_row,
            text="MOVE",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            fg_color=FANUC_BLUE,
            text_color=FANUC_TEXT,
            hover_color="#6a94d8",
            width=80,
            height=34,
            corner_radius=8,
            command=self._move_to_target,
        ).pack(side="left", padx=8)

        # Status bar
        self.status_label = ctk.CTkLabel(
            center,
            text="J1 | POS: 0 | 0.0°",
            font=ctk.CTkFont("Consolas", 11, "bold"),
            text_color=_ACCENT,
            fg_color=FANUC_PANEL,
            corner_radius=8,
            height=36,
        )
        self.status_label.pack(fill="x", pady=4, padx=0)

        # ── Right: speed + quick commands ────────────────────────────────────
        right = ctk.CTkFrame(main, fg_color=FANUC_BG, corner_radius=0)
        right.pack(side="left", fill="both", padx=(8, 0))

        spd_card = _card(right, "SPEED")
        spd_card.pack(fill="x", pady=(0, 8))

        spd_inner = ctk.CTkFrame(spd_card, fg_color=FANUC_PANEL, corner_radius=0)
        spd_inner.pack(fill="x", padx=10, pady=(4, 8))

        ctk.CTkSlider(
            spd_inner,
            from_=100,
            to=10000,
            variable=self.speed_var,
            orientation="horizontal",
            width=160,
            height=18,
            button_color=FANUC_ORANGE,
            button_hover_color="#d4995a",
            progress_color=FANUC_ORANGE,
            fg_color="#e8e4e0",
            command=self._on_speed,
        ).pack(fill="x", padx=6, pady=4)

        self.speed_label = ctk.CTkLabel(
            spd_inner,
            text=f"{DEFAULT_SPEED}",
            font=ctk.CTkFont("Consolas", 13, "bold"),
            text_color=_ACCENT,
        )
        self.speed_label.pack(pady=(0, 4))

        quick_card = _card(right, "QUICK ACTIONS")
        quick_card.pack(fill="x")

        for txt, cmd, fg, hov in [
            ("HOME", self._go_home, FANUC_BLUE, "#6a94d8"),
            ("CENTER", self._go_center, _ACCENT, _ACCENT_H),
            ("TRQ ON", self._torque_on, _ACCENT, _ACCENT_H),
            ("TRQ OFF", self._torque_off, FANUC_ORANGE, "#d4995a"),
        ]:
            ctk.CTkButton(
                quick_card,
                text=txt,
                font=ctk.CTkFont("Segoe UI", 9, "bold"),
                fg_color=fg,
                text_color=FANUC_TEXT,
                hover_color=hov,
                height=34,
                corner_radius=8,
                command=cmd,
            ).pack(fill="x", padx=8, pady=3)

    # ─────────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────────
    def select_joint(self, idx: int):
        self.selected_joint = idx
        self.joint_var.set(idx)
        if self.jog_ind:
            self.jog_ind.configure(text=f"J{idx + 1}")
        self._update_joint_highlight()
        self._update_status()
        self.log(f"J{idx + 1} selected", "info")

    def _update_joint_highlight(self):
        for i, btn in self.joint_buttons.items():
            if i == self.selected_joint:
                btn.configure(fg_color=_JOINT_ACT, text_color=FANUC_TEXT, border_color=_ACCENT_H)
            else:
                btn.configure(fg_color=_JOINT_IDLE, text_color=FANUC_TEXT, border_color="#d0ccc8")

    def _set_step(self, step: int):
        self.jog_step = step
        for s, btn in self.step_btns.items():
            btn.configure(
                fg_color=_STEP_ACT if s == step else _STEP_IDLE,
                text_color=FANUC_TEXT,
            )

    def _on_speed(self, val):
        speed = int(float(val))
        if self.speed_label:
            self.speed_label.configure(text=f"{speed}")
        self.controller.set_manual_speed(speed)

    def jog(self, direction: int):
        mid = self.controller.get_motor_id_for_joint(self.selected_joint)
        cur = self.controller.joint_positions.get(mid, 2048)
        new = max(0, min(MAX_POSITION, cur + direction * self.jog_step))
        self.controller.move_to_position(mid, new)
        self.controller.joint_positions[mid] = new
        self.pos_var.set(new)
        self._update_status()
        self._update_all_positions()

    def _move_to_target(self):
        mid = self.controller.get_motor_id_for_joint(self.selected_joint)
        pos = self.target_var.get()
        self.controller.move_to_position(mid, pos)
        self.controller.joint_positions[mid] = pos
        self.pos_var.set(pos)
        self._update_status()
        self._update_all_positions()
        self.log(f"J{self.selected_joint + 1} → {pos}", "info")

    def _go_home(self):
        self.target_var.set(0)
        self._move_to_target()

    def _go_center(self):
        self.target_var.set(2048)
        self._move_to_target()

    def _torque_on(self):
        mid = self.controller.get_motor_id_for_joint(self.selected_joint)
        self.controller.toggle_torque(mid, True)
        self.log(f"J{self.selected_joint + 1} Torque ON", "success")

    def _torque_off(self):
        mid = self.controller.get_motor_id_for_joint(self.selected_joint)
        self.controller.toggle_torque(mid, False)
        self.log(f"J{self.selected_joint + 1} Torque OFF", "warning")

    def _update_status(self):
        mid = self.controller.get_motor_id_for_joint(self.selected_joint)
        pos = self.controller.joint_positions.get(mid, 2048)
        ang = (pos / MAX_POSITION) * 360 - 180
        name = self.controller.get_joint_name(self.selected_joint)
        self.pos_var.set(int(pos))
        if self.status_label:
            self.status_label.configure(
                text=f"J{self.selected_joint + 1} ({name})  |  POS: {int(pos)}  |  {ang:.1f}°"
            )

    def _update_all_positions(self):
        for i in range(6):
            mid = self.controller.get_motor_id_for_joint(i)
            pos = self.controller.joint_positions.get(mid, 2048)
            ang = (pos / MAX_POSITION) * 360 - 180
            if i in self.joint_pos_labels:
                self.joint_pos_labels[i].configure(text=f"{int(pos)}")
            if i in self.joint_angle_labels:
                self.joint_angle_labels[i].configure(text=f"{ang:.1f}°")

    def update_from_monitor(self, data: dict):
        for j in range(6):
            mid = self.controller.get_motor_id_for_joint(j)
            if mid in data:
                d = data[mid]
                if d.position is not None:
                    self.controller.joint_positions[mid] = d.position
        self._update_all_positions()
        self._update_status()
