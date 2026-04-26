#!/usr/bin/env python3
"""FANUC-Style Status Bar Widget."""

import time
import tkinter as tk

from app.config.constants import (
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_RED,
    FANUC_TEXT,
)


class FANUCStatusBar(tk.Frame):
    """
    Верхняя строка статуса в стиле FANUC iPendant.

    Показывает: режим | скорость % | координатная система | статус
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=FANUC_BG, height=36, **kwargs)
        self.pack_propagate(False)

        self.mode_label = tk.Label(
            self,
            text="JOINT",
            font=("SF Mono", 11, "bold"),
            bg=FANUC_BG,
            fg=FANUC_GREEN,
            padx=8,
        )
        self.mode_label.pack(side="left", padx=(10, 5))
        self._sep(self)

        self.speed_pct_label = tk.Label(
            self,
            text="50%",
            font=("Consolas", 11, "bold"),
            bg=FANUC_BG,
            fg=FANUC_ORANGE,
            padx=8,
        )
        self.speed_pct_label.pack(side="left", padx=5)
        self._sep(self)

        self.coord_label = tk.Label(
            self,
            text="WORLD",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_BLUE,
            padx=8,
        )
        self.coord_label.pack(side="left", padx=5)
        self._sep(self)

        self.prog_status_label = tk.Label(
            self,
            text="IDLE",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_GRAY,
            padx=8,
        )
        self.prog_status_label.pack(side="left", padx=5)

        self.clock_label = tk.Label(
            self,
            text="00:00:00",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_GRAY,
            padx=8,
        )
        self.clock_label.pack(side="right", padx=10)

        self.cycle_label = tk.Label(
            self,
            text="CYCLE: 0",
            font=("Consolas", 10),
            bg=FANUC_BG,
            fg=FANUC_GRAY,
            padx=8,
        )
        self.cycle_label.pack(side="right", padx=5)

        self.conn_canvas = tk.Canvas(self, width=14, height=14, bg=FANUC_BG, highlightthickness=0)
        self.conn_canvas.pack(side="right", padx=5)
        self.set_connected(False)
        self._update_clock()

    @staticmethod
    def _sep(parent):
        tk.Frame(parent, width=1, bg=FANUC_GRAY).pack(side="left", fill="y", padx=4, pady=6)

    def _update_clock(self):
        self.clock_label.config(text=time.strftime("%H:%M:%S"))
        self.after(1000, self._update_clock)

    def set_mode(self, mode: str):
        self.mode_label.config(text=mode.upper())

    def set_speed_pct(self, pct: int):
        color = FANUC_GREEN if pct >= 50 else FANUC_ORANGE if pct >= 20 else FANUC_RED
        self.speed_pct_label.config(text=f"{pct}%", fg=color)

    def set_prog_status(self, status: str):
        colors = {
            "IDLE": FANUC_GRAY,
            "RUN": FANUC_GREEN,
            "PAUSE": FANUC_ORANGE,
            "ABORT": FANUC_RED,
            "DONE": FANUC_BLUE,
        }
        self.prog_status_label.config(text=status, fg=colors.get(status, FANUC_TEXT))

    def set_connected(self, connected: bool):
        self.conn_canvas.delete("all")
        color = FANUC_GREEN if connected else FANUC_RED
        self.conn_canvas.create_oval(2, 2, 12, 12, fill=color, outline="")

    def set_cycle(self, count: int):
        self.cycle_label.config(text=f"CYCLE: {count}")
