#!/usr/bin/env python3
"""
Base RL Agent — абстрактный базовый класс для всех RL агентов.

Все агенты (DQN, PPO, SAC) наследуют от BaseRLAgent и реализуют:
    select_action(obs)  → action
    update(batch)       → loss
    save(path)          → None
    load(path)          → None
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ──────────────────── Конфигурация обучения ────────────────────


@dataclass
class TrainingConfig:
    """Гиперпараметры обучения."""

    # Общие
    max_episodes: int = 1000
    max_steps_per_episode: int = 200
    gamma: float = 0.99  # коэффициент дисконтирования
    learning_rate: float = 3e-4
    batch_size: int = 64

    # Exploration (для DQN)
    epsilon_start: float = 1.0
    epsilon_end: float = 0.05
    epsilon_decay: int = 10_000  # шагов до достижения epsilon_end

    # Replay buffer (для DQN)
    buffer_size: int = 100_000
    min_buffer_size: int = 1_000  # минимум до начала обучения

    # PPO-специфичные
    clip_epsilon: float = 0.2
    entropy_coeff: float = 0.01
    value_coeff: float = 0.5
    n_steps: int = 2048  # шагов до обновления
    n_epochs: int = 10  # эпох обновления на batch

    # Сохранение
    save_interval: int = 100  # сохранять каждые N эпизодов
    checkpoint_dir: str = "checkpoints"
    log_interval: int = 10


@dataclass
class Transition:
    """Один переход среды (s, a, r, s', done)."""

    obs: np.ndarray
    action: Any
    reward: float
    next_obs: np.ndarray
    done: bool
    info: dict = field(default_factory=dict)


@dataclass
class Episode:
    """Статистика одного эпизода."""

    episode_id: int
    total_reward: float = 0.0
    steps: int = 0
    success: bool = False
    duration_s: float = 0.0
    mean_loss: float = 0.0
    info: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode": self.episode_id,
            "reward": round(self.total_reward, 4),
            "steps": self.steps,
            "success": self.success,
            "duration_s": round(self.duration_s, 3),
            "mean_loss": round(self.mean_loss, 6),
        }


# ──────────────────── Replay Buffer ────────────────────


