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
    MAX_POSITION,
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
        self.min_pos_vars: dict[int, tk.IntVar] = {}
        self.max_pos_vars: dict[int, tk.IntVar] = {}
        self.position_bars: dict[int, tk.Canvas] = {}
        self.fill_rects: dict[int, int] = {}
        self.current_positions: dict[int, int] = {i: 0 for i in range(6)}
        self.validation_errors: dict[int, bool] = {}

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
            ("Dir", 50),
            ("Min", 70),
            ("Max", 70),
            ("Position", 140),
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

            # direction toggle button (NEW)
            inv_var = tk.BooleanVar(value=False)
            self.inverted_vars[i] = inv_var
            dir_btn = tk.Button(
                row,
                text="↑",
                font=("SF Mono", 12, "bold"),
                bg=FANUC_GREEN,
                fg=FANUC_BG,
                bd=0,
                relief="flat",
                width=3,
                command=lambda idx=i: self._toggle_direction(idx),
            )
            dir_btn.pack(side="left", padx=6)

            # min position spinbox (NEW)
            min_var = tk.IntVar(value=0)
            self.min_pos_vars[i] = min_var
            min_sb = ttk.Spinbox(
                row,
                from_=0,
                to=4095,
                textvariable=min_var,
                width=5,
                font=("SF Mono", 9),
            )
            min_sb.pack(side="left", padx=4)

            # max position spinbox (NEW)
            max_var = tk.IntVar(value=4095)
            self.max_pos_vars[i] = max_var
            max_sb = ttk.Spinbox(
                row,
                from_=0,
                to=4095,
                textvariable=max_var,
                width=5,
                font=("SF Mono", 9),
            )
            max_sb.pack(side="left", padx=4)

            # position bar canvas (NEW)
            bar_canvas = tk.Canvas(
                row,
                width=100,
                height=20,
                bg=FANUC_BG,
                highlightthickness=1,
                highlightbackground=FANUC_GRAY,
            )
            bar_canvas.pack(side="left", padx=6)
            self.position_bars[i] = bar_canvas

            # Draw background rectangle
            bar_canvas.create_rectangle(2, 2, 98, 18, fill=FANUC_PANEL, outline="")
            # Draw fill rectangle (will be updated later)
            fill_rect = bar_canvas.create_rectangle(2, 2, 2, 18, fill=FANUC_BLUE, outline="")
            self.fill_rects[i] = fill_rect

            # Position label
            pos_label = tk.Label(
                row,
                text="0",
                font=("SF Mono", 9),
                bg=FANUC_PANEL,
                fg=FANUC_TEXT,
                width=5,
            )
            pos_label.pack(side="left", padx=4)

            self.validation_errors[i] = False
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
                self.min_pos_vars[i].set(m.get("min_pos", 0))
                self.max_pos_vars[i].set(m.get("max_pos", MAX_POSITION))

                # Update direction button appearance
                for widget in self.rows[i].pack_slaves():
                    if isinstance(widget, tk.Button) and widget.cget("text") in ["↑", "↓"]:
                        if m.get("inverted", False):
                            widget.config(text="↓", bg=FANUC_ORANGE)
                        else:
                            widget.config(text="↑", bg=FANUC_GREEN)
                        break

    def _save_mapping(self):
        # Validate all min/max pairs first
        has_errors = False
        for i in range(6):
            if not self._validate_min_max(i):
                has_errors = True

        if has_errors:
            messagebox.showwarning(
                "Validation Error", "Min position must be less than Max position for all joints."
            )
            return

        for i in range(6):
            self.controller.update_motor_mapping(
                joint_index=i,
                motor_id=self.mapping_vars[i].get(),
                name=self.name_vars[i].get(),
                inverted=self.inverted_vars[i].get(),
                min_pos=self.min_pos_vars[i].get(),
                max_pos=self.max_pos_vars[i].get(),
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
                    self.min_pos_vars[i].set(m["min_pos"])
                    self.max_pos_vars[i].set(m["max_pos"])

                    # Reset direction button appearance
                    for widget in self.rows[i].pack_slaves():
                        if isinstance(widget, tk.Button) and widget.cget("text") in ["↑", "↓"]:
                            if m["inverted"]:
                                widget.config(text="↓", bg=FANUC_ORANGE)
                            else:
                                widget.config(text="↑", bg=FANUC_GREEN)
                            break
            self._save_mapping()

    def _auto_detect(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first")
            return
        self.log("Scanning for motors...", "info")

    def _toggle_direction(self, joint_index: int):
        """Toggle direction button between ↑ (normal) and ↓ (inverted)."""
        current = self.inverted_vars[joint_index].get()
        self.inverted_vars[joint_index].set(not current)

        # Update button appearance
        row_widgets = self.rows[joint_index].pack_slaves()
        dir_btn = None
        # Find the direction button (5th widget after joint label, motor spinbox, name entry)
        for idx, widget in enumerate(self.rows[joint_index].pack_slaves()):
            if isinstance(widget, tk.Button) and widget.cget("text") in ["↑", "↓"]:
                dir_btn = widget
                break

        if dir_btn:
            if not current:  # switching to inverted
                dir_btn.config(text="↓", bg=FANUC_ORANGE)
            else:  # switching to normal
                dir_btn.config(text="↑", bg=FANUC_GREEN)

    def _validate_min_max(self, joint_index: int) -> bool:
        """Validate min < max. Returns True if valid."""
        min_val = self.min_pos_vars[joint_index].get()
        max_val = self.max_pos_vars[joint_index].get()

        if min_val >= max_val:
            self.validation_errors[joint_index] = True
            return False
        self.validation_errors[joint_index] = False
        return True

    def _update_position_bar(self, joint_index: int, position: int):
        """Update the position bar visualization."""
        min_pos = self.min_pos_vars[joint_index].get()
        max_pos = self.max_pos_vars[joint_index].get()

        # Calculate ratio
        if max_pos > min_pos:
            ratio = (position - min_pos) / (max_pos - min_pos)
            ratio = max(0, min(1, ratio))  # clamp to 0-1
        else:
            ratio = 0

        # Update fill rectangle
        fill_width = int(96 * ratio)  # 96px max width (100 - 4px padding)
        canvas = self.position_bars[joint_index]
        fill_rect = self.fill_rects[joint_index]

        canvas.coords(fill_rect, [2, 2, 2 + fill_width, 18])

        # Update position label (find it in row)
        for widget in self.rows[joint_index].pack_slaves():
            if isinstance(widget, tk.Label) and widget.cget("width") == 5:
                widget.config(text=str(position))
                break

        self.current_positions[joint_index] = position

    def update_positions(self, data: dict):
        """Update position bars with current motor positions.

        Args:
            data: Dict mapping joint_index to current position
        """
        for joint_index, position in data.items():
            if joint_index in self.position_bars:
                self._update_position_bar(joint_index, position)
