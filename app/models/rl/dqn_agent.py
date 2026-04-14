#!/usr/bin/env python3
"""
DQN Agent — Deep Q-Network для дискретных действий.

Реализует:
    - Double DQN (уменьшение переоценки Q-значений)
    - Experience Replay (ReplayBuffer)
    - Target Network (стабильность обучения)
    - Epsilon-greedy exploration с decay

Дискретизация действий:
    Для непрерывного управления манипулятором дискретизируем:
    Каждый сустав: {-large, -small, 0, +small, +large} = 5 действий
    Gripper: {open, close} = 2 действия
    Всего: 5^6 * 2 = 31250 — слишком много, поэтому используем
    по одному суставу за шаг (multi-discrete → 6*5+2 = 32 действия)

TDD: app/tests/test_rl_training.py::TestDQNAgent
"""

from __future__ import annotations

import logging
import os

import numpy as np

from .base_agent import BaseRLAgent, ReplayBuffer, TrainingConfig, Transition

logger = logging.getLogger(__name__)

# Дискретные действия: (joint_index, direction)
# direction: -2=большой минус, -1=малый минус, 0=стоп, +1=малый плюс, +2=большой плюс
# + 2 действия gripper
_JOINT_DELTAS = [-10.0, -3.0, 0.0, 3.0, 10.0]  # градусы
N_JOINT_ACTIONS = 6 * len(_JOINT_DELTAS)  # 30
N_GRIPPER_ACTIONS = 2  # open / close
N_ACTIONS = N_JOINT_ACTIONS + N_GRIPPER_ACTIONS  # 32


def _action_to_continuous(action_idx: int) -> np.ndarray:
    """Преобразовать дискретный индекс → непрерывный вектор [6 joints + gripper]."""
    vec = np.zeros(7)  # 6 суставов + gripper

    if action_idx < N_JOINT_ACTIONS:
        joint = action_idx // len(_JOINT_DELTAS)
        delta_idx = action_idx % len(_JOINT_DELTAS)
        vec[joint] = _JOINT_DELTAS[delta_idx]
        # Нормализуем в [-1, 1] для совместимости с env
        vec[joint] /= 10.0
        vec[6] = 1.0  # gripper open (нейтральное)
    else:
        gripper_cmd = action_idx - N_JOINT_ACTIONS
        vec[6] = 1.0 if gripper_cmd == 0 else -1.0

    return vec


class QNetwork:
    """
    Простая Q-сеть на PyTorch.

    Архитектура: FC(obs_dim) → 256 → 256 → 128 → FC(n_actions)
    """

    def __init__(self, obs_dim: int, n_actions: int, lr: float = 1e-3):
        self._obs_dim = obs_dim
        self._n_actions = n_actions
        self._lr = lr
        self._model = None
        self._optimizer = None
        self._built = False

    def build(self) -> bool:
        try:
            import torch
            import torch.nn as nn

            self._model = nn.Sequential(
                nn.Linear(self._obs_dim, 256),
                nn.ReLU(),
                nn.Linear(256, 256),
                nn.ReLU(),
                nn.Linear(256, 128),
                nn.ReLU(),
                nn.Linear(128, self._n_actions),
            )
            self._optimizer = torch.optim.Adam(self._model.parameters(), lr=self._lr)
            self._built = True
            return True
        except ImportError:
            logger.error("PyTorch not installed. Run: pip install torch")
            return False

    def forward(self, obs: np.ndarray) -> np.ndarray:
        if not self._built:
            return np.zeros(self._n_actions)
        import torch

        x = torch.FloatTensor(obs)
        if x.dim() == 1:
            x = x.unsqueeze(0)
        with torch.no_grad():
            return self._model(x).cpu().numpy().squeeze()

    def update_from_loss(self, loss_tensor) -> float:
        self._optimizer.zero_grad()
        loss_tensor.backward()
        import torch.nn as nn

        nn.utils.clip_grad_norm_(self._model.parameters(), 1.0)
        self._optimizer.step()
        return float(loss_tensor.item())

    def copy_weights_from(self, other: QNetwork) -> None:
        if self._built and other._built:
            self._model.load_state_dict(other._model.state_dict())

    def state_dict(self):
        return self._model.state_dict() if self._built else {}

    def load_state_dict(self, state_dict) -> None:
        if self._built:
            self._model.load_state_dict(state_dict)


