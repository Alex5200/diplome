"""
Reinforcement Learning agents for robot control.
"""

from .base_agent import BaseAgent

__all__ = [
    "BaseAgent",
]

# Optional: import concrete agents if available
try:
    from .ppo_agent import PPOAgent
    __all__.append("PPOAgent")
except ImportError:
    pass

try:
    from .dqn_agent import DQNAgent
    __all__.append("DQNAgent")
except ImportError:
    pass
