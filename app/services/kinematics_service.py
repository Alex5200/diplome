#!/usr/bin/env python3

"""
Kinematics Service Module

Сервис для кинематических расчетов.
Абстрагирует работу с прямой/обратной кинематикой.
"""

from dataclasses import dataclass
from typing import Any

from ..core.base_service import BaseService
from ..models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF


@dataclass
class KinematicsResult:
    """Результат кинематического расчета."""

    success: bool
    angles: list[float] | None = None
    position: tuple[float, float, float] | None = None
    error: float = 0.0
    message: str = ""


class KinematicsService(BaseService):
    """
    Сервис кинематических расчетов.

    Предоставляет API для:
    - Прямой кинематики (углы -> позиция)
    - Обратной кинематики (позиция -> углы)
    - Проверки досягаемости
    - Расчета траекторий
    """

    def __init__(self):
        """Инициализация сервиса."""
        super().__init__("KinematicsService")

        self._kinematics = RobotKinematics6DOF()
        self._ik_solver = InverseKinematics6DOF(self._kinematics)

        # Кэш последних результатов
        self._last_fk_result: KinematicsResult | None = None
        self._last_ik_result: KinematicsResult | None = None

    def _do_initialize(self) -> bool:
        """Инициализация сервиса."""
        self._emit_event(
            "kinematics_initialized", {"max_reach": self._kinematics.get_total_reach()}
        )
        return True

    def _get_extra_status(self) -> dict[str, Any]:
        """Дополнительный статус."""
        return {
            "max_reach": self._kinematics.get_total_reach(),
            "last_ik_success": self._last_ik_result.success if self._last_ik_result else None,
        }

    # ==================== Прямая кинематика ====================

    def forward_kinematics(self, angles: list[float]) -> KinematicsResult:
        """
        Расчет прямой кинематики.

        Args:
            angles: Список углов суставов в градусах

        Returns:
            Результат с позицией конечного эффектора
        """
        try:
            position = self._kinematics.get_end_effector_position(angles)
            result = KinematicsResult(success=True, position=position, error=0.0, message="OK")
            self._last_fk_result = result
            return result
        except Exception as e:
            result = KinematicsResult(success=False, message=str(e))
            self._last_fk_result = result
            return result

    def get_all_joint_positions(self, angles: list[float]) -> list[tuple[float, float, float]]:
        """
        Получение позиций всех суставов.

        Args:
            angles: Углы суставов

        Returns:
            Список позиций (x, y, z) для каждого сустава
        """
        return self._kinematics.get_all_joint_positions(angles)

    # ==================== Обратная кинематика ====================

    def inverse_kinematics(
        self, x: float, y: float, z: float, max_iterations: int = 300, tolerance: float = 1.0
    ) -> KinematicsResult:
        """
        Расчет обратной кинематики.

        Args:
            x, y, z: Целевая позиция в мм
            max_iterations: Максимум итераций
            tolerance: Допуск сходимости (мм)

        Returns:
            Результат с углами суставов
        """
        # Проверка досягаемости
        reach_check = self.check_reachability(x, y, z)
        if not reach_check.success:
            result = KinematicsResult(success=False, message=reach_check.message)
            self._last_ik_result = result
            return result

        # Решение IK
        angles = self._ik_solver.solve(x, y, z, max_iterations, tolerance)

        if angles is None:
            result = KinematicsResult(
                success=False, message=f"IK не сошлась для точки ({x:.1f}, {y:.1f}, {z:.1f})"
            )
            self._last_ik_result = result
            return result

        # Проверка точности
        actual_pos = self._kinematics.get_end_effector_position(angles)
        error = (
            (actual_pos[0] - x) ** 2 + (actual_pos[1] - y) ** 2 + (actual_pos[2] - z) ** 2
        ) ** 0.5

        result = KinematicsResult(
            success=True,
            angles=angles,
            position=actual_pos,
            error=error,
            message=f"Ошибка: {error:.2f} мм",
        )
        self._last_ik_result = result
        return result

    def check_reachability(self, x: float, y: float, z: float) -> KinematicsResult:
        """
        Проверка досягаемости точки.

        Args:
            x, y, z: Координаты точки

        Returns:
            Результат с информацией о досягаемости
        """
        distance = (x**2 + y**2 + z**2) ** 0.5
        max_reach = self._kinematics.get_total_reach()

        if distance > max_reach:
            return KinematicsResult(
                success=False,
                message=f"Точка вне досягаемости: {distance:.1f} > {max_reach:.1f} мм",
            )

        # Дополнительная проверка: минимальное расстояние
        min_reach = 20  # Минимальное расстояние от базы
        if distance < min_reach:
            return KinematicsResult(
                success=False,
                message=f"Точка слишком близко к базе: {distance:.1f} < {min_reach} мм",
            )

        return KinematicsResult(
            success=True, message=f"Точка достижима (расстояние: {distance:.1f} мм)"
        )

    # ==================== Утилиты ====================

    def get_link_lengths(self) -> dict[str, float]:
        """Получение длин звеньев."""
        return {
            "L0": self._kinematics.L0,
            "L1": self._kinematics.L1,
            "L2": self._kinematics.L2,
            "L3": self._kinematics.L3,
            "L4": self._kinematics.L4,
            "L5": self._kinematics.L5,
        }

    def get_max_reach(self) -> float:
        """Максимальная досягаемость."""
        return self._kinematics.get_total_reach()

    def get_workspace_bounds(self) -> tuple[float, float, float, float, float, float]:
        """Границы рабочей зоны."""
        return self._kinematics.get_workspace_bounds()

    def angle_to_position(self, angle_deg: float) -> int:
        """Конвертация угла в позицию мотора."""
        return RobotKinematics6DOF.angle_to_motor_position(angle_deg)

    def position_to_angle(self, position: int) -> float:
        """Конвертация позиции в угол."""
        return RobotKinematics6DOF.position_to_motor_angle(position)

    def get_last_ik_result(self) -> KinematicsResult | None:
        """Последний результат IK."""
        return self._last_ik_result

    def get_last_fk_result(self) -> KinematicsResult | None:
        """Последний результат FK."""
        return self._last_fk_result
