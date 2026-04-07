#!/usr/bin/env python3

"""
Motor Mapping Panel — Minimalist B&W
"""

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from app.config.constants import (
    DEFAULT_MOTOR_MAPPING,
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_TEXT,
    JOINT_NAMES,
)
from app.controllers.motor_controller import MotorController


class MotorMappingPanel(ttk.Frame):
    """Minimalist Motor Mapping Panel."""

    def __init__(
        self,
        parent: tk.Misc,
        controller: MotorController,
        log_callback: Callable[[str, str], None],
    ):
        super().__init__(parent, style="TFrame")
        self.controller = controller
        self.log = log_callback

        self.mapping_vars: dict[int, tk.IntVar] = {}
        self.name_vars: dict[int, tk.StringVar] = {}
        self.inverted_vars: dict[int, tk.BooleanVar] = {}

        self._create_widgets()
        self._load_current_mapping()

    def _create_widgets(self):
        main = tk.Frame(self, bg=FANUC_BG)
        main.pack(fill="both", expand=True, padx=20, pady=16)

        hdr = tk.Frame(main, bg=FANUC_BG)
        hdr.pack(fill="x", pady=(0, 12))
        tk.Label(
            hdr,
            text="MOTOR MAPPING",
            font=("SF Pro", 14, "bold"),
            bg=FANUC_BG,
            fg=FANUC_GREEN,
        ).pack(side="left")
        tk.Button(
            hdr,
            text="SAVE",
            font=("SF Pro", 10, "bold"),
            bg=FANUC_BLUE,
            fg=FANUC_BG,
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            command=self._save_mapping,
        ).pack(side="right", padx=4)
        tk.Button(
            hdr,
            text="RESET",
            font=("SF Pro", 10, "bold"),
            bg=FANUC_GRAY,
            fg=FANUC_BG,
            bd=0,
            relief="flat",
            padx=12,
            pady=4,
            command=self._reset_mapping,
        ).pack(side="right")

        # table header
        hdr_frame = tk.Frame(main, bg=FANUC_PANEL)
        hdr_frame.pack(fill="x", pady=(0, 2))
        for txt, w in [
            ("Joint", 120),
            ("Motor ID", 80),
            ("Name", 160),
            ("Inverted", 80),
        ]:
            tk.Label(
                hdr_frame,
                text=txt,
                font=("SF Mono", 10, "bold"),
                bg=FANUC_PANEL,
                fg=FANUC_ORANGE,
                width=w // 8,
            ).pack(side="left", padx=4, pady=6)

        # rows
        self.rows = {}
        for i in range(6):
            row = tk.Frame(main, bg=FANUC_PANEL)
            row.pack(fill="x", pady=2)

            # joint label
            tk.Label(
                row,
                text=f"J{i + 1}",
                font=("SF Mono", 11, "bold"),
                bg=FANUC_PANEL,
                fg=FANUC_GREEN,
                width=8,
            ).pack(side="left", padx=6)

            # motor id spinbox
            mid_var = tk.IntVar(value=i + 1)
            self.mapping_vars[i] = mid_var
            sb = ttk.Spinbox(
                row,
                from_=1,
                to=253,
                textvariable=mid_var,
                width=6,
                font=("SF Mono", 10),
            )
            sb.pack(side="left", padx=6)

            # name entry
            name_var = tk.StringVar(value=JOINT_NAMES[i])
            self.name_vars[i] = name_var
            en = tk.Entry(
                row,
                textvariable=name_var,
                font=("SF Mono", 10),
                bg=FANUC_BG,
                fg=FANUC_TEXT,
                width=18,
                bd=0,
                relief="flat",
            )
            en.pack(side="left", padx=6)

            # inverted checkbox
            inv_var = tk.BooleanVar(value=False)
            self.inverted_vars[i] = inv_var
            chk = tk.Checkbutton(
                row,
                variable=inv_var,
                onvalue=True,
                offvalue=False,
                bg=FANUC_PANEL,
                fg=FANUC_TEXT,
                activebackground=FANUC_PANEL,
            )
            chk.pack(side="left", padx=6)

            self.rows[i] = row

        # action buttons
        act = tk.Frame(main, bg=FANUC_BG)
        act.pack(fill="x", pady=16)
        tk.Button(
            act,
            text="AUTO DETECT",
            font=("SF Pro", 10, "bold"),
            bg=FANUC_BLUE,
            fg=FANUC_BG,
            bd=0,
            relief="flat",
            padx=14,
            pady=8,
            command=self._auto_detect,
        ).pack(side="left", padx=4)

    def _load_current_mapping(self):
        mapping = self.controller.motor_mapping
        for i in range(6):
            key = f"joint_{i}"
            if key in mapping:
                m = mapping[key]
                self.mapping_vars[i].set(m.get("motor_id", i + 1))
                self.name_vars[i].set(m.get("name", JOINT_NAMES[i]))
                self.inverted_vars[i].set(m.get("inverted", False))

    def _save_mapping(self):
        for i in range(6):
            self.controller.update_motor_mapping(
                joint_index=i,
                motor_id=self.mapping_vars[i].get(),
                name=self.name_vars[i].get(),
                inverted=self.inverted_vars[i].get(),
            )
        if self.controller.save_config():
            self.log("Mapping saved", "success")
        else:
            self.log("Save failed", "error")

    def _reset_mapping(self):
        if messagebox.askyesno("Confirm", "Reset to default?"):
            for i in range(6):
                key = f"joint_{i}"
                if key in DEFAULT_MOTOR_MAPPING:
                    m = DEFAULT_MOTOR_MAPPING[key]
                    self.mapping_vars[i].set(m["motor_id"])
                    self.name_vars[i].set(m["name"])
                    self.inverted_vars[i].set(m["inverted"])
            self._save_mapping()

    def _auto_detect(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first")
            return
        self.log("Scanning for motors...", "info")

    def update_positions(self, data):
        pass
