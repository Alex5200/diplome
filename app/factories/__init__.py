#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor Factory Module

Фабрика для создания и конфигурации моторов ST3215.
"""

from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from ..config.constants import DEFAULT_MOTOR_MAPPING, MAX_POSITION


@dataclass
class MotorConfig:
    """Конфигурация мотора."""
    motor_id: int
    name: str = ""
    min_position: int = 0
    max_position: int = MAX_POSITION
    inverted: bool = False
    initial_position: int = 2048
    speed_limit: int = 2400


class MotorFactory:
    """
    Фабрика для создания и конфигурации моторов ST3215.

    Предоставляет методы для:
    - Создания конфигурации мотора
    - Валидации параметров
    - Применения инверсии позиции

    Пример использования:
        factory = MotorFactory()
        config = factory.create_config(
            motor_id=1,
            name="Base Joint",
            inverted=True
        )
        position = factory.apply_inversion(2048, config.inverted)
    """

    def __init__(self):
        """Инициализация фабрики."""
        self._configs: Dict[int, MotorConfig] = {}

    def create_config(
        self,
        motor_id: int,
        name: str = "",
        min_position: int = 0,
        max_position: int = MAX_POSITION,
        inverted: bool = False,
        initial_position: int = 2048,
        speed_limit: int = 2400,
    ) -> MotorConfig:
        """
        Создание конфигурации мотора.

        Args:
            motor_id: ID мотора
            name: Название
            min_position: Минимальная позиция
            max_position: Максимальная позиция
            inverted: Инвертировать направление
            initial_position: Начальная позиция
            speed_limit: Ограничение скорости

        Returns:
            Конфигурация мотора

        Raises:
            ValueError: Если параметры невалидны
        """
        # Валидация
        if motor_id < 0:
            raise ValueError(f"motor_id должен быть >= 0, получен {motor_id}")

        if min_position < 0:
            raise ValueError(f"min_position должен быть >= 0")

        if max_position > MAX_POSITION:
            raise ValueError(f"max_position должен быть <= {MAX_POSITION}")

        if min_position > max_position:
            raise ValueError(
                f"min_position ({min_position}) > max_position ({max_position})"
            )

        if not (0 <= initial_position <= MAX_POSITION):
            raise ValueError(
                f"initial_position должен быть в диапазоне 0-{MAX_POSITION}"
            )

        config = MotorConfig(
            motor_id=motor_id,
            name=name or f"Motor {motor_id}",
            min_position=min_position,
            max_position=max_position,
            inverted=inverted,
            initial_position=initial_position,
            speed_limit=speed_limit,
        )

        self._configs[motor_id] = config
        return config

    def get_config(self, motor_id: int) -> Optional[MotorConfig]:
        """Получение конфигурации мотора."""
        return self._configs.get(motor_id)

    def get_all_configs(self) -> Dict[int, MotorConfig]:
        """Получение всех конфигураций."""
        return self._configs.copy()

    def apply_inversion(self, position: int, inverted: bool) -> int:
        """
        Применение инверсии к позиции.

        Args:
            position: Исходная позиция
            inverted: Инвертировать ли

        Returns:
            Позиция с учетом инверсии
        """
        if not inverted:
            return position
        return MAX_POSITION - position

    def position_to_angle(self, position: int, min_pos: int = 0,
                          max_pos: int = MAX_POSITION,
                          min_angle: float = -180.0,
                          max_angle: float = 180.0) -> float:
        """
        Конвертация позиции в угол.

        Args:
            position: Позиция мотора
            min_pos: Минимальная позиция для диапазона
            max_pos: Максимальная позиция
            min_angle: Минимальный угол
            max_angle: Максимальный угол

        Returns:
            Угол в градусах
        """
        position = max(min_pos, min(max_pos, position))
        normalized = (position - min_pos) / (max_pos - min_pos)
        return min_angle + normalized * (max_angle - min_angle)

    def angle_to_position(self, angle: float, min_pos: int = 0,
                          max_pos: int = MAX_POSITION,
                          min_angle: float = -180.0,
                          max_angle: float = 180.0) -> int:
        """
        Конвертация угла в позицию.

        Args:
            angle: Угол в градусах
            min_pos: Минимальная позиция
            max_pos: Максимальная позиция
            min_angle: Минимальный угол
            max_angle: Максимальный угол

        Returns:
            Позиция мотора
        """
        angle = max(min_angle, min(max_angle, angle))
        normalized = (angle - min_angle) / (max_angle - min_angle)
        position = int(min_pos + normalized * (max_pos - min_pos))
        return max(min_pos, min(max_pos, position))

    def create_from_mapping(self, mapping: Dict[str, Any]) -> Dict[int, MotorConfig]:
        """
        Создание конфигураций из соответствия моторов.

        Args:
            mapping: Соответствие {joint_X: {motor_id, name, inverted, ...}}

        Returns:
            Словарь {motor_id: MotorConfig}
        """
        configs = {}

        for joint_key, joint_data in mapping.items():
            motor_id = joint_data.get('motor_id')
            if motor_id is None:
                continue

            config = MotorConfig(
                motor_id=motor_id,
                name=joint_data.get('name', f"Motor {motor_id}"),
                min_position=joint_data.get('min_pos', 0),
                max_position=joint_data.get('max_pos', MAX_POSITION),
                inverted=joint_data.get('inverted', False),
            )
            configs[motor_id] = config

        self._configs = configs
        return configs

    def clear_configs(self) -> None:
        """Очистка всех конфигураций."""
        self._configs.clear()


# Глобальный экземпляр фабрики
_motor_factory: Optional[MotorFactory] = None


def get_motor_factory() -> MotorFactory:
    """Получение глобального экземпляра фабрики."""
    global _motor_factory
    if _motor_factory is None:
        _motor_factory = MotorFactory()
    return _motor_factory
