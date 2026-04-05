#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interfaces Module - Абстрактные базовые классы

Определяет контракты для основных компонентов системы.
Используется для dependency injection и тестирования.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass


@dataclass
class MotorInfo:
    """Информация о моторе."""
    motor_id: int
    position: int
    temperature: float
    voltage: float
    current: float
    load: float
    moving: bool
    torque_enabled: bool


class IMotorController(ABC):
    """
    Интерфейс контроллера моторов.

    Определяет базовые операции для управления сервомоторами ST3215.
    """

    @abstractmethod
    def connect(self, device: str) -> bool:
        """
        Подключение к моторам.

        Args:
            device: Имя устройства (COM порт)

        Returns:
            True если успешно
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Отключение от моторов."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Проверка подключения."""
        pass

    @abstractmethod
    def scan_servos(self) -> List[int]:
        """
        Сканирование подключенных сервомоторов.

        Returns:
            Список найденных ID моторов
        """
        pass

    @abstractmethod
    def move_to_position(self, motor_id: int, position: int,
                         speed: int, acc: int) -> bool:
        """
        Движение мотора к позиции.

        Args:
            motor_id: ID мотора
            position: Целевая позиция (0-4095)
            speed: Скорость движения
            acc: Ускорение

        Returns:
            True если успешно
        """
        pass

    @abstractmethod
    def move_joint(self, joint_index: int, position: int,
                   speed: int, acc: int) -> bool:
        """
        Движение сустава робота.

        Args:
            joint_index: Индекс сустава (0-5)
            position: Целевая позиция
            speed: Скорость
            acc: Ускорение

        Returns:
            True если успешно
        """
        pass

    @abstractmethod
    def move_all_joints(self, positions: List[int], speed: int) -> bool:
        """
        Одновременное движение всех суставов.

        Args:
            positions: Список позиций для каждого сустава
            speed: Скорость движения

        Returns:
            True если успешно
        """
        pass

    @abstractmethod
    def toggle_torque(self, motor_id: int, enable: bool) -> bool:
        """
        Включение/выключение момента мотора.

        Args:
            motor_id: ID мотора
            enable: True для включения

        Returns:
            True если успешно
        """
        pass

    @abstractmethod
    def emergency_stop(self) -> None:
        """Экстренная остановка всех моторов."""
        pass

    @abstractmethod
    def read_motor_data(self, motor_id: int) -> Dict[str, Any]:
        """
        Чтение данных мотора.

        Args:
            motor_id: ID мотора

        Returns:
            Словарь с данными мотора
        """
        pass

    @abstractmethod
    def get_motor_id_for_joint(self, joint_index: int) -> int:
        """
        Получение ID мотора для сустава.

        Args:
            joint_index: Индекс сустава

        Returns:
            ID мотора
        """
        pass


class IMotorMonitor(ABC):
    """
    Интерфейс монитора моторов.

    Определяет операции для асинхронного мониторинга состояния моторов.
    """

    @abstractmethod
    def start(self, motor_ids: List[int]) -> None:
        """
        Запуск мониторинга.

        Args:
            motor_ids: Список ID моторов для мониторинга
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Остановка мониторинга."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Проверка статуса мониторинга."""
        pass

    @abstractmethod
    def get_data(self, motor_id: int) -> Optional[MotorInfo]:
        """
        Получение данных конкретного мотора.

        Args:
            motor_id: ID мотора

        Returns:
            Данные мотора или None
        """
        pass

    @abstractmethod
    def get_all_data(self) -> Dict[int, MotorInfo]:
        """
        Получение данных всех моторов.

        Returns:
            Словарь {motor_id: MotorInfo}
        """
        pass

    @abstractmethod
    def set_callback(self, callback: Callable[[Dict[int, MotorInfo]], None]) -> None:
        """
        Установка callback для обновлений данных.

        Args:
            callback: Функция обратного вызова
        """
        pass


class IService(ABC):
    """
    Базовый интерфейс сервиса.

    Все сервисы приложения должны реализовывать этот интерфейс.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Инициализация сервиса.

        Returns:
            True если успешно
        """
        pass

    @abstractmethod
    def start(self) -> None:
        """Запуск сервиса."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Остановка сервиса."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Проверка статуса сервиса."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Получение статуса сервиса.

        Returns:
            Словарь со статусом сервиса
        """
        pass
