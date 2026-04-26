#!/usr/bin/env python3
"""
Reward Functions — функции наград для обучения с подкреплением.

Доступные функции:
    DistanceReward    — награда по расстоянию до цели (основная для манипулятора)
    SmoothMotionReward— штраф за рывки/дёрганые движения
    PickPlaceReward   — награда за pick-and-place задачи
    VisionReward      — награда на основе DetectionResult (связь с ML vision)
    CompositeReward   — комбинация нескольких функций с весами

TDD: app/tests/test_rl_training.py::TestRewards
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

# ──────────────────── Базовый класс ────────────────────


class BaseReward(ABC):
    """Абстрактная функция награды."""

    @abstractmethod
    def compute(self, state: dict[str, Any]) -> float:
        """
        Вычислить награду.

        Args:
            state: словарь состояния среды, содержит:
                - "ee_pos": np.ndarray[3]  — позиция end-effector (x,y,z мм)
                - "target_pos": np.ndarray[3]  — позиция цели
                - "joint_angles": np.ndarray[6]  — углы суставов (градусы)
                - "prev_joint_angles": np.ndarray[6]  — предыдущие углы
                - "gripper_state": bool  — открыт/закрыт
                - "object_grasped": bool  — объект захвачен
                - "object_pos": np.ndarray[3]  — позиция объекта
                - "detection": DetectionResult | None  — результат vision

        Returns:
            float — скалярная награда
        """
        ...

    def __add__(self, other: BaseReward) -> CompositeReward:
        return CompositeReward([(1.0, self), (1.0, other)])

    def __mul__(self, weight: float) -> WeightedReward:
        return WeightedReward(self, weight)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


@dataclass
class WeightedReward(BaseReward):
    """Взвешенная функция награды."""

    reward_fn: BaseReward
    weight: float

    def compute(self, state: dict[str, Any]) -> float:
        return self.weight * self.reward_fn.compute(state)


# ──────────────────── DistanceReward ────────────────────


class DistanceReward(BaseReward):
    """
    Награда на основе расстояния end-effector до цели.

    r = exp(-k * distance) * scale  — гауссова награда

    Максимум = scale когда distance = 0.
    Минимум → 0 на больших расстояниях.

    Дополнительно:
        - Бонус при достижении цели (< threshold)
        - Штраф за выход за пределы рабочей зоны
    """

    def __init__(
        self,
        scale: float = 1.0,
        sharpness: float = 0.01,  # k в exp(-k * dist^2)
        success_threshold_mm: float = 20.0,
        success_bonus: float = 10.0,
        workspace_radius_mm: float = 400.0,
        workspace_penalty: float = -5.0,
    ):
        self.scale = scale
        self.sharpness = sharpness
        self.success_threshold = success_threshold_mm
        self.success_bonus = success_bonus
        self.workspace_radius = workspace_radius_mm
        self.workspace_penalty = workspace_penalty

    def compute(self, state: dict[str, Any]) -> float:
        ee_pos = np.asarray(state.get("ee_pos", [0, 0, 0]), dtype=float)
        target = np.asarray(state.get("target_pos", [0, 0, 200]), dtype=float)

        dist = float(np.linalg.norm(ee_pos - target))

        # Гауссова награда приближения
        reward = self.scale * math.exp(-self.sharpness * dist)

        # Бонус успеха
        if dist < self.success_threshold:
            reward += self.success_bonus

        # Штраф выхода из рабочей зоны
        if float(np.linalg.norm(ee_pos)) > self.workspace_radius:
            reward += self.workspace_penalty

        return reward

    def is_success(self, state: dict[str, Any]) -> bool:
        ee_pos = np.asarray(state.get("ee_pos", [0, 0, 0]), dtype=float)
        target = np.asarray(state.get("target_pos", [0, 0, 200]), dtype=float)
        return float(np.linalg.norm(ee_pos - target)) < self.success_threshold


# ──────────────────── SmoothMotionReward ────────────────────


class SmoothMotionReward(BaseReward):
    """
    Штраф за рывки и дёрганые движения.

    Пенализирует большие изменения углов суставов между шагами.
    Поощряет плавную траекторию.

    r = -k * ||Δangles||²
    """

    def __init__(
        self,
        smoothness_weight: float = 0.1,
        joint_limit_penalty: float = -2.0,
        joint_limit_deg: float = 150.0,
    ):
        self.smoothness_weight = smoothness_weight
        self.joint_limit_penalty = joint_limit_penalty
        self.joint_limit_deg = joint_limit_deg

    def compute(self, state: dict[str, Any]) -> float:
        angles = np.asarray(state.get("joint_angles", np.zeros(6)), dtype=float)
        prev = np.asarray(state.get("prev_joint_angles", angles), dtype=float)

        # Штраф за рывки
        delta = angles - prev
        smoothness_penalty = -self.smoothness_weight * float(np.sum(delta**2))

        # Штраф за превышение лимитов суставов
        limit_penalty = 0.0
        for angle in angles:
            if abs(angle) > self.joint_limit_deg:
                limit_penalty += self.joint_limit_penalty

        return smoothness_penalty + limit_penalty


# ──────────────────── PickPlaceReward ────────────────────


class PickPlaceReward(BaseReward):
    """
    Награда для задачи pick-and-place.

    Фазы:
        1. APPROACH  — приближение к объекту  (+distance reward к объекту)
        2. GRASP     — захват объекта          (+grasp bonus)
        3. LIFT      — подъём объекта          (+height reward)
        4. TRANSPORT — перенос к цели          (+distance reward к цели)
        5. PLACE     — размещение              (+place bonus)

    Награды:
        approach_reward  — по расстоянию до объекта
        grasp_bonus      — за захват
        lift_reward      — за высоту подъёма (z объекта)
        place_bonus      — за размещение в цели
        drop_penalty     — штраф за роняние объекта
    """

    # Фазы задачи
    APPROACH = "approach"
    GRASP = "grasp"
    LIFT = "lift"
    TRANSPORT = "transport"
    PLACE = "place"

    def __init__(
        self,
        approach_scale: float = 0.5,
        grasp_bonus: float = 5.0,
        lift_scale: float = 0.3,
        transport_scale: float = 1.0,
        place_bonus: float = 20.0,
        drop_penalty: float = -5.0,
        grasp_threshold_mm: float = 30.0,
        place_threshold_mm: float = 25.0,
    ):
        self.approach_scale = approach_scale
        self.grasp_bonus = grasp_bonus
        self.lift_scale = lift_scale
        self.transport_scale = transport_scale
        self.place_bonus = place_bonus
        self.drop_penalty = drop_penalty
        self.grasp_threshold = grasp_threshold_mm
        self.place_threshold = place_threshold_mm

        self._prev_grasped = False

    def compute(self, state: dict[str, Any]) -> float:
        ee_pos = np.asarray(state.get("ee_pos", [0, 0, 0]), dtype=float)
        obj_pos = np.asarray(state.get("object_pos", [100, 0, 0]), dtype=float)
        target = np.asarray(state.get("target_pos", [0, 100, 0]), dtype=float)
        grasped: bool = state.get("object_grasped", False)

        reward = 0.0

        if not grasped:
            # Фаза APPROACH — приближение к объекту
            dist_to_obj = float(np.linalg.norm(ee_pos - obj_pos))
            reward += self.approach_scale * math.exp(-0.01 * dist_to_obj)

            # Бонус за захват
            if dist_to_obj < self.grasp_threshold and state.get("gripper_state") is False:
                reward += self.grasp_bonus

        else:
            # Объект в захвате
            if not self._prev_grasped:
                # Только что схватили
                reward += self.grasp_bonus

            # Фаза LIFT — высота подъёма
            lift_height = obj_pos[2] - 0.0  # высота над столом
            reward += self.lift_scale * max(0.0, lift_height / 100.0)

            # Фаза TRANSPORT — перенос к цели
            dist_to_target = float(np.linalg.norm(obj_pos - target))
            reward += self.transport_scale * math.exp(-0.01 * dist_to_target)

            # Бонус размещения
            if dist_to_target < self.place_threshold:
                reward += self.place_bonus

        # Штраф за роняние
        if self._prev_grasped and not grasped:
            dist_to_target = float(np.linalg.norm(obj_pos - target))
            if dist_to_target > self.place_threshold:
                reward += self.drop_penalty

        self._prev_grasped = grasped
        return reward

    def reset(self) -> None:
        """Сбросить состояние между эпизодами."""
        self._prev_grasped = False


# ──────────────────── VisionReward ────────────────────


class VisionReward(BaseReward):
    """
    Награда на основе результатов vision (DetectionResult).

    Связывает ML-трекер с RL-обучением:
        - Объект обнаружен и по центру → высокая награда
        - Объект обнаружен, но смещён → меньшая награда
        - Объект не обнаружен → штраф

    Применение: обучение робота смотреть на объект и центрировать его в кадре.
    """

    def __init__(
        self,
        center_reward: float = 1.0,
        detection_reward: float = 0.3,
        no_detection_penalty: float = -0.5,
        center_threshold: float = 0.05,  # нормализованное расстояние от центра
    ):
        self.center_reward = center_reward
        self.detection_reward = detection_reward
        self.no_detection_penalty = no_detection_penalty
        self.center_threshold = center_threshold

    def compute(self, state: dict[str, Any]) -> float:
        detection = state.get("detection")

        if detection is None or not detection.found:
            return self.no_detection_penalty

        # Отклонение от центра кадра
        err_x = detection.cx - 0.5
        err_y = detection.cy - 0.5
        center_dist = math.sqrt(err_x**2 + err_y**2)

        base = self.detection_reward
        if center_dist < self.center_threshold:
            base += self.center_reward

        # Непрерывная награда за центрирование
        centering = self.center_reward * math.exp(-20.0 * center_dist)
        return base + centering


# ──────────────────── CompositeReward ────────────────────


class CompositeReward(BaseReward):
    """
    Комбинация нескольких функций наград с весами.

    Пример:
        reward = CompositeReward([
            (1.0,  DistanceReward(scale=1.0)),
            (0.1,  SmoothMotionReward()),
            (0.5,  PickPlaceReward()),
        ])
        r = reward.compute(state)

    Или через операторы:
        reward = DistanceReward() * 1.0 + SmoothMotionReward() * 0.1
    """

    def __init__(self, components: list[tuple[float, BaseReward]] | None = None):
        self._components: list[tuple[float, BaseReward]] = components or []

    def add(self, reward_fn: BaseReward, weight: float = 1.0) -> CompositeReward:
        """Добавить функцию награды с весом."""
        self._components.append((weight, reward_fn))
        return self

    def compute(self, state: dict[str, Any]) -> float:
        total = 0.0
        for weight, fn in self._components:
            total += weight * fn.compute(state)
        return total

    def reset(self) -> None:
        """Сбросить stateful компоненты (например PickPlaceReward)."""
        for _, fn in self._components:
            if hasattr(fn, "reset"):
                fn.reset()

    def __repr__(self) -> str:
        parts = [f"{w}*{fn}" for w, fn in self._components]
        return f"CompositeReward([{', '.join(parts)}])"
