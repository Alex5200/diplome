#!/usr/bin/env python3
"""
RL Training Module — обучение с подкреплением для робота-манипулятора.

Доступные агенты:
    DQNAgent   — Deep Q-Network (дискретные действия)
    PPOAgent   — Proximal Policy Optimization (непрерывные действия)

Среды:
    RobotArmEnv — Gym-совместимая среда для 6-DOF манипулятора

Функции наград:
    DistanceReward, SmoothMotionReward, PickPlaceReward,
    VisionReward, CompositeReward

Использование:
    from app.models.rl import DQNAgent, PPOAgent, RobotArmEnv
    from app.models.rl import CompositeReward, DistanceReward, PickPlaceReward
"""

from .base_agent import BaseRLAgent, Episode, TrainingConfig
from .dqn_agent import DQNAgent
from .environment import RobotArmConfig, RobotArmEnv
from .ppo_agent import PPOAgent
from .rewards import (
    CompositeReward,
    DistanceReward,
    PickPlaceReward,
    SmoothMotionReward,
    VisionReward,
)

__all__ = [
    # Agents
    "BaseRLAgent",
    "DQNAgent",
    "PPOAgent",
    # Environment
    "RobotArmEnv",
    "RobotArmConfig",
    # Rewards
    "CompositeReward",
    "DistanceReward",
    "PickPlaceReward",
    "SmoothMotionReward",
    "VisionReward",
    # Data
    "Episode",
    "TrainingConfig",
]
