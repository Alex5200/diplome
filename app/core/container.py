#!/usr/bin/env python3

"""
Dependency Injection Container

Контейнер для управления зависимостями приложения.
Поддерживает ленивую инициализацию, одиночные экземпляры и иерархию.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class ServiceDescriptor:
    """Описание сервиса в контейнере."""

    cls: type
    factory: Callable[[], Any] | None = None
    instance: Any | None = None
    dependencies: list = field(default_factory=list)
    is_singleton: bool = True
    is_initialized: bool = False


class Container:
    """
    Контейнер зависимостей (DI Container).

    Возможности:
    - Регистрация сервисов по классу или интерфейсу
    - Поддержка singleton и transient жизненных циклов
    - Автоматическое разрешение зависимостей
    - Ленивая инициализация сервисов

    Пример использования:
        container = Container()

        # Регистрация
        container.register('robot', RobotService)
        container.register('kinematics', KinematicsService)

        # Получение
        robot = container.get('robot')
        kinematics = container.get('kinematics')
    """

    def __init__(self):
        """Инициализация контейнера."""
        self._services: dict[str, ServiceDescriptor] = {}
        self._aliases: dict[str, str] = {}
        self._initialized = False

    def register(
        self,
        name: str,
        cls: type = None,
        factory: Callable = None,
        instance: Any = None,
        dependencies: list = None,
        is_singleton: bool = True,
    ) -> "Container":
        """
        Регистрация сервиса.

        Args:
            name: Имя сервиса для последующего получения
            cls: Класс сервиса (для создания экземпляра)
            factory: Фабрика для создания экземпляра
            instance: Готовый экземпляр (для existing instance)
            dependencies: Зависимости сервиса
            is_singleton: Одиночный экземпляр или новый каждый раз

        Returns:
            self для цепочки вызовов

        Raises:
            ValueError: Если не указан ни cls, ни factory, ни instance
        """
        if cls is None and factory is None and instance is None:
            raise ValueError("Must provide either cls, factory, or instance")

        self._services[name] = ServiceDescriptor(
            cls=cls,
            factory=factory,
            instance=instance,
            dependencies=dependencies or [],
            is_singleton=is_singleton,
        )

        return self

    def register_alias(self, alias: str, target: str) -> "Container":
        """
        Регистрация алиаса для сервиса.

        Args:
            alias: Новое имя
            target: Оригинальное имя сервиса

        Returns:
            self для цепочки вызовов
        """
        self._aliases[alias] = target
        return self

    def get(self, name: str) -> Any:
        """
        Получение сервиса из контейнера.

        Args:
            name: Имя сервиса

        Returns:
            Экземпляр сервиса

        Raises:
            KeyError: Если сервис не зарегистрирован
        """
        # Проверка алиасов
        if name in self._aliases:
            name = self._aliases[name]

        if name not in self._services:
            raise KeyError(f"Service '{name}' not registered")

        descriptor = self._services[name]

        # Если это singleton и уже создан
        if descriptor.is_singleton and descriptor.instance is not None:
            return descriptor.instance

        # Создание экземпляра
        instance = self._create_instance(descriptor)

        if descriptor.is_singleton:
            descriptor.instance = instance

        return instance

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Создание экземпляра сервиса."""
        # Если есть готовый instance
        if descriptor.instance is not None:
            return descriptor.instance

        # Если есть factory
        if descriptor.factory is not None:
            return descriptor.factory()

        # Если есть cls
        if descriptor.cls is not None:
            # Разрешение зависимостей
            kwargs = {}
            for dep_name in descriptor.dependencies:
                kwargs[dep_name] = self.get(dep_name)

            # Создание с зависимостями или без
            if kwargs:
                return self.cls(**kwargs)
            return self.cls()

        raise ValueError("Cannot create instance: no cls, factory, or instance")

    def get_optional(self, name: str, default: Any = None) -> Any:
        """
        Получение сервиса с значением по умолчанию.

        Args:
            name: Имя сервиса
            default: Значение по умолчанию

        Returns:
            Экземпляр сервиса или default
        """
        try:
            return self.get(name)
        except KeyError:
            return default

    def has(self, name: str) -> bool:
        """Проверка наличия сервиса."""
        return name in self._services or name in self._aliases

    def remove(self, name: str) -> bool:
        """
        Удаление сервиса из контейнера.

        Args:
            name: Имя сервиса

        Returns:
            True если сервис существовал
        """
        if name in self._aliases:
            del self._aliases[name]
            return True

        if name in self._services:
            del self._services[name]
            return True

        return False

    def clear(self) -> None:
        """Очистка всех сервисов."""
        self._services.clear()
        self._aliases.clear()

    def get_all(self) -> dict[str, Any]:
        """
        Получение всех сервисов.

        Returns:
            Словарь {name: instance}
        """
        return {name: self.get(name) for name in self._services}

    def initialize_all(self) -> None:
        """Инициализация всех singleton сервисов."""
        for name in self._services:
            if self._services[name].is_singleton:
                self.get(name)

    def __getitem__(self, name: str) -> Any:
        """Синтаксический сахар: container['service']."""
        return self.get(name)

    def __contains__(self, name: str) -> bool:
        """Проверка: 'service' in container."""
        return self.has(name)


# Глобальный контейнер приложения
_app_container: Container | None = None


def get_container() -> Container:
    """Получение глобального контейнера приложения."""
    global _app_container
    if _app_container is None:
        _app_container = Container()
    return _app_container


def reset_container() -> None:
    """Сброс глобального контейнера (для тестов)."""
    global _app_container
    _app_container = None
