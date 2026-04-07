#!/usr/bin/env python3
"""Alarm History Panel — история аварий/предупреждений в стиле FANUC."""

import time
import tkinter as tk
from tkinter import ttk

from app.config.constants import (
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
)


class AlarmHistoryPanel(ttk.Frame):
    """Панель истории аварий/предупреждений в стиле FANUC."""

    def __init__(self, parent):
        super().__init__(parent)
        self.alarms: list[dict] = []
        self._create_widgets()

    def _create_widgets(self):
        header = tk.Frame(self, bg=FANUC_PANEL)
        header.pack(fill="x")
        tk.Label(header, text="ALARM HISTORY", font=("Consolas", 14, "bold"),
                 bg=FANUC_PANEL, fg=FANUC_RED).pack(side="left", padx=10, pady=5)
        tk.Button(header, text="CLEAR", font=("Arial", 9, "bold"), bg=FANUC_ORANGE,
                  fg=FANUC_TEXT, bd=0, padx=10, pady=3,
                  command=self._clear).pack(side="right", padx=10, pady=5)

        columns = ("time", "level", "message")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        self.tree.heading("time", text="Time")
        self.tree.heading("level", text="Level")
        self.tree.heading("message", text="Message")
        self.tree.column("time", width=100)
        self.tree.column("level", width=80)
        self.tree.column("message", width=500)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

    def add_alarm(self, level: str, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.alarms.insert(0, {"time": timestamp, "level": level, "message": message})
        if len(self.alarms) > 500:
            self.alarms = self.alarms[:500]
        tag = "error" if level == "ERROR" else "warning" if level == "WARNING" else "info"
        self.tree.insert("", 0, values=(timestamp, level, message), tags=(tag,))
        self.tree.tag_configure("error", foreground=FANUC_RED)
        self.tree.tag_configure("warning", foreground=FANUC_ORANGE)
        self.tree.tag_configure("info", foreground=FANUC_TEXT)

    def _clear(self):
        self.alarms.clear()
        self.tree.delete(*self.tree.get_children())
