#!/usr/bin/env python3

"""
ST3215 Robot Control Application

Модульное приложение для управления роботом-манипулятором на основе сервомоторов ST3215.

Архитектура:
    - config: Константы и конфигурация
    - models: Модели данных
    - controllers: Логика управления моторами
    - views: GUI компоненты (Tkinter)
    - utils: Вспомогательные утилиты

Пример использования:
    from app.controllers import MotorController, MotorMonitor
    from app.models import MotorData

    controller = MotorController('COM3')
    controller.connect()
"""

__version__ = "6.1.0"
__author__ = "Alexandr Lyachov"

from app.config.constants import (
    BLOCK_COLORS,
    CONFIG_FILE,
    DEFAULT_ACC,
    DEFAULT_MOTOR_CONFIG,
    DEFAULT_MOTOR_MAPPING,
    DEFAULT_SPEED,
    JOINT_NAMES,
    KINEMA_COLORS,
    MAX_POSITION,
    MIN_POSITION,
    MONITOR_INTERVAL,
    PROGRAM_FILE,
    TEMP_CRITICAL,
    TEMP_WARNING,
)
from app.models.motor_data import MotorData, ProgramBlock

__all__ = [
    # Version
    "__version__",
    "__author__",
    # Constants
    "MIN_POSITION",
    "MAX_POSITION",
    "DEFAULT_SPEED",
    "DEFAULT_ACC",
    "MONITOR_INTERVAL",
    "TEMP_WARNING",
    "TEMP_CRITICAL",
    "CONFIG_FILE",
    "PROGRAM_FILE",
    "JOINT_NAMES",
    "DEFAULT_MOTOR_MAPPING",
    "DEFAULT_MOTOR_CONFIG",
    "BLOCK_COLORS",
    "KINEMA_COLORS",
    # Models
    "MotorData",
    "ProgramBlock",
]
