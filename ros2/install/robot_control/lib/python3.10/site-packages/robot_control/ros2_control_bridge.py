#!/usr/bin/env python3
"""
ros2_control Bridge Node.

Мост между ros2_control (mock_components/GenericSystem) и реальным железом.

Архитектура:
  ┌─────────────────────────────────────────────────────────────────┐
  │  JointTrajectoryController (ros2_control)                       │
  │    writes position commands → mock hardware state               │
  │    publishes /joint_trajectory_controller/state (desired pos)   │
  └────────────────────────────┬────────────────────────────────────┘
                               │ /joint_trajectory_controller/state
                               ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  Ros2ControlBridge  (этот узел)                                │
  │    1. Читает desired positions из JTC state                    │
  │    2. Пишет в RobotHWInterface → MotorController → ST3215     │
  │    3. Читает реальные позиции из RobotHWInterface              │
  │    4. Публикует реальные /joint_states для мониторинга         │
  └────────────────────────────────────────────────────────────────┘

Параметры:
    port            (str)   — serial port (default: "COM3")
    baudrate        (int)   — serial baudrate (default: 1000000)
    monitor_rate_hz (float) — hardware polling rate (default: 50.0)
    command_timeout (float) — stop forwarding if no command for N sec (default: 1.0)

Топики:
    Subscribed:
        /joint_trajectory_controller/state  (control_msgs/JointTrajectoryControllerState)
        /robot/stop                         (std_msgs/Empty)
    Published:
        /joint_states                       (sensor_msgs/JointState)  — реальные позиции
        /ros2_control_bridge/status         (std_msgs/String)

Usage:
    ros2 run robot_control ros2_control_bridge --ros-args -p port:=/dev/ttyUSB0
"""

from __future__ import annotations

import sys
import os
import math
import time
import threading
from typing import Optional

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import JointState
from std_msgs.msg import String, Empty

# Import JTC state message — available with ros2_controllers
try:
    from control_msgs.msg import JointTrajectoryControllerState
    _HAS_CONTROL_MSGS = True
except ImportError:
    _HAS_CONTROL_MSGS = False

# Allow importing from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from robot_control.hardware_interface import RobotHWInterface

# Joint names matching the URDF
JOINT_NAMES = ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]


class Ros2ControlBridge(Node):
    """
    Bridge between ros2_control JointTrajectoryController and real hardware.

    Subscribes to JTC desired-state topic, forwards position commands to
    RobotHWInterface, and publishes actual hardware positions back.
    """

    def __init__(self) -> None:
        super().__init__("ros2_control_bridge")

        # ── Parameters ──────────────────────────────────────────────────
        self.declare_parameter("port",            "COM3")
        self.declare_parameter("baudrate",        1_000_000)
        self.declare_parameter("monitor_rate_hz", 50.0)
        self.declare_parameter("command_timeout", 1.0)

        port            = self.get_parameter("port").value
        baudrate        = self.get_parameter("baudrate").value
        monitor_rate_hz = self.get_parameter("monitor_rate_hz").value
        self._cmd_timeout = self.get_parameter("command_timeout").value

        # ── Hardware interface ───────────────────────────────────────────
        self._hw = RobotHWInterface.get_instance()
        connected = self._hw.initialize(port, baudrate, monitor_rate_hz)
        if connected:
            self.get_logger().info(f"Hardware connected: port={port}")
        else:
            self.get_logger().warn(
                f"Hardware NOT connected (port={port}). "
                "Bridge running in simulation mode."
            )

        # ── State ────────────────────────────────────────────────────────
        self._last_cmd_time: float = 0.0
        self._cmd_lock = threading.Lock()

        # ── Subscribers ──────────────────────────────────────────────────
        if _HAS_CONTROL_MSGS:
            self.create_subscription(
                JointTrajectoryControllerState,
                "/joint_trajectory_controller/state",
                self._on_jtc_state,
                10,
            )
            self.get_logger().info(
                "Subscribed to /joint_trajectory_controller/state "
                "(control_msgs/JointTrajectoryControllerState)"
            )
        else:
            self.get_logger().warn(
                "control_msgs not available — "
                "install ros-humble-control-msgs to enable JTC forwarding. "
                "Only /robot/joint_cmd topic will be accepted."
            )

        # Fallback: accept existing /robot/joint_cmd as well
        from trajectory_msgs.msg import JointTrajectoryPoint
        self.create_subscription(
            JointTrajectoryPoint,
            "/robot/joint_cmd",
            self._on_joint_cmd,
            10,
        )

        # Emergency stop
        self.create_subscription(
            Empty,
            "/robot/stop",
            self._on_stop,
            10,
        )

        # ── Publishers ───────────────────────────────────────────────────
        self._joint_states_pub = self.create_publisher(
            JointState, "/joint_states", 10
        )
        self._status_pub = self.create_publisher(
            String, "/ros2_control_bridge/status", 10
        )

        # ── Timers ───────────────────────────────────────────────────────
        # Publish actual hardware state at 50 Hz
        self.create_timer(1.0 / 50.0, self._publish_joint_states)
        # Status log every 5 s
        self.create_timer(5.0, self._publish_status)

        self.get_logger().info("Ros2ControlBridge ready.")

    # ──────────────────────────────────────────────────────────────────────
    # Command callbacks
    # ──────────────────────────────────────────────────────────────────────

    def _on_jtc_state(self, msg: "JointTrajectoryControllerState") -> None:
        """
        Called at ~50 Hz by JointTrajectoryController.
        msg.desired.positions contains the commanded joint positions (rad).
        Forward them to real hardware.
        """
        positions = list(msg.desired.positions)
        if len(positions) < 6:
            return
        self._send_to_hardware(positions[:6])

    def _on_joint_cmd(self, msg) -> None:
        """Fallback: accept /robot/joint_cmd (JointTrajectoryPoint)."""
        positions = list(msg.positions)
        if len(positions) < 6:
            return
        self._send_to_hardware(positions[:6])

    def _on_stop(self, _msg: Empty) -> None:
        """Emergency stop — halt all motors immediately."""
        self._hw.emergency_stop()
        self.get_logger().warn("Emergency stop received!")

    def _send_to_hardware(self, positions_rad: list[float]) -> None:
        """Write position commands to real hardware via RobotHWInterface."""
        if not self._hw.is_connected():
            return
        with self._cmd_lock:
            self._last_cmd_time = time.time()
        self._hw.write_joint_positions(positions_rad)

    # ──────────────────────────────────────────────────────────────────────
    # State publishing
    # ──────────────────────────────────────────────────────────────────────

    def _publish_joint_states(self) -> None:
        """Read actual hardware positions and publish as /joint_states."""
        states = self._hw.read_joint_states()

        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = JOINT_NAMES

        for js in states:
            msg.position.append(js.position_rad)
            msg.velocity.append(js.velocity_rad_s)
            msg.effort.append(js.effort)

        self._joint_states_pub.publish(msg)

    def _publish_status(self) -> None:
        """Publish bridge status string."""
        with self._cmd_lock:
            last_cmd_age = time.time() - self._last_cmd_time if self._last_cmd_time else -1.0

        connected = self._hw.is_connected()
        status = String()
        status.data = (
            f"connected={connected} "
            f"last_cmd_age={last_cmd_age:.1f}s "
            f"control_msgs={_HAS_CONTROL_MSGS}"
        )
        self._status_pub.publish(status)

    # ──────────────────────────────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────────────────────────────

    def destroy_node(self) -> None:
        self._hw.shutdown()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Ros2ControlBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
