#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base Service Module

Базовый класс для всех сервисов приложения.
Реализует общую логику управления жизненным циклом сервиса.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from .interfaces import IService
from .events import EventBus, event_bus


class BaseService(IService):
    """
    Базовый класс сервиса.

    Предоставляет:
    - Управление жизненным циклом (init/start/stop)
    - Встроенное логирование событий
    - Механизм состояния сервиса
    - Интеграцию с шиной событий

    Пример использования:
        class MotorService(BaseService):
            def _do_initialize(self):
                # Инициализация моторов
                pass

            def _do_start(self):
                # Запуск моторов
                pass

            def _do_stop(self):
                # Остановка моторов
                pass
    """

    def __init__(self, name: str):
        """
        Инициализация сервиса.

        Args:
            name: Имя сервиса
        """
        self._name = name
        self._state = "stopped"  # stopped, running, error
        self._error_message: Optional[str] = None
        self._started_at: Optional[datetime] = None
        self._event_bus = event_bus

    @property
    def name(self) -> str:
        """Имя сервиса."""
        return self._name

    @property
    def state(self) -> str:
        """Текущее состояние сервиса."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Проверка: запущен ли сервис."""
        return self._state == "running"

    def initialize(self) -> bool:
        """
        Инициализация сервиса.

        Returns:
            True если успешно
        """
        try:
            self._emit_event("service_initializing", {"service": self._name})
            result = self._do_initialize()
            if result:
                self._state = "initialized"
                self._emit_event("service_initialized", {"service": self._name})
            return result
        except Exception as e:
            self._state = "error"
            self._error_message = str(e)
            self._emit_event("service_error", {"service": self._name, "error": str(e)})
            return False

    def start(self) -> bool:
        """
        Запуск сервиса.

        Returns:
            True если успешно
        """
        if self._state not in ("initialized", "stopped"):
            return False

        try:
            self._emit_event("service_starting", {"service": self._name})
            self._do_start()
            self._state = "running"
            self._started_at = datetime.now()
            self._emit_event(
                "service_started",
                {"service": self._name, "started_at": self._started_at.isoformat()},
            )
            return True
        except Exception as e:
            self._state = "error"
            self._error_message = str(e)
            self._emit_event("service_error", {"service": self._name, "error": str(e)})
            return False

    def stop(self) -> None:
        """Остановка сервиса."""
        if self._state != "running":
            return

        try:
            self._emit_event("service_stopping", {"service": self._name})
            self._do_stop()
            self._state = "stopped"
            self._emit_event("service_stopped", {"service": self._name})
        except Exception as e:
            self._emit_event("service_error", {"service": self._name, "error": str(e)})

    def get_status(self) -> Dict[str, Any]:
        """
        Получение статуса сервиса.

        Returns:
            Словарь со статусом сервиса
        """
        status = {
            "name": self._name,
            "state": self._state,
            "is_running": self.is_running,
            "error_message": self._error_message,
        }

        if self._started_at:
            status["started_at"] = self._started_at.isoformat()
            status["uptime_seconds"] = (
                datetime.now() - self._started_at
            ).total_seconds()

        status.update(self._get_extra_status())
        return status

    def _emit_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """
        Отправка события в шину.

        Args:
            event_name: Имя события
            data: Данные события
        """
        self._event_bus.emit(event_name, data, source=self._name)

    # Методы для переопределения в подклассах

    def _do_initialize(self) -> bool:
        """
        Инициализация сервиса (переопределить в подклассе).

        Returns:
            True если успешно
        """
        return True

    def _do_start(self) -> None:
        """Запуск сервиса (переопределить в подклассе)."""
        pass

    def _do_stop(self) -> None:
        """Остановка сервиса (переопределить в подклассе)."""
        pass

    def _get_extra_status(self) -> Dict[str, Any]:
        """
        Дополнительные данные статуса (переопределить в подклассе).

        Returns:
            Словарь с дополнительными данными
        """
        return {}
