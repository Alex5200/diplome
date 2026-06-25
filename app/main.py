#!/usr/bin/env python3
"""
ST3215 Robot Control Application
Главный файл запуска приложения — CustomTkinter edition

Версия: 8.0.0
Автор: Alexandr Lyachov
"""

import sys
from pathlib import Path

# Добавляем родительскую директорию в path
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# ── CTk must be configured BEFORE any tk/ctk import ────────────────────────
from app.style import config_styles, setup_ctk

setup_ctk()

# ── Patch CTkScrollableFrame for CustomTkinter 5.2.2 mouse-wheel crash ────
import customtkinter as ctk

_orig_check = ctk.CTkScrollableFrame.check_if_master_is_canvas


def _patched_check(self, widget):
    if isinstance(widget, str):
        return False
    try:
        return _orig_check(self, widget)
    except AttributeError:
        return False


ctk.CTkScrollableFrame.check_if_master_is_canvas = _patched_check

# ── Now safe to import the rest ─────────────────────────────────────────────
from app.views.main_window import RobotControlGUI


def main():
    print("\n" + "=" * 60)
    print("  ST3215 Robot Control v8.0 — CustomTkinter UI")
    print("=" * 60)
    print("  Tabs: Dashboard | Jog | 3D View | Registers |")
    print("        Teach | Program | Setup | XYZ | Alarms")
    print("-" * 60)
    print("  Shortcuts:")
    print("    Ctrl+1..6  Select joint")
    print("    Arrows     Jog selected joint")
    print("    +/-        Speed override")
    print("    Ctrl+S     Save config")
    print("    F5         Run program")
    print("    Escape     Emergency stop")
    print("=" * 60)

    app = RobotControlGUI()
    config_styles(app)   # configure ttk styles for Treeview / Spinbox etc.
    app.mainloop()


if __name__ == "__main__":
    main()
