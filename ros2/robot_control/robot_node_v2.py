#!/usr/bin/env python3
"""
robot_node_v2 — ROS2 node using RobotHWInterface singleton.

Published topics:
    /robot/joint_states   (sensor_msgs/JointState)  — current joint positions
    /robot/status         (std_msgs/String)          — JSON robot state

Subscribed topics:
    /robot/joint_cmd      (trajectory_msgs/JointTrajectoryPoint) — target joints
    /robot/stop           (std_msgs/Empty)            — emergency stop

Usage:
    ros2 run robot_control robot_node_v2 --ros-args -p port:=COM3
"""

from __future__ import annotations

import json
import os
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty, String
from trajectory_msgs.msg import JointTrajectoryPoint

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hardware_interface import RobotHWInterface

JOINT_NAMES = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]


class RobotNodeV2(Node):
    """Robot control node using shared hardware interface."""

    def __init__(self):
        super().__init__("robot_node_v2")

        # Parameters
        self.declare_parameter("port", "COM3")
        self.declare_parameter("baudrate", 1_000_000)
        self.declare_parameter("monitor_rate_hz", 50.0)

        port = self.get_parameter("port").value
        baudrate = self.get_parameter("baudrate").value
        rate_hz = self.get_parameter("monitor_rate_hz").value

        # Use singleton hardware interface
        self._hw = RobotHWInterface.get_instance()

        # Initialize hardware if not already done
        if not self._hw.is_initialized():
            if self._hw.initialize(port, baudrate, rate_hz):
                self.get_logger().info(f"Connected to robot on {port}")
            else:
                self.get_logger().warn(f"Could not connect to {port} — running in offline mode")
        else:
            self.get_logger().info("Using existing hardware interface")

        # Publishers
        self._pub_joints = self.create_publisher(JointState, "/robot/joint_states", 10)
        self._pub_status = self.create_publisher(String, "/robot/status", 10)

        # Subscribers
        self.create_subscription(JointTrajectoryPoint, "/robot/joint_cmd", self._on_joint_cmd, 10)
        self.create_subscription(Empty, "/robot/stop", self._on_stop, 10)

        # Publish timer
        self.create_timer(1.0 / rate_hz, self._publish_state)

        self.get_logger().info("robot_node_v2 started")

    def _publish_state(self) -> None:
        """Publish current joint states."""
        states = self._hw.read_joint_states()

        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = JOINT_NAMES

        for state in states:
            msg.position.append(state.position_rad)
            msg.velocity.append(state.velocity_rad_s)
            msg.effort.append(state.effort)

        self._pub_joints.publish(msg)

        # JSON status
        status: dict = {"connected": self._hw.is_connected(), "motors": {}}

        motor_data = self._hw.get_all_motor_data()
        for mid, data in motor_data.items():
            status["motors"][str(mid)] = {
                "position": data.position,
                "temperature": data.temperature,
            }

        self._pub_status.publish(String(data=json.dumps(status)))

    def _on_joint_cmd(self, msg: JointTrajectoryPoint) -> None:
        """Handle joint command."""
        if not self._hw.is_connected():
            self.get_logger().warn("Cannot move: not connected")
            return

        if len(msg.positions) != 6:
            self.get_logger().error(f"Expected 6 positions, got {len(msg.positions)}")
            return

        success = self._hw.write_joint_positions(list(msg.positions))
        if not success:
            self.get_logger().warn("Failed to send some joint commands")

    def _on_stop(self, _: Empty) -> None:
        """Emergency stop."""
        self.get_logger().warn("Emergency stop received")
        self._hw.emergency_stop()

    def destroy_node(self):
        """Cleanup on shutdown."""
        # Don't shutdown HW here - other nodes may be using it
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RobotNodeV2()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
