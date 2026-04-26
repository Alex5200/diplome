"""
Базовый класс для Gymnasium-совместимых сред MuJoCo робота.
"""

from __future__ import annotations

import logging
import sys
from abc import abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

# Добавляем корень проекта
_parent_dir = Path(__file__).parent.parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

try:
    import mujoco
    import mujoco.viewer
except ImportError:
    sys.exit("MuJoCo не установлен. Запустите: uv pip install mujoco")

# Импортируем генератор MJCF из основного симулятора
from app.tests.mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf

logger = logging.getLogger(__name__)


class BaseRobotEnv:
    """
    Базовый класс для RL сред робота в MuJoCo.

    Поддерживает:
    - Программное управление (headless mode для RL)
    - RGB/Depth наблюдения с камер
    - Сенсоры суставов и end-effector
    - Позиции объектов

    Использует API как Gymnasium (без наследования):
    reset() -> obs, info
    step(action) -> obs, reward, terminated, truncated, info
    close()
    """

    # Метаданные для Gymnasium-совместимости
    metadata = {
        "render_modes": ["human", "rgb_array", "depth_array"],
        "render_fps": 50,
    }

    def __init__(
        self,
        mjcf_string: str | None = None,
        camera_width: int = 640,
        camera_height: int = 480,
        frame_skip: int = 5,
        max_steps: int = 500,
        render_mode: str | None = None,
    ):
        """
        Args:
            mjcf_string: XML модель (если None — используется generate_robot_mjcf)
            camera_width: Ширина камеры для наблюдений
            camera_height: Высота камеры для наблюдений
            frame_skip: Сколько шагов физики на 1 RL step
            max_steps: Максимум шагов в эпизоде
            render_mode: "human" | "rgb_array" | "depth_array" | None
        """
        # Создаём контроллер
        if mjcf_string is None:
            mjcf_string = generate_robot_mjcf()

        self.controller = MuJoCoRobotController(
            xml_string=mjcf_string,
            camera_width=camera_width,
            camera_height=camera_height,
        )

        self.frame_skip = frame_skip
        self.max_steps = max_steps
        self.render_mode = render_mode
        self._step_count = 0

        # Кэшируем начальные позиции объектов
        self._initial_object_positions = {}

    # ====================
    # Gymnasium API
    # ====================

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Сброс среды в начальное состояние.

        Returns:
            observation: dict с наблюдениями
            info: словарь с дополнительной информацией
        """
        # Seed для воспроизводимости (опционально)
        if seed is not None:
            np.random.seed(seed)

        # Сброс симуляции
        self.controller.reset()
        self._step_count = 0

        # Сброс позиций объектов (если нужно)
        self._reset_objects()

        # Начальная поза робота
        if options and "initial_angles" in options:
            self.controller.set_joint_angles(options["initial_angles"], immediate=True)
        else:
            self._set_default_initial_state()

        # Первые шаги для стабилизации
        self.controller.step(50)

        return self._get_obs(), self._get_info()

    def step(self, action: np.ndarray) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        """
        Выполнить один RL шаг.

        Args:
            action: np.ndarray с действием агента

        Returns:
            observation: наблюдения
            reward: награда
            terminated: True если эпизод закончился успешно/неудачно
            truncated: True если превышен max_steps
            info: дополнительная информация
        """
        self._step_count += 1

        # Применяем действие
        self._apply_action(action)

        # Шаги физики
        self.controller.step(self.frame_skip)

        # Получаем наблюдения
        obs = self._get_obs()

        # Вычисляем награду
        reward = self._compute_reward(obs)

        # Проверяем условия окончания
        terminated = self._check_terminated(obs)
        truncated = self._step_count >= self.max_steps

        info = self._get_info()
        info["step"] = self._step_count

        return obs, reward, terminated, truncated, info

    def close(self) -> None:
        """Освобождение ресурсов."""
        self.controller.close()

    def render(self) -> np.ndarray | None:
        """
        Рендеринг текущего состояния.

        Returns:
            np.ndarray: RGB изображение если render_mode="rgb_array"
            None: если render_mode=None
        """
        if self.render_mode == "rgb_array":
            return self.controller.render_camera("top_down", depth=False)
        elif self.render_mode == "depth_array":
            return self.controller.render_camera("top_down", depth=True)
        elif self.render_mode == "human":
            # Для human mode нужен отдельный viewer
            return None
        return None

    # ====================
    # Abstract Methods
    # ====================

    @abstractmethod
    def _get_obs(self) -> dict[str, Any]:
        """Получить наблюдения."""
        raise NotImplementedError

    @abstractmethod
    def _apply_action(self, action: np.ndarray) -> None:
        """Применить действие к симуляции."""
        raise NotImplementedError

    @abstractmethod
    def _compute_reward(self, obs: dict[str, Any]) -> float:
        """Вычислить награду."""
        raise NotImplementedError

    @abstractmethod
    def _check_terminated(self, obs: dict[str, Any]) -> bool:
        """Проверить условия окончания эпизода."""
        raise NotImplementedError

    @abstractmethod
    def _set_default_initial_state(self) -> None:
        """Установить начальное состояние по умолчанию."""
        raise NotImplementedError

    # ====================
    # Utility Methods
    # ====================

    def _get_info(self) -> dict[str, Any]:
        """Дополнительная информация о состоянии."""
        return {
            "ee_position": self.controller.get_ee_position(),
            "ee_position_mm": self.controller.get_ee_position_mm(),
            "joint_angles": self.controller.get_joint_angles(),
        }

    def _reset_objects(self) -> None:
        """Сброс позиций объектов."""
        # Можно переопределить для сброса объектов
        pass

    def get_end_effector_distance_to(self, target_pos: np.ndarray) -> float:
        """
        Расстояние от end-effector до целевой точки.

        Args:
            target_pos: [x, y, z] в метрах

        Returns:
            float: евклидово расстояние
        """
        ee_pos = np.array(self.controller.get_ee_position())
        return float(np.linalg.norm(ee_pos - target_pos))

    def normalize_angles(self, angles: list[float]) -> np.ndarray:
        """
        Нормализация углов в [-1, 1] для RL.

        Args:
            angles: углы в градусах

        Returns:
            np.ndarray: нормализованные углы в [-1, 1]
        """
        safe_limits = self.controller.SAFE_ANGLE_LIMITS_DEG
        normalized = []
        for angle, (low, high) in zip(angles, safe_limits):
            # Нормализуем в [-1, 1]
            norm = 2.0 * (angle - low) / (high - low) - 1.0
            normalized.append(np.clip(norm, -1.0, 1.0))
        return np.array(normalized, dtype=np.float32)

    def denormalize_angles(self, normalized: np.ndarray) -> list[float]:
        """
        Денормализация из [-1, 1] в градусы.

        Args:
            normalized: углы в [-1, 1]

        Returns:
            list[float]: углы в градусах
        """
        safe_limits = self.controller.SAFE_ANGLE_LIMITS_DEG
        angles = []
        for norm, (low, high) in zip(normalized, safe_limits):
            # Денормализуем из [-1, 1]
            angle = low + (norm + 1.0) * 0.5 * (high - low)
            angles.append(angle)
        return angles

    # ====================
    # Context Manager
    # ====================

    def __enter__(self) -> BaseRobotEnv:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
