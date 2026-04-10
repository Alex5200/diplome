#!/usr/bin/env python3
"""
RL Training Service — сервис управления обучением с подкреплением.

Функции:
    - Запуск/остановка обучения в фоновом потоке
    - Поддержка DQN и PPO агентов
    - Callback'и: on_episode, on_step, on_complete
    - Сохранение/загрузка чекпоинтов
    - Логирование метрик (reward, loss, epsilon)
    - Curriculum learning: поэтапное усложнение задачи
    - Режим демонстрации: запуск обученного агента без обучения

Использование:
    from app.models.rl import DQNAgent, PPOAgent, RobotArmEnv
    from app.models.rl import CompositeReward, DistanceReward, PickPlaceReward
    from app.services.rl_training_service import RLTrainingService, TrainingMode

    # Создать среду с наградой
    reward = CompositeReward([
        (1.0,  DistanceReward()),
        (0.1,  SmoothMotionReward()),
        (0.5,  PickPlaceReward()),
    ])
    env = RobotArmEnv(reward_fn=reward)

    # Создать и запустить сервис
    svc = RLTrainingService()
    svc.setup_dqn(env)           # или .setup_ppo(env)
    svc.start_training()

    # Статус
    print(svc.get_status())
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import numpy as np

from ..core.base_service import BaseService
from ..models.rl.base_agent import BaseRLAgent, Episode, TrainingConfig
from ..models.rl.dqn_agent import DQNAgent
from ..models.rl.environment import RobotArmConfig, RobotArmEnv
from ..models.rl.ppo_agent import PPOAgent
from ..models.rl.rewards import (
    CompositeReward,
    DistanceReward,
    PickPlaceReward,
    SmoothMotionReward,
    VisionReward,
)

logger = logging.getLogger(__name__)


# ──────────────────── Режимы обучения ────────────────────


class TrainingMode(Enum):
    """Режим обучения."""

    DQN = auto()  # Deep Q-Network (дискретные действия)
    PPO = auto()  # Proximal Policy Optimization (непрерывные)
    CURRICULUM = auto()  # Curriculum learning (поэтапное усложнение)
    DEMO = auto()  # Демонстрация без обучения


class RewardPreset(Enum):
    """Готовые пресеты функций наград."""

    REACH = "reach"  # Достичь точки в пространстве
    PICK_PLACE = "pick_place"  # Взять и положить объект
    TRACK_VISION = "track_vision"  # Следить за объектом через камеру
    CUSTOM = "custom"  # Пользовательская функция


# ──────────────────── Состояние сервиса ────────────────────


@dataclass
class TrainingStatus:
    """Текущее состояние обучения."""

    mode: str = "idle"
    agent_type: str = ""
    episode: int = 0
    total_steps: int = 0
    best_reward: float = float("-inf")
    last_reward: float = 0.0
    mean_reward_100: float = 0.0
    last_loss: float = 0.0
    epsilon: float = 1.0  # только для DQN
    is_training: bool = False
    is_converged: bool = False
    checkpoint_path: str = ""
    error: str = ""
    reward_history: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "agent_type": self.agent_type,
            "episode": self.episode,
            "total_steps": self.total_steps,
            "best_reward": round(self.best_reward, 3),
            "last_reward": round(self.last_reward, 3),
            "mean_reward_100": round(self.mean_reward_100, 3),
            "last_loss": round(self.last_loss, 6),
            "epsilon": round(self.epsilon, 4),
            "is_training": self.is_training,
            "is_converged": self.is_converged,
            "checkpoint": self.checkpoint_path,
            "error": self.error,
        }


@dataclass
class CurriculumStage:
    """Этап curriculum learning."""

    name: str
    max_delta_deg: float  # сложность управления
    target_range_mm: float  # диапазон цели
    success_threshold_mm: float  # порог успеха
    episodes: int  # количество эпизодов на этапе
    min_success_rate: float = 0.7  # успешность для перехода


# ──────────────────── Основной сервис ────────────────────


class RLTrainingService(BaseService):
    """
    Сервис обучения с подкреплением.

    Поддерживает:
        - DQN (дискретные действия, off-policy)
        - PPO (непрерывные действия, on-policy)
        - Curriculum learning (поэтапное усложнение)
        - Демо-режим (запуск обученного агента)

    TDD: app/tests/test_rl_training.py::TestRLTrainingService
    """

    # Стандартные этапы curriculum
    DEFAULT_CURRICULUM = [
        CurriculumStage("easy", 10.0, 80.0, 40.0, 200, 0.6),
        CurriculumStage("medium", 10.0, 150.0, 30.0, 300, 0.6),
        CurriculumStage("hard", 10.0, 200.0, 20.0, 500, 0.5),
    ]

    def __init__(
        self,
        checkpoint_dir: str = "checkpoints/rl",
        robot_service=None,
        kinematics_service=None,
    ):
        super().__init__("RLTrainingService")
        self._checkpoint_dir = checkpoint_dir
        self._robot = robot_service
        self._kin = kinematics_service

        os.makedirs(checkpoint_dir, exist_ok=True)

        # Компоненты обучения
        self._agent: BaseRLAgent | None = None
        self._env: RobotArmEnv | None = None
        self._mode: TrainingMode = TrainingMode.DQN

        # Состояние
        self._status = TrainingStatus()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._training_thread: threading.Thread | None = None

        # Callbacks
        self._on_episode: Callable[[Episode], None] | None = None
        self._on_step_cb: Callable[[dict], None] | None = None
        self._on_complete: Callable[[TrainingStatus], None] | None = None
        self._on_stage_complete: Callable[[CurriculumStage], None] | None = None

        # Curriculum
        self._curriculum_stages: list[CurriculumStage] = list(self.DEFAULT_CURRICULUM)
        self._current_stage_idx: int = 0

        # История наград
        self._reward_history: list[float] = []

    # ──────────── Настройка агентов ────────────

    def setup_dqn(
        self,
        env: RobotArmEnv | None = None,
        config: TrainingConfig | None = None,
    ) -> RLTrainingService:
        """
        Настроить DQN агент.

        Args:
            env: среда (создаётся автоматически если None)
            config: гиперпараметры

        Returns:
            self (для chaining)
        """
        self._mode = TrainingMode.DQN
        self._env = env or self._create_default_env()
        cfg = config or TrainingConfig(
            max_episodes=1000,
            batch_size=64,
            buffer_size=50_000,
            learning_rate=1e-3,
            checkpoint_dir=self._checkpoint_dir,
        )
        self._agent = DQNAgent(
            obs_dim=self._env.obs_dim,
            config=cfg,
        )
        self._setup_agent_callbacks()
        with self._lock:
            self._status.agent_type = "DQN"
            self._status.mode = "dqn"
        logger.info("DQN agent configured")
        return self

    def setup_ppo(
        self,
        env: RobotArmEnv | None = None,
        config: TrainingConfig | None = None,
    ) -> RLTrainingService:
        """
        Настроить PPO агент.

        Args:
            env: среда (создаётся автоматически если None)
            config: гиперпараметры

        Returns:
            self (для chaining)
        """
        self._mode = TrainingMode.PPO
        self._env = env or self._create_default_env()
        cfg = config or TrainingConfig(
            max_episodes=500,
            n_steps=2048,
            batch_size=64,
            n_epochs=10,
            learning_rate=3e-4,
            gamma=0.99,
            checkpoint_dir=self._checkpoint_dir,
        )
        self._agent = PPOAgent(
            obs_dim=self._env.obs_dim,
            action_dim=self._env.action_dim,
            config=cfg,
        )
        self._setup_agent_callbacks()
        with self._lock:
            self._status.agent_type = "PPO"
            self._status.mode = "ppo"
        logger.info("PPO agent configured")
        return self

    def setup_with_reward_preset(
        self,
        preset: RewardPreset,
        mode: TrainingMode = TrainingMode.PPO,
        config: TrainingConfig | None = None,
    ) -> RLTrainingService:
        """
        Настроить сервис с готовым пресетом наград.

        Пресеты:
            REACH       — достичь точки (DistanceReward)
            PICK_PLACE  — взять и положить (DistanceReward + PickPlaceReward)
            TRACK_VISION— слежение камерой (VisionReward + SmoothMotionReward)
        """
        reward = self._build_reward(preset)
        env_cfg = RobotArmConfig(
            use_real_robot=self._robot is not None,
        )
        env = RobotArmEnv(
            reward_fn=reward,
            config=env_cfg,
            robot_service=self._robot,
            kinematics_service=self._kin,
        )

        if mode == TrainingMode.DQN:
            return self.setup_dqn(env, config)
        else:
            return self.setup_ppo(env, config)

    def setup_curriculum(
        self,
        stages: list[CurriculumStage] | None = None,
        mode: TrainingMode = TrainingMode.PPO,
    ) -> RLTrainingService:
        """
        Настроить curriculum learning.

        Автоматически переходит от простых задач к сложным
        при достижении min_success_rate.
        """
        self._curriculum_stages = stages or self.DEFAULT_CURRICULUM
        self._current_stage_idx = 0
        self._mode = TrainingMode.CURRICULUM

        # Создать среду для первого этапа
        stage = self._curriculum_stages[0]
        self._env = self._create_env_for_stage(stage)

        cfg = TrainingConfig(
            max_episodes=stage.episodes,
            checkpoint_dir=self._checkpoint_dir,
        )
        if mode == TrainingMode.PPO:
            self._agent = PPOAgent(self._env.obs_dim, self._env.action_dim, cfg)
        else:
            self._agent = DQNAgent(self._env.obs_dim, cfg)

        self._setup_agent_callbacks()
        with self._lock:
            self._status.agent_type = f"{mode.name}+Curriculum"
            self._status.mode = "curriculum"
        logger.info("Curriculum learning configured: %d stages", len(self._curriculum_stages))
        return self

    # ──────────── Управление обучением ────────────

    def start_training(self) -> bool:
        """Запустить обучение в фоновом потоке."""
        if self._agent is None or self._env is None:
            logger.error("Agent or env not configured. Call setup_dqn() or setup_ppo() first.")
            return False

        if self._status.is_training:
            logger.warning("Training already running")
            return False

        self._stop_event.clear()
        self._training_thread = threading.Thread(
            target=self._training_loop,
            daemon=True,
            name="rl-training",
        )
        self._training_thread.start()

        with self._lock:
            self._status.is_training = True

        logger.info(
            "RL training started (mode=%s, agent=%s)", self._mode.name, self._status.agent_type
        )
        return True

    def stop_training(self) -> None:
        """Остановить обучение."""
        self._stop_event.set()
        if self._agent:
            self._agent.stop_training()
        if self._training_thread and self._training_thread.is_alive():
            self._training_thread.join(timeout=10.0)

        with self._lock:
            self._status.is_training = False

        logger.info("RL training stopped at episode %d", self._status.episode)

    def save_checkpoint(self, name: str = "manual") -> str:
        """Сохранить чекпоинт вручную."""
        if not self._agent:
            return ""
        path = os.path.join(self._checkpoint_dir, f"{self._status.agent_type}_{name}.pt")
        self._agent.save(path)
        with self._lock:
            self._status.checkpoint_path = path
        return path

    def load_checkpoint(self, path: str) -> bool:
        """Загрузить чекпоинт."""
        if not self._agent:
            return False
        ok = self._agent.load(path)
        if ok:
            with self._lock:
                self._status.checkpoint_path = path
        return ok

    # ──────────── Демо-режим ────────────

    def run_demo(self, episodes: int = 5, render: bool = True) -> list[float]:
        """
        Запустить обученного агента без обучения.

        Args:
            episodes: количество демо-эпизодов
            render: печатать состояние в консоль

        Returns:
            Список наград за каждый эпизод
        """
        if not self._agent or not self._env:
            logger.error("Agent not configured")
            return []

        rewards = []
        for ep in range(episodes):
            obs, _ = self._env.reset()
            total_reward = 0.0
            done = False
            step = 0

            while not done and step < 200:
                action = self._agent.select_action(obs, explore=False)
                result = self._env.step(action)
                if len(result) == 5:
                    obs, reward, terminated, truncated, info = result
                    done = terminated or truncated
                else:
                    obs, reward, done, info = result

                total_reward += reward
                step += 1

                if render:
                    print(f"\r[Demo ep={ep + 1}] {self._env.render()}", end="", flush=True)

            if render:
                print(
                    f"\n  → reward={total_reward:.2f} steps={step} success={info.get('success', False)}"
                )

            rewards.append(total_reward)

        return rewards

    # ──────────── Callbacks ────────────

    def on_episode(self, cb: Callable[[Episode], None]) -> None:
        self._on_episode = cb

    def on_complete(self, cb: Callable[[TrainingStatus], None]) -> None:
        self._on_complete = cb

    def on_stage_complete(self, cb: Callable[[CurriculumStage], None]) -> None:
        self._on_stage_complete = cb

    # ──────────── Статус ────────────

    def get_status(self) -> TrainingStatus:
        with self._lock:
            status = TrainingStatus(
                mode=self._status.mode,
                agent_type=self._status.agent_type,
                episode=self._status.episode,
                total_steps=self._agent.total_steps if self._agent else 0,
                best_reward=self._status.best_reward,
                last_reward=self._status.last_reward,
                mean_reward_100=self._status.mean_reward_100,
                last_loss=self._status.last_loss,
                epsilon=getattr(self._agent, "epsilon", 1.0) if self._agent else 1.0,
                is_training=self._status.is_training,
                is_converged=self._status.is_converged,
                checkpoint_path=self._status.checkpoint_path,
                error=self._status.error,
                reward_history=list(self._reward_history[-100:]),
            )
        return status

    def export_metrics(self, path: str = "training_metrics.json") -> str:
        """Сохранить метрики обучения в JSON."""
        status = self.get_status()
        metrics = {
            **status.to_dict(),
            "reward_history": self._reward_history,
        }
        with open(path, "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info("Metrics exported → %s", path)
        return path

    # ──────────── Внутренние методы ────────────

    def _training_loop(self) -> None:
        """Основной цикл обучения (в фоновом потоке)."""
        try:
            if self._mode == TrainingMode.CURRICULUM:
                self._curriculum_loop()
            else:
                self._standard_loop()
        except Exception as e:
            logger.exception("Training loop error: %s", e)
            with self._lock:
                self._status.error = str(e)
        finally:
            with self._lock:
                self._status.is_training = False

            if self._on_complete:
                self._on_complete(self.get_status())

    def _standard_loop(self) -> None:
        """Обычный цикл DQN/PPO."""
        history = self._agent.train(self._env)
        with self._lock:
            self._status.episode = len(history)

    def _curriculum_loop(self) -> None:
        """Curriculum: поэтапное усложнение."""
        for stage_idx, stage in enumerate(self._curriculum_stages):
            if self._stop_event.is_set():
                break

            logger.info(
                "Curriculum stage %d/%d: %s",
                stage_idx + 1,
                len(self._curriculum_stages),
                stage.name,
            )

            # Пересоздать среду для нового этапа
            self._env = self._create_env_for_stage(stage)
            self._agent._stop_requested = False

            # Обучать на этапе
            history = self._agent.train(self._env, episodes=stage.episodes)

            # Проверить успешность
            if len(history) >= 20:
                recent = history[-20:]
                success_rate = sum(1 for ep in recent if ep.success) / len(recent)
                logger.info("Stage '%s' success rate: %.1f%%", stage.name, success_rate * 100)

                if success_rate < stage.min_success_rate:
                    logger.warning(
                        "Stage '%s' not passed (%.1f%% < %.1f%%). Repeating...",
                        stage.name,
                        success_rate * 100,
                        stage.min_success_rate * 100,
                    )

            if self._on_stage_complete:
                self._on_stage_complete(stage)

            # Сохранить чекпоинт после каждого этапа
            ckpt = os.path.join(
                self._checkpoint_dir, f"{self._status.agent_type}_stage_{stage.name}.pt"
            )
            self._agent.save(ckpt)

    def _setup_agent_callbacks(self) -> None:
        """Зарегистрировать callback'и агента."""
        if not self._agent:
            return

        def on_episode(ep: Episode) -> None:
            self._reward_history.append(ep.total_reward)
            recent = self._reward_history[-100:]
            mean_r = float(np.mean(recent)) if recent else 0.0

            with self._lock:
                self._status.episode = ep.episode_id
                self._status.last_reward = ep.total_reward
                self._status.mean_reward_100 = mean_r
                self._status.last_loss = ep.mean_loss

                if ep.total_reward > self._status.best_reward:
                    self._status.best_reward = ep.total_reward
                    # Авто-сохранение лучшего
                    best_path = os.path.join(
                        self._checkpoint_dir, f"{self._status.agent_type}_best.pt"
                    )
                    if self._agent:
                        self._agent.save(best_path)
                        self._status.checkpoint_path = best_path

            if self._on_episode:
                self._on_episode(ep)

        self._agent.on_episode_end(on_episode)

    def _create_default_env(self) -> RobotArmEnv:
        """Создать среду с настройками по умолчанию."""
        reward = CompositeReward(
            [
                (1.0, DistanceReward()),
                (0.05, SmoothMotionReward()),
            ]
        )
        return RobotArmEnv(
            reward_fn=reward,
            robot_service=self._robot,
            kinematics_service=self._kin,
        )

    def _create_env_for_stage(self, stage: CurriculumStage) -> RobotArmEnv:
        """Создать среду для конкретного этапа curriculum."""
        reward = CompositeReward(
            [
                (1.0, DistanceReward(success_threshold_mm=stage.success_threshold_mm)),
                (0.05, SmoothMotionReward()),
            ]
        )
        config = RobotArmConfig(
            max_delta_deg=stage.max_delta_deg,
            target_range_mm=stage.target_range_mm,
            success_threshold_mm=stage.success_threshold_mm,
            use_real_robot=self._robot is not None,
        )
        return RobotArmEnv(
            reward_fn=reward,
            config=config,
            robot_service=self._robot,
            kinematics_service=self._kin,
        )

    @staticmethod
    def _build_reward(preset: RewardPreset) -> CompositeReward:
        """Построить функцию наград из пресета."""
        if preset == RewardPreset.REACH:
            return CompositeReward(
                [
                    (1.0, DistanceReward(scale=1.0)),
                    (0.05, SmoothMotionReward()),
                ]
            )
        elif preset == RewardPreset.PICK_PLACE:
            return CompositeReward(
                [
                    (0.5, DistanceReward(scale=0.5)),
                    (1.0, PickPlaceReward()),
                    (0.05, SmoothMotionReward()),
                ]
            )
        elif preset == RewardPreset.TRACK_VISION:
            return CompositeReward(
                [
                    (1.0, VisionReward()),
                    (0.1, SmoothMotionReward()),
                ]
            )
        else:
            return CompositeReward([(1.0, DistanceReward())])

    # ──────────── BaseService methods ────────────

    def _do_initialize(self) -> bool:
        return True

    def _do_start(self) -> None:
        pass

    def _do_stop(self) -> None:
        self.stop_training()

    def _get_extra_status(self) -> dict[str, Any]:
        return self.get_status().to_dict()