class DQNAgent(BaseRLAgent):
    """
    Double Deep Q-Network агент.

    Особенности:
        - Double DQN: Q_target = r + γ * Q_target(s', argmax_a Q_online(s',a))
        - Replay Buffer: равномерная выборка прошлых переходов
        - Target Network: обновляется каждые target_update_interval шагов
        - Epsilon-greedy: linear decay от epsilon_start до epsilon_end

    Использование:
        env = RobotArmEnv()
        agent = DQNAgent(env.obs_dim, config=TrainingConfig(max_episodes=500))
        history = agent.train(env)
    """

    def __init__(
        self,
        obs_dim: int,
        config: TrainingConfig | None = None,
        target_update_interval: int = 500,
    ):
        cfg = config or TrainingConfig()
        super().__init__(obs_dim, N_ACTIONS, cfg, name="DQNAgent")

        self._buffer = ReplayBuffer(cfg.buffer_size)
        self._target_update_interval = target_update_interval

        self._q_online = QNetwork(obs_dim, N_ACTIONS, lr=cfg.learning_rate)
        self._q_target = QNetwork(obs_dim, N_ACTIONS, lr=cfg.learning_rate)

        self._built = False

    def _ensure_built(self) -> bool:
        if not self._built:
            ok1 = self._q_online.build()
            ok2 = self._q_target.build()
            if ok1 and ok2:
                self._q_target.copy_weights_from(self._q_online)
                self._built = True
        return self._built

    @property
    def epsilon(self) -> float:
        """Текущее значение epsilon (линейный decay)."""
        progress = min(self._total_steps / max(self.config.epsilon_decay, 1), 1.0)
        return self.config.epsilon_start + progress * (
            self.config.epsilon_end - self.config.epsilon_start
        )

    def select_action(self, obs: np.ndarray, explore: bool = True) -> np.ndarray:
        """
        Epsilon-greedy выбор действия.

        Returns:
            np.ndarray[7] — непрерывный вектор действия для env.step()
        """
        if not self._ensure_built():
            return np.zeros(7)

        if explore and np.random.random() < self.epsilon:
            action_idx = np.random.randint(0, N_ACTIONS)
        else:
            q_values = self._q_online.forward(obs)
            action_idx = int(np.argmax(q_values))

        return _action_to_continuous(action_idx)

    def _observe(self, transition: Transition) -> None:
        """Сохранить переход в replay buffer."""
        self._buffer.push(transition)

    def update(self) -> float:
        """Double DQN update шаг."""
        if not self._ensure_built():
            return 0.0

        if len(self._buffer) < self.config.min_buffer_size:
            return 0.0

        import torch
        import torch.nn.functional as F

        batch = self._buffer.sample(self.config.batch_size)

        obs_b = torch.FloatTensor(np.array([t.obs for t in batch]))
        act_b = torch.LongTensor([int(np.argmax(np.abs(t.action))) for t in batch])
        rew_b = torch.FloatTensor([t.reward for t in batch])
        next_b = torch.FloatTensor(np.array([t.next_obs for t in batch]))
        done_b = torch.FloatTensor([float(t.done) for t in batch])

        # Q_online(s, a)
        q_values = self._q_online._model(obs_b)
        q_sa = q_values.gather(1, act_b.unsqueeze(1)).squeeze(1)

        # Double DQN: a* = argmax_a Q_online(s', a)
        with torch.no_grad():
            next_q_online = self._q_online._model(next_b)
            best_actions = next_q_online.argmax(1, keepdim=True)
            next_q_target = self._q_target._model(next_b)
            q_next = next_q_target.gather(1, best_actions).squeeze(1)
            q_target = rew_b + self.config.gamma * q_next * (1.0 - done_b)

        loss = F.smooth_l1_loss(q_sa, q_target)
        self._q_online.update_from_loss(loss)

        # Обновить target network
        if self._total_steps % self._target_update_interval == 0:
            self._q_target.copy_weights_from(self._q_online)

        return float(loss.item())

    def save(self, path: str) -> None:
        if not self._built:
            return
        import torch

        torch.save(
            {
                "q_online": self._q_online.state_dict(),
                "q_target": self._q_target.state_dict(),
                "total_steps": self._total_steps,
                "episode": self._episode,
                "config": self.config.__dict__,
            },
            path,
        )
        logger.info("[DQN] checkpoint saved → %s", path)

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        self._ensure_built()
        import torch

        ckpt = torch.load(path, map_location="cpu")
        self._q_online.load_state_dict(ckpt["q_online"])
        self._q_target.load_state_dict(ckpt["q_target"])
        self._total_steps = ckpt.get("total_steps", 0)
        self._episode = ckpt.get("episode", 0)
        logger.info("[DQN] checkpoint loaded ← %s", path)
        return True
