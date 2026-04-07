#!/usr/bin/env python3

"""
Manual Control Panel — Minimalist B&W
"""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from app.config.constants import (
    DEFAULT_SPEED,
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_TEXT,
    MAX_POSITION,
)
from app.controllers.motor_controller import MotorController


class ManualControlPanel(ttk.Frame):
    """Minimalist Jog Control Panel."""

    def __init__(
        self,
        parent,
        controller: MotorController,
        log_callback: Callable,
        update_callback: Callable | None = None,
    ):
        super().__init__(parent, style="TFrame")
        self.controller = controller
        self.log = log_callback
        self.update_callback = update_callback

        self.selected_joint = 0
        self.jog_step = 100

        self.joint_var = tk.IntVar(value=0)
        self.speed_var = tk.IntVar(value=DEFAULT_SPEED)
        self.pos_var = tk.IntVar(value=0)
        self.step_var = tk.IntVar(value=100)

        self.joint_buttons: dict[int, tk.Button] = {}
        self.joint_pos_labels: dict[int, tk.Label] = {}
        self.joint_angle_labels: dict[int, tk.Label] = {}
        self.speed_label: ttk.Label | None = None
        self.status_label: tk.Label | None = None

        self._create_widgets()
        self._update_all_positions()

    def _create_widgets(self):
        main = tk.Frame(self, bg=FANUC_BG)
        main.pack(fill="both", expand=True, padx=16, pady=12)

        # left: joint list
        left = tk.Frame(main, bg=FANUC_BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        lf = tk.LabelFrame(
            left,
            text="JOINTS",
            bg=FANUC_BG,
            fg=FANUC_GREEN,
            font=("SF Pro", 10, "bold"),
        )
        lf.pack(fill="x", pady=(0, 8))

        for i in range(6):
            row = tk.Frame(lf, bg=FANUC_PANEL)
            row.pack(fill="x", padx=4, pady=2)

            name = self.controller.get_joint_name(i)

            btn = tk.Button(
                row,
                text=f"J{i + 1}",
                width=3,
                font=("SF Mono", 10, "bold"),
                bg=FANUC_PANEL,
                fg=FANUC_TEXT,
                activebackground=FANUC_GREEN,
                bd=0,
                relief="flat",
                command=lambda idx=i: self.select_joint(idx),
            )
            btn.pack(side="left", padx=2)
            self.joint_buttons[i] = btn

            tk.Label(
                row,
                text=name,
                font=("SF Pro", 9),
                bg=FANUC_PANEL,
                fg=FANUC_GRAY,
                width=10,
                anchor="w",
            ).pack(side="left", padx=4)

            pos_lbl = tk.Label(
                row,
                text="----",
                font=("SF Mono", 10),
                bg=FANUC_BG,
                fg=FANUC_TEXT,
                width=5,
                relief="sunken",
            )
            pos_lbl.pack(side="left", padx=2)
            self.joint_pos_labels[i] = pos_lbl

            ang_lbl = tk.Label(
                row,
                text="0.0°",
                font=("SF Mono", 9),
                bg=FANUC_PANEL,
                fg=FANUC_ORANGE,
                width=6,
            )
            ang_lbl.pack(side="left", padx=2)
            self.joint_angle_labels[i] = ang_lbl

        self._update_joint_highlight()

        # center: jog
        center = tk.Frame(main, bg=FANUC_BG)
        center.pack(side="left", fill="both", expand=True, padx=8)

        cf = tk.LabelFrame(
            center, text="JOG", bg=FANUC_BG, fg=FANUC_GREEN, font=("SF Pro", 10, "bold")
        )
        cf.pack(fill="x", pady=(0, 8))

        btn_frame = tk.Frame(cf, bg=FANUC_PANEL)
        btn_frame.pack(pady=12)

        tk.Button(
            btn_frame,
            text="−",
            width=6,
            height=2,
            font=("SF Pro", 18, "bold"),
            bg=FANUC_ORANGE,
            fg=FANUC_BG,
            bd=0,
            relief="flat",
            command=lambda: self.jog(-1),
        ).grid(row=0, column=0, padx=12)

        self.jog_ind = tk.Label(
            btn_frame,
            text="J1",
            width=4,
            font=("SF Mono", 24, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_GREEN,
        )
        self.jog_ind.grid(row=0, column=1, padx=16)

        tk.Button(
            btn_frame,
            text="+",
            width=6,
            height=2,
            font=("SF Pro", 18, "bold"),
            bg=FANUC_GREEN,
            fg=FANUC_BG,
            bd=0,
            relief="flat",
            command=lambda: self.jog(1),
        ).grid(row=0, column=2, padx=12)

        # step buttons
        stp_f = tk.Frame(cf, bg=FANUC_PANEL)
        stp_f.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(
            stp_f,
            text="STEP",
            font=("SF Mono", 9, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_ORANGE,
        ).pack(side="left", padx=6)

        self.step_btns: dict[int, tk.Button] = {}
        for step in [10, 50, 100, 250, 500, 1000]:
            b = tk.Button(
                stp_f,
                text=str(step),
                width=4,
                font=("SF Mono", 9),
                bg=FANUC_PANEL if step != 100 else FANUC_BLUE,
                fg=FANUC_TEXT if step != 100 else FANUC_BG,
                bd=0,
                relief="flat",
                command=lambda s=step: self._set_step(s),
            )
            b.pack(side="left", padx=2)
            self.step_btns[step] = b

        # target
        tg_f = tk.LabelFrame(
            center,
            text="GO TO",
            bg=FANUC_BG,
            fg=FANUC_GREEN,
            font=("SF Pro", 10, "bold"),
        )
        tg_f.pack(fill="x", pady=(0, 8))

        tg_in = tk.Frame(tg_f, bg=FANUC_PANEL)
        tg_in.pack(fill="x", padx=10, pady=8)

        self.target_var = tk.IntVar(value=2048)
        ttk.Spinbox(
            tg_in,
            from_=0,
            to=MAX_POSITION,
            textvariable=self.target_var,
            width=10,
            font=("SF Mono", 14),
        ).pack(side="left", padx=6)

        tk.Button(
            tg_in,
            text="MOVE",
            font=("SF Pro", 10, "bold"),
            bg=FANUC_BLUE,
            fg=FANUC_BG,
            bd=0,
            relief="flat",
            padx=14,
            pady=4,
            command=self._move_to_target,
        ).pack(side="left", padx=8)

        self.status_label = tk.Label(
            center,
            text="J1 | POS: 0 | 0.0°",
            font=("SF Mono", 11, "bold"),
            bg=FANUC_BG,
            fg=FANUC_GREEN,
            relief="sunken",
            padx=10,
            pady=6,
        )
        self.status_label.pack(fill="x", pady=4)

        # right: speed + quick cmds
        right = tk.Frame(main, bg=FANUC_BG)
        right.pack(side="left", fill="both", padx=(8, 0))

        spd_f = tk.LabelFrame(
            right,
            text="SPEED",
            bg=FANUC_BG,
            fg=FANUC_GREEN,
            font=("SF Pro", 10, "bold"),
        )
        spd_f.pack(fill="x", pady=(0, 8))

        tk.Scale(
            spd_f,
            from_=100,
            to=10000,
            variable=self.speed_var,
            orient="horizontal",
            bg=FANUC_BG,
            fg=FANUC_ORANGE,
            troughcolor=FANUC_GRAY,
            highlightthickness=0,
            command=self._on_speed,
        ).pack(fill="x", padx=10, pady=6)

        self.speed_label = tk.Label(
            spd_f,
            text=f"{DEFAULT_SPEED}",
            font=("SF Mono", 12, "bold"),
            bg=FANUC_BG,
            fg=FANUC_GREEN,
        )
        self.speed_label.pack()

        cmd_f = tk.LabelFrame(
            right,
            text="QUICK",
            bg=FANUC_BG,
            fg=FANUC_GREEN,
            font=("SF Pro", 10, "bold"),
        )
        cmd_f.pack(fill="x")

        for txt, cmd, bg in [
            ("HOME", self._go_home, FANUC_BLUE),
            ("CENTER", self._go_center, FANUC_GREEN),
            ("TRQ ON", self._torque_on, FANUC_GREEN),
            ("TRQ OFF", self._torque_off, FANUC_ORANGE),
        ]:
            tk.Button(
                cmd_f,
                text=txt,
                font=("SF Pro", 9, "bold"),
                bg=bg,
                fg=FANUC_BG,
                bd=0,
                relief="flat",
                padx=8,
                pady=6,
                command=cmd,
            ).pack(fill="x", padx=6, pady=2)

    # ── actions ──

    def select_joint(self, idx: int):
        self.selected_joint = idx
        self.joint_var.set(idx)
        self.jog_ind.config(text=f"J{idx + 1}")
        self._update_joint_highlight()
        self._update_status()
        self.log(f"J{idx + 1} selected", "info")

    def _update_joint_highlight(self):
        for i, btn in self.joint_buttons.items():
            if i == self.selected_joint:
                btn.config(bg=FANUC_GREEN, fg=FANUC_BG)
            else:
                btn.config(bg=FANUC_PANEL, fg=FANUC_TEXT)

    def _set_step(self, step: int):
        self.jog_step = step
        self.step_var.set(step)
        for s, btn in self.step_btns.items():
            if s == step:
                btn.config(bg=FANUC_BLUE, fg=FANUC_BG)
            else:
                btn.config(bg=FANUC_PANEL, fg=FANUC_TEXT)

    def _on_speed(self, val):
        speed = int(float(val))
        self.speed_label.config(text=f"{speed}")
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
        self.pos_var.set(int(pos))
        if self.status_label:
            name = self.controller.get_joint_name(self.selected_joint)
            self.status_label.config(
                text=f"J{self.selected_joint + 1} ({name}) | POS: {int(pos)} | {ang:.1f}°"
            )

    def _update_all_positions(self):
        for i in range(6):
            mid = self.controller.get_motor_id_for_joint(i)
            pos = self.controller.joint_positions.get(mid, 2048)
            ang = (pos / MAX_POSITION) * 360 - 180
            if i in self.joint_pos_labels:
                self.joint_pos_labels[i].config(text=f"{int(pos)}")
            if i in self.joint_angle_labels:
                self.joint_angle_labels[i].config(text=f"{ang:.1f}°")

    def update_from_monitor(self, data: dict[int, any]):
        for j in range(6):
            mid = self.controller.get_motor_id_for_joint(j)
            if mid in data:
                d = data[mid]
                if d.position is not None:
                    self.controller.joint_positions[mid] = d.position
        self._update_all_positions()
        self._update_status()
