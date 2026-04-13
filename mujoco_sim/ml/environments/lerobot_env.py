"""
LeRobot Environment for MuJoCo
Gymnasium-compatible environment with LeRobot data format
"""

import numpy as np
from pathlib import Path
from typing import Any, Optional, Tuple

import mujoco

# Import robot generator
from mujoco_sim.ml.models.robot_generator import generate_robot_mjcf

# LeRobot data format constants
FPS = 20
DT = 1.0 / FPS  # 0.05 seconds per frame


class LeRobotEnv:
    """
    LeRobot-compatible MuJoCo environment.

    Features:
    - Action: (7,) = 6 joint angles + gripper (0/1)
    - Observation.state: (6,) = ee position (xyz) + orientation (rpy)
    - Observation.image: RGB from cameras

    Compatible with LeRobot dataset format.
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": FPS}

    def __init__(
        self,
        xml_string: Optional[str] = None,
        camera_width: int = 256,
        camera_height: int = 256,
        frame_skip: int = 5,
        max_episode_length: int = 500,
        render_mode: Optional[str] = None,
    ):
        """
        Initialize LeRobot environment.

        Args:
            xml_string: MJCF XML string. If None, generates from robot_config.json
            camera_width: Image width
            camera_height: Image height
            frame_skip: Physics steps per action
            max_episode_length: Maximum steps per episode
            render_mode: "human", "rgb_array", or None
        """
        # Generate XML if not provided
        if xml_string is None:
            xml_string = generate_robot_mjcf()

        # Create MuJoCo model and data
        self.model = mujoco.MjModel.from_xml_string(xml_string)
        self.data = mujoco.MjData(self.model)

        # Configuration
        self.camera_width = camera_width
        self.camera_height = camera_height
        self.frame_skip = frame_skip
        self.max_episode_length = max_episode_length
        self.render_mode = render_mode

        # State tracking
        self._step_count = 0
        self._episode_started = False

        # Joint names
        self.joint_names = [f"joint_{i}" for i in range(6)]

        # Camera IDs
        self._camera_ids = {}
        for cam_name in ["top_down", "egocentric", "agentview"]:
            cam_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, cam_name)
            if cam_id >= 0:
                self._camera_ids[cam_name] = cam_id

    def reset(self, seed: Optional[int] = None) -> Tuple[dict, dict]:
        """
        Reset environment to initial state.

        Returns:
            observation: dict with state and image
            info: additional information
        """
        # Reset MuJoCo data
        mujoco.mj_resetData(self.model, self.data)

        # Set initial joint positions (all zeros)
        self.data.qpos[:6] = 0.0

        # Run forward to stabilize
        mujoco.mj_step(self.model, self.data)

        # Reset counters
        self._step_count = 0
        self._episode_started = True

        return self._get_obs(), self._get_info()

    def step(self, action: np.ndarray) -> Tuple[dict, float, bool, bool, dict]:
        """
        Execute one environment step.

        Args:
            action: (7,) array - 6 joint angles + gripper

        Returns:
            observation: dict with state and image
            reward: float reward
            terminated: bool (episode done)
            truncated: bool (max steps reached)
            info: dict
        """
        self._step_count += 1

        # Apply action (joint positions)
        if len(action) >= 6:
            self.data.ctrl[:6] = action[:6]

        # Run physics
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)

        # Get observation
        obs = self._get_obs()

        # Compute reward (distance to target, can be customized)
        reward = self._compute_reward(obs)

        # Check termination conditions
        terminated = False  # Can be customized (e.g., success condition)
        truncated = self._step_count >= self.max_episode_length

        info = self._get_info()
        info["step"] = self._step_count

        return obs, reward, terminated, truncated, info

    def _get_obs(self) -> dict:
        """
        Get LeRobot-format observation.

        Returns:
            dict with:
            - observation.state: (6,) = [x, y, z, roll, pitch, yaw]
            - observation.image: RGB from agentview camera
            - observation.wrist_image: RGB from egocentric camera (optional)
        """
        # Get joint positions
        joint_pos = self.data.qpos[:6].copy()

        # Get end-effector position (from site)
        ee_pos = self.data.site_xpos[0].copy() if self.model.nsite > 0 else np.zeros(3)

        # Compute orientation (roll-pitch-yaw) from end-effector rotation
        ee_quat = self.data.site_xmat[0].copy() if self.model.nsite > 0 else np.eye(3).flatten()
        rpy = self._quat_to_rpy(ee_quat)

        # State observation
        state = np.concatenate([ee_pos, rpy], dtype=np.float32)

        # Image observation (from camera)
        rgb_image = self._render_camera("agentview")

        obs = {
            "observation.state": state,
            "observation.image": rgb_image,
        }

        return obs

    def _get_info(self) -> dict:
        """Get additional information."""
        return {
            "ee_position": self.data.site_xpos[0].copy() if self.model.nsite > 0 else np.zeros(3),
            "joint_angles": self.data.qpos[:6].copy(),
            "joint_velocities": self.data.qvel[:6].copy(),
        }

    def _compute_reward(self, obs: dict) -> float:
        """Compute reward. Simple version - can be customized."""
        # Default: small negative reward to encourage progress
        return -0.01

    def _render_camera(self, camera_name: str) -> np.ndarray:
        """
        Render image from camera.

        Args:
            camera_name: "top_down", "egocentric", or "agentview"

        Returns:
            RGB image array (height, width, 3)
        """
        cam_id = self._camera_ids.get(camera_name)
        if cam_id is None:
            # Return black image if camera not found
            return np.zeros((self.camera_height, self.camera_width, 3), dtype=np.uint8)

        # Configure camera
        self.model.cam_fovy[cam_id] = 60

        # Render
        width = self.camera_width
        height = self.camera_height

        # Create buffers
        rgb = np.zeros((height, width, 3), dtype=np.uint8)

        # Use offscreen rendering
        # Note: requires GLFW for actual rendering
        # For headless, use renderer

        return rgb

    def _quat_to_rpy(self, quat: np.ndarray) -> np.ndarray:
        """Convert quaternion to roll-pitch-yaw."""
        # Simplified conversion
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (quat[0] * quat[1] + quat[2] * quat[3])
        cosr_cosp = 1 - 2 * (quat[1] ** 2 + quat[2] ** 2)
        roll = np.arctan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2 * (quat[0] * quat[2] - quat[3] * quat[1])
        if np.abs(sinp) >= 1:
            pitch = np.copysign(np.pi / 2, sinp)
        else:
            pitch = np.arcsin(sinp)

        # Yaw (z-axis rotation)
        siny_cosp = 2 * (quat[0] * quat[3] + quat[1] * quat[2])
        cosy_cosp = 1 - 2 * (quat[2] ** 2 + quat[3] ** 2)
        yaw = np.arctan2(siny_cosp, cosy_cosp)

        return np.array([roll, pitch, yaw], dtype=np.float32)

    def render(self) -> Optional[np.ndarray]:
        """Render current state."""
        if self.render_mode == "rgb_array":
            return self._render_camera("agentview")
        return None

    def close(self) -> None:
        """Clean up resources."""
        # MuJoCo cleanup if needed
        pass

    def get_joint_angles(self) -> np.ndarray:
        """Get current joint angles."""
        return self.data.qpos[:6].copy()

    def set_joint_angles(self, angles: np.ndarray, immediate: bool = False) -> None:
        """Set joint angles."""
        if len(angles) >= 6:
            self.data.qpos[:6] = angles[:6]
            if immediate:
                mujoco.mj_step(self.model, self.data)

    def get_ee_position(self) -> np.ndarray:
        """Get end-effector position."""
        if self.model.nsite > 0:
            return self.data.site_xpos[0].copy()
        return np.zeros(3)


# Convenience function
def create_env(xml_string: Optional[str] = None, **kwargs) -> LeRobotEnv:
    """
    Create LeRobot environment.

    Args:
        xml_string: Optional MJCF XML
        **kwargs: Additional arguments to LeRobotEnv

    Returns:
        LeRobotEnv instance
    """
    return LeRobotEnv(xml_string=xml_string, **kwargs)


if __name__ == "__main__":
    # Test environment
    env = LeRobotEnv()

    # Reset
    obs, info = env.reset()

    print("✓ Environment initialized")
    print(f"  State shape: {obs['observation.state'].shape}")
    print(f"  Image shape: {obs['observation.image'].shape}")

    # Test step
    action = np.zeros(7, dtype=np.float32)  # Hold position
    obs, reward, terminated, truncated, info = env.step(action)

    print(f"✓ Step executed")
    print(f"  Reward: {reward:.3f}")
    print(f"  EE position: {info['ee_position']}")
