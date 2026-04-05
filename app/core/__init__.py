#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Core Module - Базовые абстракции и инфраструктура

Модуль содержит базовые классы и интерфейсы для всей архитектуры:
- Event system для слабой связи компонентов
- Базовые абстракции для сервисов
- Интерфейсы для контроллеров
- DI контейнер для управления зависимостями
"""

from .events import Event, EventBus, event_bus
from .interfaces import IMotorController, IMotorMonitor, IService
from .base_service import BaseService
from .container import Container, get_container, reset_container

__all__ = [
    # Events
    'Event',
    'EventBus',
    'event_bus',
    # Interfaces
    'IMotorController',
    'IMotorMonitor',
    'IService',
    # Base classes
    'BaseService',
    # DI Container
    'Container',
    'get_container',
    'reset_container',
]
