#!/usr/bin/env python3

"""
Services Module - Бизнес-логика приложения

Модуль содержит сервисы уровня бизнес-логики:
- RobotService - управление роботом
- KinematicsService - кинематические расчеты
- ProgramService - выполнение программ
"""

from .kinematics_service import KinematicsService
from .program_service import ProgramService
from .robot_service import RobotService

__all__ = [
    "KinematicsService",
    "ProgramService",
    "RobotService",
]
