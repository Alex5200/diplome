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
from pathlib import Path

# Добавляем родительскую директорию в path для импорта st3215
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from app.views.main_window import RobotControlGUI


def main():
    """Точка входа приложения."""
    print("\n" + "=" * 60)
    print("  ST3215 Robot Control v7.0 — FANUC iPendant Style")
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
    app.mainloop()


if __name__ == '__main__':
    main()
