"""
Reinforcement Learning agents for robot control.
"""

from .base_agent import BaseAgent
from .dqn_agent import DQNAgent
from .ppo_agent import PPOAgent

__all__ = [
    "BaseAgent",
<<<<<<< HEAD
=======
    "DQNAgent",
    "PPOAgent",
>>>>>>> b5c93df3b58eceb91aa6e4d4c9cde48e4ac00ecb
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
