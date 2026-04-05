#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Services Module - Бизнес-логика приложения

Модуль содержит сервисы уровня бизнес-логики:
- RobotService - управление роботом
- KinematicsService - кинематические расчеты
- ProgramService - выполнение программ
"""

from .robot_service import RobotService
from .kinematics_service import KinematicsService
from .program_service import ProgramService

__all__ = [
    'RobotService',
    'KinematicsService',
    'ProgramService',
]
