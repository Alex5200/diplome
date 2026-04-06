#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Event System Module

Система событий для слабой связи между компонентами приложения.
Позволяет компонентам общаться без прямых зависимостей.

Пример использования:
    # Подписка на событие
    EventBus.on('motor_connected', callback)

    # Отправка события
    EventBus.emit('motor_connected', {'port': 'COM3'})
"""

import threading
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import weakref


@dataclass
class Event:
    """
    Базовый класс события.

    Attributes:
        name: Имя события
        data: Данные события (словарь)
        timestamp: Время создания события
        source: Источник события (имя компонента)
    """

    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""

    def __str__(self) -> str:
        return f"Event('{self.name}', source='{self.source}', data={self.data})"


class EventBus:
    """
    Шина событий для связи между компонентами.

    Реализует паттерн Publish-Subscribe с поддержкой:
    - Слабых ссылок на подписчиков (автоматическая очистка)
    - Фильтрации событий по имени
    - Асинхронной доставки
    - Приоритетов подписчиков

    Пример использования:
        def on_motor_connected(data):
            print(f"Connected to {data['port']}")

        EventBus.on('motor_connected', on_motor_connected)
        EventBus.emit('motor_connected', {'port': 'COM3'})
    """

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._subscribers: Dict[str, List[weakref.WeakMethod]] = {}
        self._lock = threading.RLock()
        self._event_history: List[Event] = []
        self._max_history = 100
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "EventBus":
        """Получить экземпляр шины событий."""
        return cls()

    def on(
        self,
        event_name: str,
        callback: Callable[[Dict[str, Any]], None],
        priority: int = 0,
    ) -> None:
        """
        Подписка на событие.

        Args:
            event_name: Имя события для подписки
            callback: Функция обратного вызова, принимающая dict с данными
            priority: Приоритет подписчика (чем выше, тем раньше вызывается)
        """
        with self._lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []

            # Сохраняем callback с приоритетом
            self._subscribers[event_name].append(
                {
                    "callback": weakref.WeakMethod(callback)
                    if hasattr(callback, "__self__")
                    else callback,
                    "priority": priority,
                    "is_method": hasattr(callback, "__self__"),
                }
            )

            # Сортируем по приоритету
            self._subscribers[event_name].sort(
                key=lambda x: x["priority"], reverse=True
            )

    def off(self, event_name: str, callback: Callable = None) -> None:
        """
        Отписка от события.

        Args:
            event_name: Имя события
            callback: Конкретный callback для отписки (None для всех)
        """
        with self._lock:
            if event_name not in self._subscribers:
                return

            if callback is None:
                del self._subscribers[event_name]
            else:
                self._subscribers[event_name] = [
                    sub
                    for sub in self._subscribers[event_name]
                    if sub["callback"] != callback
                ]

    def emit(
        self, event_name: str, data: Dict[str, Any] = None, source: str = ""
    ) -> Event:
        """
        Отправка события всем подписчикам.

        Args:
            event_name: Имя события
            data: Данные события
            source: Источник события

        Returns:
            Созданное событие
        """
        event = Event(
            name=event_name, data=data or {}, source=source, timestamp=datetime.now()
        )

        # Сохраняем в историю
        self._add_to_history(event)

        # Уведомляем подписчиков
        self._notify_subscribers(event)

        return event

    def _add_to_history(self, event: Event) -> None:
        """Добавление события в историю."""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

    def _notify_subscribers(self, event: Event) -> None:
        """Уведомление подписчиков."""
        with self._lock:
            if event.name not in self._subscribers:
                return

            # Копируем список для безопасной итерации
            subscribers = self._subscribers[event.name].copy()

        for sub in subscribers:
            try:
                if sub["is_method"]:
                    callback = sub["callback"]()
                    if callback is not None:
                        callback(event.data)
                else:
                    sub["callback"](event.data)
            except ReferenceError:
                pass  # Слабая ссылка уже мертва
            except Exception as e:
                print(f"⚠️ Error in event callback for '{event.name}': {e}")

    def clear_history(self) -> None:
        """Очистка истории событий."""
        with self._lock:
            self._event_history.clear()

    def get_history(self, event_name: str = None, limit: int = 50) -> List[Event]:
        """
        Получение истории событий.

        Args:
            event_name: Фильтр по имени события (None для всех)
            limit: Максимальное количество событий

        Returns:
            Список событий
        """
        with self._lock:
            if event_name:
                events = [e for e in self._event_history if e.name == event_name]
            else:
                events = self._event_history.copy()

            return events[-limit:]

    def cleanup(self) -> None:
        """Очистка мертвых ссылок."""
        with self._lock:
            for event_name in list(self._subscribers.keys()):
                self._subscribers[event_name] = [
                    sub
                    for sub in self._subscribers[event_name]
                    if not sub["is_method"] or sub["callback"]() is not None
                ]
                if not self._subscribers[event_name]:
                    del self._subscribers[event_name]


# Глобальный экземпляр
event_bus = EventBus()
