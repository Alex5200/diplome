#!/usr/bin/env python3

"""
Services Module - Бизнес-логика приложения

Модуль содержит сервисы уровня бизнес-логики:
- RobotService - управление роботом
- KinematicsService - кинематические расчеты
- ProgramService - выполнение программ
"""

from .ai_provider import AIProvider
from .dataset_recorder_service import DatasetRecorderService
from .inference_service import InferenceService
from .kinematics_service import KinematicsService
from .program_service import ProgramService
from .robot_service import RobotService
from .vision_tracker_service import VisionTrackerService

__all__ = [
    "AIProvider",
    "DatasetRecorderService",
    "InferenceService",
    "KinematicsService",
    "ProgramService",
    "RobotService",
    "VisionTrackerService",
]
