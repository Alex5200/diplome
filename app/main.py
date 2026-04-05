#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ST3215 Robot Control Application
Главный файл запуска приложения

Версия: 7.0.0
Автор: Alexandr Lyachov

Описание:
    Модульное приложение для управления роботом-манипулятором
    на основе сервомоторов ST3215 с FANUC iPendant-стилем GUI.

Функции:
    - FANUC-стиль интерфейс (темная тема, статус-бар, боковая панель)
    - Настройка соответствия моторов суставам
    - 3D визуализация прямой кинематики (DH)
    - Обратная кинематика (Damped Least Squares)
    - Позиционные регистры (PR) с записью/воспроизведением
    - Teach Pendant — обучение траекториям
    - Блочное программирование движений
    - Асинхронный мониторинг моторов
    - Speed Override (1-100%)
    - История аварий (Alarm Log)
    - Jogging управление (Joint/Cartesian)

Пример запуска:
    python -m app.main
    или
    python app/main.py
"""

import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path

# Добавляем родительскую директорию в path для импорта st3215
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from app.views.main_window import RobotControlGUI
from app.config.constants import (
    LIGHT_BG, LIGHT_PANEL, LIGHT_TEXT, LIGHT_TEXT2, LIGHT_BORDER,
    LIGHT_GREEN, LIGHT_ORANGE, LIGHT_RED, LIGHT_BLUE, LIGHT_ACCENT,
    LIGHT_HOVER, LIGHT_SELECT,
)


def apply_light_theme(root: tk.Tk) -> None:
    """Применяет светлую тему ко всем ttk и tk виджетам."""
    # ── Базовый ttk-стиль ──────────────────────────────────────
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".",
        background=LIGHT_BG,
        foreground=LIGHT_TEXT,
        fieldbackground=LIGHT_PANEL,
        bordercolor=LIGHT_BORDER,
        troughcolor=LIGHT_HOVER,
        selectbackground=LIGHT_SELECT,
        selectforeground=LIGHT_TEXT,
        font=("Segoe UI", 10),
    )

    style.configure("TFrame",    background=LIGHT_BG)
    style.configure("TLabel",    background=LIGHT_BG, foreground=LIGHT_TEXT)
    style.configure("TLabelframe",
        background=LIGHT_BG,
        foreground=LIGHT_TEXT2,
        bordercolor=LIGHT_BORDER,
        relief="groove",
    )
    style.configure("TLabelframe.Label",
        background=LIGHT_BG,
        foreground=LIGHT_ACCENT,
        font=("Segoe UI", 9, "bold"),
    )

    style.configure("TNotebook",
        background=LIGHT_BG,
        bordercolor=LIGHT_BORDER,
        tabmargins=[2, 5, 2, 0],
    )
    style.configure("TNotebook.Tab",
        background=LIGHT_HOVER,
        foreground=LIGHT_TEXT2,
        padding=[12, 5],
        font=("Segoe UI", 9),
    )
    style.map("TNotebook.Tab",
        background=[("selected", LIGHT_PANEL)],
        foreground=[("selected", LIGHT_ACCENT)],
        expand=[("selected", [1, 1, 1, 0])],
    )

    style.configure("TButton",
        background=LIGHT_PANEL,
        foreground=LIGHT_TEXT,
        bordercolor=LIGHT_BORDER,
        relief="flat",
        padding=[10, 5],
        font=("Segoe UI", 9),
    )
    style.map("TButton",
        background=[("active", LIGHT_HOVER), ("pressed", LIGHT_SELECT)],
    )

    style.configure("Accent.TButton",
        background=LIGHT_ACCENT,
        foreground="#ffffff",
        font=("Segoe UI", 9, "bold"),
    )
    style.map("Accent.TButton",
        background=[("active", LIGHT_BLUE)],
    )

    style.configure("Danger.TButton",
        background=LIGHT_RED,
        foreground="#ffffff",
        font=("Segoe UI", 9, "bold"),
    )
    style.map("Danger.TButton",
        background=[("active", "#9a0007")],
    )

    style.configure("TEntry",
        fieldbackground=LIGHT_PANEL,
        foreground=LIGHT_TEXT,
        bordercolor=LIGHT_BORDER,
        insertcolor=LIGHT_TEXT,
    )
    style.configure("TSpinbox",
        fieldbackground=LIGHT_PANEL,
        foreground=LIGHT_TEXT,
        bordercolor=LIGHT_BORDER,
        arrowcolor=LIGHT_TEXT2,
    )
    style.configure("TCombobox",
        fieldbackground=LIGHT_PANEL,
        foreground=LIGHT_TEXT,
        selectbackground=LIGHT_SELECT,
        arrowcolor=LIGHT_TEXT2,
    )
    style.configure("TScrollbar",
        background=LIGHT_HOVER,
        troughcolor=LIGHT_BG,
        arrowcolor=LIGHT_TEXT2,
        bordercolor=LIGHT_BORDER,
    )
    style.configure("TScale",
        background=LIGHT_BG,
        troughcolor=LIGHT_HOVER,
        sliderrelief="flat",
    )
    style.configure("TCheckbutton",
        background=LIGHT_BG,
        foreground=LIGHT_TEXT,
        indicatorcolor=LIGHT_PANEL,
        indicatordiameter=14,
    )
    style.configure("TRadiobutton",
        background=LIGHT_BG,
        foreground=LIGHT_TEXT,
    )
    style.configure("TSeparator", background=LIGHT_BORDER)
    style.configure("TProgressbar",
        troughcolor=LIGHT_HOVER,
        background=LIGHT_ACCENT,
    )

    # ── Глобальные tk-опции (tk.Frame / tk.Label / tk.Text и пр.) ──
    root.option_add("*Background",       LIGHT_BG)
    root.option_add("*Foreground",       LIGHT_TEXT)
    root.option_add("*Font",             "Segoe\\ UI 10")
    root.option_add("*Entry.Background", LIGHT_PANEL)
    root.option_add("*Text.Background",  LIGHT_PANEL)
    root.option_add("*Text.Foreground",  LIGHT_TEXT)
    root.option_add("*Listbox.Background",       LIGHT_PANEL)
    root.option_add("*Listbox.Foreground",       LIGHT_TEXT)
    root.option_add("*Listbox.SelectBackground", LIGHT_SELECT)
    root.option_add("*Listbox.SelectForeground", LIGHT_TEXT)
    root.option_add("*Button.Background", LIGHT_PANEL)
    root.option_add("*Button.Foreground", LIGHT_TEXT)
    root.option_add("*Button.Relief",     "flat")


def main():
    """Точка входа приложения."""
    print("\n" + "=" * 60)
    print("  ST3215 Robot Control v7.0 — Light Theme")
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
    apply_light_theme(app)
    app.configure(bg=LIGHT_BG)
    app.mainloop()


if __name__ == '__main__':
    main()
