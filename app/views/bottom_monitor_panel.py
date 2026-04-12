#!/usr/bin/env python3
"""
Bottom Monitor Panel — CustomTkinter edition.

Compact horizontal row of 6 motor status cards.
"""

import tkinter as tk
from typing import Any

import customtkinter as ctk

from app.config.constants import (
    FANUC_BG,
    FANUC_GRAY,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    FANUC_TEXT2,
    MAX_POSITION,
    NUM_JOINTS,
    TEMP_CRITICAL,
    TEMP_WARNING,
)
from app.controllers.motor_controller import MotorController
from app.models.motor_data import MotorData

_ACCENT   = "#7dd3c0"
_GOOD     = _ACCENT
_WARN     = FANUC_ORANGE
_CRIT     = FANUC_RED
_IDLE     = FANUC_GRAY


class BottomMonitorPanel(ctk.CTkFrame):
    """Six compact motor cards in one horizontal strip."""

    def __init__(self, parent: tk.Misc, controller: MotorController):
        super().__init__(parent, fg_color=FANUC_BG, corner_radius=0)
        self.controller     = controller
        self.motor_widgets: dict[int, dict[str, Any]] = {}
        # Fonts must be created after the root window exists
        self._f_mono_sm = ctk.CTkFont("Consolas", 8)
        self._f_bold_sm = ctk.CTkFont("Segoe UI",  8, "bold")
        self._create_widgets()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _create_widgets(self):
        main = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        main.pack(fill="x", padx=2, pady=2)

        for i in range(NUM_JOINTS):
            card = self._create_motor_card(main, i)
            card.pack(side="left", fill="x", expand=True, padx=2)

    def _create_motor_card(self, parent, joint_idx: int) -> ctk.CTkFrame:
        name = self.controller.get_joint_name(joint_idx)

        card = ctk.CTkFrame(
            parent,
            fg_color=FANUC_PANEL,
            corner_radius=8,
            border_width=1,
            border_color="#e8e4e0",
        )

        row = ctk.CTkFrame(card, fg_color=FANUC_PANEL, corner_radius=0)
        row.pack(fill="x", padx=6, pady=4)

        # Status dot (tiny canvas, kept as tk.Canvas for pixel precision)
        dot_canvas = tk.Canvas(
            row, width=8, height=8,
            bg=FANUC_PANEL, highlightthickness=0,
        )
        dot_canvas.pack(side="left", padx=(0, 3))
        dot_canvas.create_oval(0, 0, 8, 8, fill=_IDLE, outline="", tags="dot")

        ctk.CTkLabel(
            row,
            text=f"J{joint_idx + 1} {name}",
            font=self._f_bold_sm,
            text_color=_ACCENT,
        ).pack(side="left")

        # Data labels
        pos_lbl  = self._mini_label(row, "-- (--)")
        self._sep(row)
        temp_lbl = self._mini_label(row)
        self._sep(row)
        load_lbl = self._mini_label(row)
        self._sep(row)
        volt_lbl = self._mini_label(row, fg=FANUC_TEXT2)

        self.motor_widgets[joint_idx] = {
            "card":       card,
            "dot_canvas": dot_canvas,
            "pos_label":  pos_lbl,
            "temp_label": temp_lbl,
            "load_label": load_lbl,
            "volt_label": volt_lbl,
        }
        return card

    def _mini_label(self, parent, text: str = "--", fg: str = FANUC_TEXT) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(parent, text=text, font=self._f_mono_sm, text_color=fg)
        lbl.pack(side="left")
        return lbl

    def _sep(self, parent):
        ctk.CTkLabel(parent, text=" | ", font=self._f_mono_sm, text_color=FANUC_TEXT2).pack(side="left")

    # ── Data update ───────────────────────────────────────────────────────────
    def update_data(self, motor_data_dict: dict[int, MotorData]):
        for joint_idx in range(NUM_JOINTS):
            motor_id = self.controller.get_motor_id_for_joint(joint_idx)
            if motor_id not in motor_data_dict or joint_idx not in self.motor_widgets:
                continue

            data = motor_data_dict[motor_id]
            w    = self.motor_widgets[joint_idx]

            # Status dot colour
            dot_color = _IDLE
            if data.position is not None:
                dot_color = _GOOD
                if data.is_overheating():
                    dot_color = _CRIT
                elif (data.temperature and data.temperature >= TEMP_WARNING) or (
                    data.load and data.load > 70
                ):
                    dot_color = _WARN

            c = w["dot_canvas"]
            c.delete("dot")
            c.create_oval(0, 0, 8, 8, fill=dot_color, outline="", tags="dot")

            # Position + angle
            pos   = data.position if data.position is not None else 0
            angle = (pos / MAX_POSITION) * 360 - 180
            w["pos_label"].configure(text=f"{pos} ({angle:.0f}\u00b0)")

            # Temperature
            temp = data.temperature or 0
            w["temp_label"].configure(
                text=f"{temp}\u00b0C",
                text_color=_CRIT if temp >= TEMP_CRITICAL else _WARN if temp >= TEMP_WARNING else _GOOD,
            )

            # Load
            load = data.load or 0
            w["load_label"].configure(
                text=f"{load}%",
                text_color=_CRIT if load >= 90 else _WARN if load >= 70 else _GOOD,
            )

            # Voltage
            volt = data.voltage or 0
            w["volt_label"].configure(text=f"{volt:.1f}V" if volt > 0 else "--V")

    def clear_data(self):
        for joint_idx, w in self.motor_widgets.items():
            w["pos_label"].configure(text="-- (--)")
            w["temp_label"].configure(text="--\u00b0C", text_color=FANUC_TEXT)
            w["load_label"].configure(text="--%",       text_color=FANUC_TEXT)
            w["volt_label"].configure(text="--V")
            c = w["dot_canvas"]
            c.delete("dot")
            c.create_oval(0, 0, 8, 8, fill=_IDLE, outline="", tags="dot")
