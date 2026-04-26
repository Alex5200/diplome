"""
Базовый класс для RL агентов.
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any

import numpy as np


class BaseAgent:
    """
    Базовый класс для RL агентов.

    Все агенты должны реализовать:
    - select_action(state) -> action
    - train(batch) -> metrics
    - save(path) / load(path)
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        learning_rate: float = 3e-4,
        device: str = "cpu",
    ):
        """
        Args:
            state_dim: Размерность пространства состояний
            action_dim: Размерность пространства действий
            learning_rate: Скорость обучения
            device: "cpu" или "cuda"
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.learning_rate = learning_rate
        self.device = device

        # Статистика
        self.training_steps = 0
        self.episodes = 0

    @abstractmethod
    def select_action(
        self,
        state: np.ndarray,
        deterministic: bool = False,
    ) -> np.ndarray:
        """
        Выбрать действие для данного состояния.

        Args:
            state: np.ndarray[state_dim]
            deterministic: если True — выбор argmax, иначе sampling

        Returns:
            action: np.ndarray[action_dim]
        """
        raise NotImplementedError

    @abstractmethod
    def train_step(self, batch: dict[str, Any]) -> dict[str, float]:
        """
        Один шаг обучения.

        Args:
            batch: словарь с experience (states, actions, rewards, etc.)

        Returns:
            metrics: словарь с метриками обучения
        """
        raise NotImplementedError

    @abstractmethod
    def save(self, path: Path | str) -> None:
        """Сохранить модель."""
        raise NotImplementedError

    @abstractmethod
    def load(self, path: Path | str) -> None:
        """Загрузить модель."""
        raise NotImplementedError

    def on_episode_end(self, episode_reward: float, episode_length: int) -> None:
        """Колбэк в конце эпизода."""
        self.episodes += 1

    def get_config(self) -> dict[str, Any]:
        """Получить конфигурацию агента."""
        return {
            "state_dim": self.state_dim,
            "action_dim": self.action_dim,
            "learning_rate": self.learning_rate,
            "device": self.device,
            "training_steps": self.training_steps,
            "episodes": self.episodes,
        }
