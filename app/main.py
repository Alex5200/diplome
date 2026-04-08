#!/usr/bin/env python3

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
from pathlib import Path
from tkinter import ttk

from style import config_styles

# Добавляем родительскую директорию в path для импорта st3215
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from config.constants import (
    LIGHT_ACCENT,
    LIGHT_BG,
    LIGHT_BLUE,
    LIGHT_BORDER,
    LIGHT_HOVER,
    LIGHT_PANEL,
    LIGHT_RED,
    LIGHT_SELECT,
    LIGHT_TEXT,
    LIGHT_TEXT2,
)

from app.views.main_window import RobotControlGUI


def apply_light_theme(root: tk.Tk) -> None:
    """Применяет светлую тему ко всем ttk и tk виджетам."""
    # ── Базовый ttk-стиль ──────────────────────────────────────
    style = config_styles(root)
    # ── Глобальные tk-опции (tk.Frame / tk.Label / tk.Text и пр.) ──
    root.option_add("*Background", LIGHT_BG)
    root.option_add("*Foreground", LIGHT_TEXT)
    root.option_add("*Font", "Segoe\\ UI 10")
    root.option_add("*Entry.Background", LIGHT_PANEL)
    root.option_add("*Text.Background", LIGHT_PANEL)
    root.option_add("*Text.Foreground", LIGHT_TEXT)
    root.option_add("*Listbox.Background", LIGHT_PANEL)
    root.option_add("*Listbox.Foreground", LIGHT_TEXT)
    root.option_add("*Listbox.SelectBackground", LIGHT_SELECT)
    root.option_add("*Listbox.SelectForeground", LIGHT_TEXT)
    root.option_add("*Button.Background", LIGHT_PANEL)
    root.option_add("*Button.Foreground", LIGHT_TEXT)
    root.option_add("*Button.Relief", "flat")


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


if __name__ == "__main__":
    main()