class ReplayBuffer:
    """
    Circular replay buffer для off-policy алгоритмов (DQN, SAC).

    Хранит переходы (s, a, r, s', done) и выдаёт случайные батчи.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._buffer: list[Transition] = []
        self._pos = 0

    def push(self, transition: Transition) -> None:
        if len(self._buffer) < self.capacity:
            self._buffer.append(transition)
        else:
            self._buffer[self._pos] = transition
        self._pos = (self._pos + 1) % self.capacity

    def sample(self, batch_size: int) -> list[Transition]:
        indices = np.random.choice(len(self._buffer), batch_size, replace=False)
        return [self._buffer[i] for i in indices]

    def __len__(self) -> int:
        return len(self._buffer)

    @property
    def is_ready(self) -> bool:
        return len(self._buffer) >= 1


# ──────────────────── Базовый агент ────────────────────


class BaseRLAgent(ABC):
    """
    Абстрактный базовый класс для RL агентов.

    Определяет общий интерфейс:
        select_action  — выбор действия (с exploration)
        update         — обновление весов сети
        save / load    — сохранение/загрузка чекпоинтов
        train          — полный цикл обучения

    Subclasses:
        DQNAgent  — Deep Q-Network
        PPOAgent  — Proximal Policy Optimization
    """

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        config: TrainingConfig | None = None,
        name: str = "BaseAgent",
    ):
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.config = config or TrainingConfig()
        self.name = name

        self._total_steps = 0
        self._episode = 0
        self._training = False
        self._stop_requested = False

        # Callbacks
        self._on_episode_end: Callable[[Episode], None] | None = None
        self._on_step: Callable[[Transition], None] | None = None

        os.makedirs(self.config.checkpoint_dir, exist_ok=True)
        logger.info("[%s] initialized (obs=%d, action=%d)", name, obs_dim, action_dim)

    # ── Абстрактные методы ──

    @abstractmethod
    def select_action(self, obs: np.ndarray, explore: bool = True) -> Any:
        """Выбрать действие по наблюдению."""
        ...

    @abstractmethod
    def update(self) -> float:
        """Обновить веса сети. Возвращает loss."""
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        """Сохранить чекпоинт."""
        ...

    @abstractmethod
    def load(self, path: str) -> bool:
        """Загрузить чекпоинт. Возвращает True при успехе."""
        ...

    # ── Callbacks ──

    def on_episode_end(self, cb: Callable[[Episode], None]) -> None:
        self._on_episode_end = cb

    def on_step(self, cb: Callable[[Transition], None]) -> None:
        self._on_step = cb

    # ── Главный цикл обучения ──

    def train(self, env, episodes: int | None = None) -> list[Episode]:
        """
        Запустить полный цикл обучения.

        Args:
            env: среда с интерфейсом reset()/step(action)
            episodes: количество эпизодов (или из config)

        Returns:
            Список статистик по эпизодам
        """
        n_episodes = episodes or self.config.max_episodes
        history: list[Episode] = []
        self._training = True
        self._stop_requested = False

        logger.info("[%s] training started: %d episodes", self.name, n_episodes)

        for ep in range(n_episodes):
            if self._stop_requested:
                break

            ep_stats = self._run_episode(env, ep)
            history.append(ep_stats)
            self._episode += 1

            if self._on_episode_end:
                self._on_episode_end(ep_stats)

            if ep % self.config.log_interval == 0:
                logger.info(
                    "[%s] ep=%d reward=%.2f steps=%d loss=%.5f",
                    self.name,
                    ep,
                    ep_stats.total_reward,
                    ep_stats.steps,
                    ep_stats.mean_loss,
                )

            if ep % self.config.save_interval == 0 and ep > 0:
                self.save(os.path.join(self.config.checkpoint_dir, f"{self.name}_ep{ep}.pt"))

        self._training = False
        logger.info("[%s] training complete. episodes=%d", self.name, len(history))
        return history

    def stop_training(self) -> None:
        """Остановить обучение после текущего эпизода."""
        self._stop_requested = True

    def _run_episode(self, env, episode_id: int) -> Episode:
        """Выполнить один эпизод. Переопределяется в subclasses при необходимости."""
        obs, _ = env.reset() if self._returns_tuple(env) else (env.reset(), {})
        total_reward = 0.0
        losses = []
        t0 = time.time()

        for step in range(self.config.max_steps_per_episode):
            action = self.select_action(obs, explore=True)
            result = env.step(action)

            if len(result) == 5:
                next_obs, reward, terminated, truncated, info = result
                done = terminated or truncated
            else:
                next_obs, reward, done, info = result

            transition = Transition(obs, action, reward, next_obs, done, info)

            if self._on_step:
                self._on_step(transition)

            self._observe(transition)
            loss = self.update()
            if loss > 0:
                losses.append(loss)

            total_reward += reward
            self._total_steps += 1
            obs = next_obs

            if done:
                break

        return Episode(
            episode_id=episode_id,
            total_reward=total_reward,
            steps=step + 1,
            success=info.get("success", False),
            duration_s=time.time() - t0,
            mean_loss=float(np.mean(losses)) if losses else 0.0,
        )

    def _observe(self, transition: Transition) -> None:
        """Сохранить переход (переопределяется в subclasses)."""
        pass

    @staticmethod
    def _returns_tuple(env) -> bool:
        """Проверить, возвращает ли env.reset() кортеж (obs, info)."""
        try:
            import gymnasium

            return isinstance(env, gymnasium.Env)
        except ImportError:
            return False

    @property
    def total_steps(self) -> int:
        return self._total_steps

    @property
    def is_training(self) -> bool:
        return self._training

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(obs={self.obs_dim}, action={self.action_dim})"
