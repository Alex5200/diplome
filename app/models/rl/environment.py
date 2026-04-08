#!/usr/bin/env python3
"""
RobotArmEnv — Gym-совместимая среда для 6-DOF манипулятора.

Совместима с:
    - OpenAI Gymnasium (gymnasium.Env)
    - Stable-Baselines3
    - Нашим BaseRLAgent

Observation space (18 float32):
    [0:6]   — текущие углы суставов (нормализованные -1..+1)
    [6:9]   — позиция end-effector (нормализованная)
    [9:12]  — позиция цели (нормализованная)
    [12:15] — позиция объекта (нормализованная)
    [15]    — gripper state (0 или 1)
    [16]    — объект захвачен (0 или 1)
    [17]    — расстояние до цели (нормализованное)

Action space (7 float32):
    [0:6]   — дельты углов суставов (-1..+1, масштабируются на max_delta_deg)
    [6]     — команда gripper (-1=закрыть, +1=открыть)

TDD: app/tests/test_rl_training.py::TestRobotArmEnv
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .rewards import BaseReward, CompositeReward, DistanceReward, SmoothMotionReward

logger = logging.getLogger(__name__)

OBS_DIM = 18
ACTION_DIM = 7


@dataclass
class RobotArmConfig:
    """Конфигурация среды RobotArmEnv."""

    # Физика
    max_delta_deg: float = 10.0  # макс. изменение угла за шаг (градусы)
    joint_limit_deg: float = 150.0  # лимит суставов
    workspace_radius_mm: float = 350.0  # радиус рабочей зоны

    # Задача
    success_threshold_mm: float = 20.0  # дистанция для признания успеха
    max_steps: int = 200  # макс. шагов в эпизоде

    # Длины звеньев (мм) — совпадают с RobotKinematics6DOF
    L1: float = 104.0
    L2: float = 95.0
    L3: float = 34.0
    L4: float = 35.0

    # Рандомизация (domain randomization)
    randomize_target: bool = True
    randomize_object: bool = True
    target_range_mm: float = 150.0  # диапазон случайных позиций цели

    # Обратная связь с реальным роботом
    use_real_robot: bool = False


class RobotArmEnv:
    """
    Среда для обучения манипулятора.

    Работает в двух режимах:
        1. Симуляция (use_real_robot=False) — кинематика считается аналитически
        2. Реальный робот (use_real_robot=True) — действия отправляются на RobotService

    Интерфейс Gymnasium:
        obs, info = env.reset()
        obs, reward, terminated, truncated, info = env.step(action)

    Также поддерживается старый OpenAI Gym стиль:
        obs = env.reset()
        obs, reward, done, info = env.step(action)
    """

    OBS_DIM = OBS_DIM
    ACTION_DIM = ACTION_DIM

    def __init__(
        self,
        reward_fn: BaseReward | None = None,
        config: RobotArmConfig | None = None,
        robot_service=None,
        kinematics_service=None,
    ):
        self.config = config or RobotArmConfig()
        self.reward_fn = reward_fn or CompositeReward(
            [
                (
                    1.0,
                    DistanceReward(
                        scale=1.0, success_threshold_mm=self.config.success_threshold_mm
                    ),
                ),
                (0.05, SmoothMotionReward()),
            ]
        )
        self._robot = robot_service
        self._kin = kinematics_service

        # Состояние эпизода
        self._joint_angles = np.zeros(6)
        self._prev_joint_angles = np.zeros(6)
        self._ee_pos = np.zeros(3)
        self._target_pos = np.array([150.0, 0.0, 150.0])
        self._object_pos = np.array([100.0, 50.0, 0.0])
        self._gripper_open = True
        self._object_grasped = False
        self._steps = 0
        self._episode_reward = 0.0

        logger.info("RobotArmEnv created (real_robot=%s)", self.config.use_real_robot)

    # ── Gym интерфейс ──

    def reset(self, seed: int | None = None) -> tuple[np.ndarray, dict]:
        """Сбросить среду в начальное состояние."""
        if seed is not None:
            np.random.seed(seed)

        # Начальная позиция (всегда домашняя)
        self._joint_angles = np.zeros(6)
        self._prev_joint_angles = np.zeros(6)
        self._gripper_open = True
        self._object_grasped = False
        self._steps = 0
        self._episode_reward = 0.0

        # Рандомизация цели
        if self.config.randomize_target:
            r = self.config.target_range_mm
            self._target_pos = np.array(
                [
                    np.random.uniform(80, r),
                    np.random.uniform(-r / 2, r / 2),
                    np.random.uniform(50, r),
                ]
            )
        else:
            self._target_pos = np.array([150.0, 0.0, 150.0])

        # Рандомизация объекта
        if self.config.randomize_object:
            r = self.config.target_range_mm * 0.5
            self._object_pos = np.array(
                [
                    np.random.uniform(60, r),
                    np.random.uniform(-r, r),
                    np.random.uniform(0, 20),
                ]
            )
        else:
            self._object_pos = np.array([100.0, 50.0, 0.0])

        # Сброс reward_fn stateful-компонентов
        if hasattr(self.reward_fn, "reset"):
            self.reward_fn.reset()

        # Вычислить начальный FK
        self._ee_pos = self._forward_kinematics(self._joint_angles)

        if self.config.use_real_robot and self._robot:
            self._robot.go_home()

        obs = self._get_obs()
        return obs, {"episode": 0}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        """
        Применить действие.

        Args:
            action: np.ndarray[7] — [delta_j1..delta_j6, gripper]

        Returns:
            (obs, reward, terminated, truncated, info)
        """
        action = np.clip(np.asarray(action, dtype=float), -1.0, 1.0)
        self._steps += 1

        # Сохранить предыдущие углы
        self._prev_joint_angles = self._joint_angles.copy()

        # Применить дельты суставов
        delta = action[:6] * self.config.max_delta_deg
        self._joint_angles = np.clip(
            self._joint_angles + delta,
            -self.config.joint_limit_deg,
            self.config.joint_limit_deg,
        )

        # Gripper
        self._gripper_open = action[6] > 0.0

        # Вычислить FK
        self._ee_pos = self._forward_kinematics(self._joint_angles)

        # Логика захвата объекта
        self._update_grasp()

        # Вычислить награду
        state = self._get_state_dict()
        reward = float(self.reward_fn.compute(state))
        self._episode_reward += reward

        # Применить на реальном роботе
        if self.config.use_real_robot and self._robot:
            self._apply_to_robot()

        # Условия завершения
        dist = float(np.linalg.norm(self._ee_pos - self._target_pos))
        terminated = dist < self.config.success_threshold_mm
        truncated = self._steps >= self.config.max_steps

        info = {
            "distance_mm": dist,
            "success": terminated,
            "steps": self._steps,
            "episode_reward": self._episode_reward,
            "object_grasped": self._object_grasped,
        }

        return self._get_obs(), reward, terminated, truncated, info

    def render(self) -> str:
        """Текстовая визуализация состояния."""
        dist = float(np.linalg.norm(self._ee_pos - self._target_pos))
        return (
            f"Step={self._steps} | "
            f"EE=({self._ee_pos[0]:.0f},{self._ee_pos[1]:.0f},{self._ee_pos[2]:.0f}) | "
            f"Target=({self._target_pos[0]:.0f},{self._target_pos[1]:.0f},{self._target_pos[2]:.0f}) | "
            f"Dist={dist:.1f}mm | "
            f"Gripper={'OPEN' if self._gripper_open else 'CLOSE'} | "
            f"Reward={self._episode_reward:.2f}"
        )

    def close(self) -> None:
        pass

    # ── Вспомогательные методы ──

    def _get_obs(self) -> np.ndarray:
        """Составить вектор наблюдений."""
        r = self.config.workspace_radius_mm
        norm_joints = self._joint_angles / self.config.joint_limit_deg
        norm_ee = self._ee_pos / r
        norm_target = self._target_pos / r
        norm_obj = self._object_pos / r
        dist = float(np.linalg.norm(self._ee_pos - self._target_pos)) / (2 * r)

        obs = np.concatenate(
            [
                norm_joints,  # [0:6]
                np.clip(norm_ee, -1, 1),  # [6:9]
                np.clip(norm_target, -1, 1),  # [9:12]
                np.clip(norm_obj, -1, 1),  # [12:15]
                [float(not self._gripper_open)],  # [15]
                [float(self._object_grasped)],  # [16]
                [np.clip(dist, 0, 1)],  # [17]
            ]
        ).astype(np.float32)
        return obs

    def _get_state_dict(self) -> dict[str, Any]:
        """Словарь состояния для reward function."""
        return {
            "ee_pos": self._ee_pos,
            "target_pos": self._target_pos,
            "joint_angles": self._joint_angles,
            "prev_joint_angles": self._prev_joint_angles,
            "gripper_state": self._gripper_open,
            "object_grasped": self._object_grasped,
            "object_pos": self._object_pos,
            "detection": None,
        }

    def _forward_kinematics(self, angles_deg: np.ndarray) -> np.ndarray:
        """
        Упрощённая аналитическая FK для 6-DOF манипулятора.
        Возвращает позицию end-effector (x, y, z) в мм.
        """
        a = np.radians(angles_deg)
        L1, L2, L3, L4 = (
            self.config.L1,
            self.config.L2,
            self.config.L3,
            self.config.L4,
        )

        # Проекция плоскости плечо-локоть
        r2 = L2 * math.cos(a[1]) + L3 * math.cos(a[1] + a[2])
        z2 = L2 * math.sin(a[1]) + L3 * math.sin(a[1] + a[2])

        x = r2 * math.cos(a[0])
        y = r2 * math.sin(a[0])
        z = L1 * math.sin(a[1] - math.pi / 2) + z2 + self.config.L4 * math.sin(a[1] + a[2] + a[3])

        # Смещение запястья
        z += 19.0  # L0

        return np.array([x, y, z], dtype=float)

    def _update_grasp(self) -> None:
        """Обновить состояние захвата объекта."""
        dist_to_obj = float(np.linalg.norm(self._ee_pos - self._object_pos))

        if not self._gripper_open and dist_to_obj < 40.0:
            self._object_grasped = True

        if self._gripper_open:
            self._object_grasped = False

        # Если объект захвачен — он движется вместе с EE
        if self._object_grasped:
            self._object_pos = self._ee_pos.copy()

    def _apply_to_robot(self) -> None:
        """Отправить команды на реальный робот."""
        try:
            self._robot.move_joints(
                list(self._joint_angles),
                speed=800,
            )
        except Exception as e:
            logger.warning("Failed to apply action to real robot: %s", e)

    @property
    def obs_dim(self) -> int:
        return OBS_DIM

    @property
    def action_dim(self) -> int:
        return ACTION_DIM

    @property
    def current_state(self) -> dict[str, Any]:
        return self._get_state_dict()
