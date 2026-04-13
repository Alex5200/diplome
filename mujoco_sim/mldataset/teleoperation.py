"""
Keyboard Teleoperation for LeRobot Environment
Allows manual control of robot via keyboard for data collection
"""

import numpy as np
from typing import Optional, Tuple

try:
    import glfw

    GLFW_AVAILABLE = True
except ImportError:
    GLFW_AVAILABLE = False


# Keyboard key mappings (from lerobot-mujoco-tutorial)
KEY_MAPPING = {
    # Movement in XY plane
    "w": np.array([-0.007, 0.0, 0.0]),  # forward
    "s": np.array([0.007, 0.0, 0.0]),  # backward
    "a": np.array([0.0, -0.007, 0.0]),  # left
    "d": np.array([0.0, 0.007, 0.0]),  # right
    # Z axis
    "r": np.array([0.0, 0.0, 0.007]),  # up
    "f": np.array([0.0, 0.0, -0.007]),  # down
    # Rotation (roll-pitch-yaw)
    "q": np.array([0.0, 0.0, 0.1]),  # tilt left
    "e": np.array([0.0, 0.0, -0.1]),  # tilt right
}


class KeyboardTeleop:
    """
    Keyboard teleoperation for LeRobot environment.

    Controls:
    --------
    W/S     - Move forward/backward (X axis)
    A/D     - Move left/right (Y axis)
    R/F     - Move up/down (Z axis)
    Q/E     - Tilt left/right
    ↑/↓     - Pitch up/down
    ←/→     - Yaw left/right
    SPACE   - Toggle gripper
    Z       - Reset episode

    Action format: (7,) = [dx, dy, dz, droll, dpitch, dyaw, gripper]
    """

    def __init__(
        self,
        delta_position: float = 0.007,
        delta_rotation: float = 0.1,
    ):
        """
        Initialize keyboard teleoperation.

        Args:
            delta_position: Position delta per key press (meters)
            delta_rotation: Rotation delta per key press (radians)
        """
        self.delta_position = delta_position
        self.delta_rotation = delta_rotation

        # Current state
        self._position_delta = np.zeros(3)
        self._rotation_delta = np.zeros(3)
        self._gripper_state = 0.0  # 0 = open, 1 = closed
        self._reset_requested = False

        # Previous key states (for repeated presses)
        self._keys_pressed = set()
        self._keys_repeated = set()

    def get_action(self) -> np.ndarray:
        """
        Get current action from keyboard.

        Returns:
            action: (7,) array - [dx, dy, dz, droll, dpitch, dyaw, gripper]
        """
        # Build action
        action = np.zeros(7, dtype=np.float32)
        action[:3] = self._position_delta
        action[3:6] = self._rotation_delta
        action[6] = self._gripper_state

        return action

    def reset(self) -> None:
        """Reset teleoperation state."""
        self._position_delta = np.zeros(3)
        self._rotation_delta = np.zeros(3)
        self._reset_requested = False

    def is_reset_requested(self) -> bool:
        """Check if reset was requested."""
        return self._reset_requested

    def toggle_gripper(self) -> None:
        """Toggle gripper state."""
        self._gripper_state = 1.0 - self._gripper_state

    def process_key_event(self, key: int, action: int) -> None:
        """
        Process GLFW key event.

        Args:
            key: GLFW key code
            action: GLFW action (PRESS, REPEAT, RELEASE)
        """
        if not GLFW_AVAILABLE:
            return

        is_pressed = action == glfw.PRESS
        is_released = action == glfw.RELEASE
        is_repeated = action == glfw.REPEAT

        # Movement keys (WASD + RF)
        if key == glfw.KEY_W:
            self._update_delta("w", is_pressed or is_repeated, self.delta_position)
        elif key == glfw.KEY_S:
            self._update_delta("s", is_pressed or is_repeated, self.delta_position)
        elif key == glfw.KEY_A:
            self._update_delta("a", is_pressed or is_repeated, self.delta_position)
        elif key == glfw.KEY_D:
            self._update_delta("d", is_pressed or is_repeated, self.delta_position)
        elif key == glfw.KEY_R:
            self._update_delta("r", is_pressed or is_repeated, self.delta_position)
        elif key == glfw.KEY_F:
            self._update_delta("f", is_pressed or is_repeated, self.delta_position)

        # Rotation keys (QE)
        elif key == glfw.KEY_Q:
            self._update_delta("q", is_pressed or is_repeated, self.delta_rotation)
        elif key == glfw.KEY_E:
            self._update_delta("e", is_pressed or is_repeated, self.delta_rotation)

        # Arrow keys (rotation)
        elif key == glfw.KEY_LEFT:
            self._update_delta("left", is_pressed or is_repeated, self.delta_rotation)
        elif key == glfw.KEY_RIGHT:
            self._update_delta("right", is_pressed or is_repeated, self.delta_rotation)
        elif key == glfw.KEY_UP:
            self._update_delta("up", is_pressed or is_repeated, self.delta_rotation)
        elif key == glfw.KEY_DOWN:
            self._update_delta("down", is_pressed or is_repeated, self.delta_rotation)

        # Gripper toggle (SPACE)
        elif key == glfw.KEY_SPACE and is_pressed:
            self.toggle_gripper()

        # Reset (Z)
        elif key == glfw.KEY_Z and is_pressed:
            self._reset_requested = True

        # Update key sets
        if is_pressed:
            self._keys_pressed.add(key)
        elif is_released:
            self._keys_pressed.discard(key)
        if is_repeated:
            self._keys_repeated.add(key)

    def _update_delta(self, key: str, active: bool, delta: float) -> None:
        """Update position or rotation delta."""
        if key in ["w", "s"]:
            idx = 0
        elif key in ["a", "d"]:
            idx = 1
        elif key in ["r", "f"]:
            idx = 2
        elif key in ["q", "e"]:
            idx = 2  # yaw
        elif key == "left":
            idx = 0  # roll
        elif key == "right":
            idx = 0
        elif key == "up":
            idx = 1  # pitch
        elif key == "down":
            idx = 1
        else:
            return

        # Determine sign
        sign = 1.0 if key in ["s", "d", "f", "e", "right", "down"] else -1.0

        if key in ["w", "s", "a", "d", "r", "f"]:
            # Position delta
            self._position_delta[idx] = sign * delta if active else 0.0
        else:
            # Rotation delta
            self._rotation_delta[idx] = sign * delta if active else 0.0


def create_teleop_env():
    """
    Create teleoperation-enabled environment.

    Returns:
        Tuple of (environment, teleoperation)
    """
    from mujoco_sim.ml.environments.lerobot_env import LeRobotEnv

    env = LeRobotEnv()
    teleop = KeyboardTeleop()

    return env, teleop


if __name__ == "__main__":
    # Test teleoperation
    teleop = KeyboardTeleop()

    print("✓ KeyboardTeleop initialized")
    print("  Controls:")
    print("    W/S - Forward/backward")
    print("    A/D - Left/right")
    print("    R/F - Up/down")
    print("    Q/E - Tilt")
    print("    Arrows - Rotation")
    print("    SPACE - Gripper")
    print("    Z - Reset")
