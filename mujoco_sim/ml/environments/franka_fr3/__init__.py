"""
Franka FR3 MuJoCo Environment with Real Robot Bridge.

Пакет для работы с Franka FR3 в MuJoCo симуляции и реальном мире:
- FrankaFR3Controller: Контроллер симуляции FR3
- FrankaFR3Env: RL среда Gymnasium
- FrankaBridge: Мост для связи с реальным роботом

Пример:
    >>> from mujoco_sim.ml.environments.franka_fr3 import FrankaFR3Env
    >>> env = FrankaFR3Env(render_mode="rgb_array")
    >>> obs, info = env.reset()
    >>> action = env.action_space.sample()
    >>> obs, reward, terminated, truncated, info = env.step(action)
"""

from __future__ import annotations

from .controller import FrankaFR3Controller
from .environment import FrankaFR3Env
from .real_bridge import FrankaRealBridge

__all__ = [
    "FrankaFR3Controller",
    "FrankaFR3Env",
    "FrankaRealBridge",
]
