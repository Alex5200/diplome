#!/usr/bin/env python3
"""
PPO Agent — Proximal Policy Optimization для непрерывных действий.

Реализует:
    - Clipped Surrogate Objective (основное нововведение PPO)
    - Generalized Advantage Estimation (GAE, λ=0.95)
    - Value Function Loss (MSE или Huber)
    - Entropy Bonus (для exploration)
    - Gradient Clipping

Преимущества над DQN для манипулятора:
    - Непрерывное пространство действий (нет дискретизации)
    - On-policy: собирает данные именно той политикой, которую обучает
    - Стабильнее DDPG/SAC без тюнинга

Архитектура сетей:
    Actor (Policy): obs → 256 → 256 → mu[action_dim] + log_std
    Critic (Value): obs → 256 → 256 → V(s)

TDD: app/tests/test_rl_training.py::TestPPOAgent
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .base_agent import BaseRLAgent, TrainingConfig, Transition

logger = logging.getLogger(__name__)


@dataclass
class RolloutBuffer:
    """
    On-policy буфер для PPO.

    Накапливает N шагов, затем вычисляет advantages и обновляет политику.
    """

    obs: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    rewards: list = field(default_factory=list)
    values: list = field(default_factory=list)
    log_probs: list = field(default_factory=list)
    dones: list = field(default_factory=list)

    def clear(self) -> None:
        self.obs.clear()
        self.actions.clear()
        self.rewards.clear()
        self.values.clear()
        self.log_probs.clear()
        self.dones.clear()

    def __len__(self) -> int:
        return len(self.rewards)


class ActorCriticNetwork:
    """
    Объединённая Actor-Critic сеть.

    Actor:  obs → policy (mu, std) для Normal distribution
    Critic: obs → V(s)
    """

    def __init__(self, obs_dim: int, action_dim: int, lr: float = 3e-4):
        self._obs_dim = obs_dim
        self._action_dim = action_dim
        self._lr = lr
        self._actor = None
        self._critic = None
        self._log_std = None
        self._optimizer = None
        self._built = False

    def build(self) -> bool:
        try:
            import torch
            import torch.nn as nn

            self._actor = nn.Sequential(
                nn.Linear(self._obs_dim, 256),
                nn.Tanh(),
                nn.Linear(256, 256),
                nn.Tanh(),
                nn.Linear(256, self._action_dim),
                nn.Tanh(),  # действия в [-1, 1]
            )

            self._critic = nn.Sequential(
                nn.Linear(self._obs_dim, 256),
                nn.Tanh(),
                nn.Linear(256, 256),
                nn.Tanh(),
                nn.Linear(256, 1),
            )

            # Логарифм стандартного отклонения (обучаемый параметр)
            self._log_std = nn.Parameter(torch.zeros(self._action_dim) - 0.5)

            self._optimizer = torch.optim.Adam(
                list(self._actor.parameters()) + list(self._critic.parameters()) + [self._log_std],
                lr=self._lr,
            )
            self._built = True
            return True
        except ImportError:
            logger.error("PyTorch not installed. Run: pip install torch")
            return False

    def get_action(self, obs: np.ndarray) -> tuple[np.ndarray, float, float]:
        """
        Выбрать действие из политики.

        Returns:
            (action, log_prob, value)
        """
        if not self._built:
            return np.zeros(self._action_dim), 0.0, 0.0

        import torch

        x = torch.FloatTensor(obs).unsqueeze(0)
        with torch.no_grad():
            mu = self._actor(x).squeeze(0)
            std = self._log_std.exp()
            dist = torch.distributions.Normal(mu, std)
            action = dist.sample()
            action = torch.clamp(action, -1.0, 1.0)
            log_prob = dist.log_prob(action).sum()
            value = self._critic(x).squeeze().item()

        return action.numpy(), float(log_prob.item()), float(value)

    def evaluate(self, obs_t, actions_t):
        """
        Вычислить log_prob, entropy, value для батча.

        Используется при обновлении политики.
        """
        import torch

        mu = self._actor(obs_t)
        std = self._log_std.exp().expand_as(mu)
        dist = torch.distributions.Normal(mu, std)
        log_probs = dist.log_prob(actions_t).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)
        values = self._critic(obs_t).squeeze(-1)
        return log_probs, entropy, values

    def state_dict(self) -> dict:
        if not self._built:
            return {}
        return {
            "actor": self._actor.state_dict(),
            "critic": self._critic.state_dict(),
            "log_std": self._log_std.data,
        }

    def load_state_dict(self, d: dict) -> None:
        if self._built and d:
            self._actor.load_state_dict(d["actor"])
            self._critic.load_state_dict(d["critic"])
            import torch

            self._log_std.data = d["log_std"]


class PPOAgent(BaseRLAgent):
    """
    Proximal Policy Optimization агент.

    Цикл обучения:
        1. Собрать n_steps переходов (rollout)
        2. Вычислить GAE advantages
        3. Обновить политику n_epochs раз с clipping
        4. Повторить

    Использование:
        env = RobotArmEnv()
        agent = PPOAgent(env.obs_dim, env.action_dim)
        history = agent.train(env, episodes=500)
    """

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        config: TrainingConfig | None = None,
        gae_lambda: float = 0.95,
    ):
        cfg = config or TrainingConfig()
        super().__init__(obs_dim, action_dim, cfg, name="PPOAgent")

        self._gae_lambda = gae_lambda
        self._net = ActorCriticNetwork(obs_dim, action_dim, lr=cfg.learning_rate)
        self._rollout = RolloutBuffer()
        self._built = False

        # Текущие значения для _observe
        self._current_log_prob = 0.0
        self._current_value = 0.0

    def _ensure_built(self) -> bool:
        if not self._built:
            self._built = self._net.build()
        return self._built

    def select_action(self, obs: np.ndarray, explore: bool = True) -> np.ndarray:
        """Выбрать непрерывное действие из stochastic policy."""
        if not self._ensure_built():
            return np.zeros(self.action_dim)

        action, log_prob, value = self._net.get_action(obs)
        self._current_log_prob = log_prob
        self._current_value = value
        return action

    def _observe(self, transition: Transition) -> None:
        """Накопить шаг в rollout буфер."""
        self._rollout.obs.append(transition.obs)
        self._rollout.actions.append(transition.action)
        self._rollout.rewards.append(transition.reward)
        self._rollout.values.append(self._current_value)
        self._rollout.log_probs.append(self._current_log_prob)
        self._rollout.dones.append(float(transition.done))

    def update(self) -> float:
        """
        PPO update — вызывается после накопления n_steps шагов.
        Возвращает 0.0 пока буфер не заполнен.
        """
        if not self._ensure_built():
            return 0.0

        if len(self._rollout) < self.config.n_steps:
            return 0.0

        loss = self._ppo_update()
        self._rollout.clear()
        return loss

    def _ppo_update(self) -> float:
        """Выполнить n_epochs эпох PPO обновлений."""
        import torch
        import torch.nn.functional as F

        obs_a = np.array(self._rollout.obs)
        act_a = np.array(self._rollout.actions)
        rew_a = np.array(self._rollout.rewards, dtype=np.float32)
        val_a = np.array(self._rollout.values, dtype=np.float32)
        lp_a = np.array(self._rollout.log_probs, dtype=np.float32)
        done_a = np.array(self._rollout.dones, dtype=np.float32)

        # GAE advantages
        advantages = self._compute_gae(rew_a, val_a, done_a)
        returns = advantages + val_a
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        obs_t = torch.FloatTensor(obs_a)
        act_t = torch.FloatTensor(act_a)
        adv_t = torch.FloatTensor(advantages)
        ret_t = torch.FloatTensor(returns)
        old_lp_t = torch.FloatTensor(lp_a)

        total_loss = 0.0

        for _ in range(self.config.n_epochs):
            # Shuffle
            idx = torch.randperm(len(obs_t))
            for start in range(0, len(obs_t), self.config.batch_size):
                b = idx[start : start + self.config.batch_size]

                log_probs, entropy, values = self._net.evaluate(obs_t[b], act_t[b])

                # Ratio π_new / π_old
                ratio = torch.exp(log_probs - old_lp_t[b])

                # Clipped surrogate loss
                clip = self.config.clip_epsilon
                surr1 = ratio * adv_t[b]
                surr2 = torch.clamp(ratio, 1 - clip, 1 + clip) * adv_t[b]
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss
                value_loss = F.mse_loss(values, ret_t[b])

                # Entropy bonus
                entropy_loss = -entropy.mean()

                loss = (
                    policy_loss
                    + self.config.value_coeff * value_loss
                    + self.config.entropy_coeff * entropy_loss
                )

                self._net._optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    list(self._net._actor.parameters()) + list(self._net._critic.parameters()),
                    0.5,
                )
                self._net._optimizer.step()
                total_loss += float(loss.item())

        return total_loss / (self.config.n_epochs * max(1, len(obs_t) // self.config.batch_size))

    def _compute_gae(
        self,
        rewards: np.ndarray,
        values: np.ndarray,
        dones: np.ndarray,
        last_value: float = 0.0,
    ) -> np.ndarray:
        """Generalized Advantage Estimation."""
        n = len(rewards)
        advantages = np.zeros(n, dtype=np.float32)
        gae = 0.0

        for t in reversed(range(n)):
            next_val = last_value if t == n - 1 else values[t + 1]
            delta = rewards[t] + self.config.gamma * next_val * (1 - dones[t]) - values[t]
            gae = delta + self.config.gamma * self._gae_lambda * (1 - dones[t]) * gae
            advantages[t] = gae

        return advantages

    def save(self, path: str) -> None:
        if not self._built:
            return
        import torch

        torch.save(
            {
                "net": self._net.state_dict(),
                "total_steps": self._total_steps,
                "episode": self._episode,
            },
            path,
        )
        logger.info("[PPO] checkpoint saved → %s", path)

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        self._ensure_built()
        import torch

        ckpt = torch.load(path, map_location="cpu")
        self._net.load_state_dict(ckpt["net"])
        self._total_steps = ckpt.get("total_steps", 0)
        self._episode = ckpt.get("episode", 0)
        logger.info("[PPO] checkpoint loaded ← %s", path)
        return True
