"""
robot_node — main ROS2 node for ST3215 robot control.

Published topics:
    /robot/joint_states   (sensor_msgs/JointState)  — current joint positions
    /robot/status         (std_msgs/String)          — JSON robot state

Subscribed topics:
    /robot/joint_cmd      (trajectory_msgs/JointTrajectoryPoint) — target joints
    /robot/stop           (std_msgs/Empty)            — emergency stop

Services:
    /robot/connect        (std_srvs/SetBool)          — connect/disconnect

Usage:
    ros2 run robot_control robot_node --ros-args -p port:=COM3
"""

from __future__ import annotations

import json
import math
import threading

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty, String
from std_srvs.srv import SetBool
from trajectory_msgs.msg import JointTrajectoryPoint

from core.kinematics import RobotKinematics6DOF
from core.motor_data import MotorData, RobotState

JOINT_NAMES = ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]


class RobotNode(Node):
    def __init__(self):
        super().__init__("robot_node")

        self.declare_parameter("port", "COM3")
        self.declare_parameter("baudrate", 1_000_000)
        self.declare_parameter("monitor_rate_hz", 10.0)

        port = self.get_parameter("port").value
        baudrate = self.get_parameter("baudrate").value
        rate_hz = self.get_parameter("monitor_rate_hz").value

        from robot_control.hardware_interface import RobotHWInterface
        self._hw = RobotHWInterface.get_instance()
        self._connected = self._hw.initialize(port, baudrate, rate_hz)

        if self._connected:
            self.get_logger().info(f"Connected to robot on {port}")
        else:
            self.get_logger().warn(f"Could not connect to {port} — running in offline mode")

        self._kinematics = RobotKinematics6DOF()

        self._pub_joints = self.create_publisher(JointState, "/robot/joint_states", 10)
        self._pub_status = self.create_publisher(String, "/robot/status", 10)

        self.create_subscription(JointTrajectoryPoint, "/robot/joint_cmd", self._on_joint_cmd, 10)
        self.create_subscription(Empty, "/robot/stop", self._on_stop, 10)

        self.create_service(SetBool, "/robot/connect", self._on_connect_srv)

        self.create_timer(1.0 / rate_hz, self._publish_state)

        self.get_logger().info("robot_node started")

    def _publish_state(self) -> None:
        if not self._connected:
            return

        states = self._hw.read_joint_states()
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = JOINT_NAMES
        msg.position = [s.position_rad for s in states]

        status: dict = {"connected": True, "motors": {}}
        for i, state in enumerate(states):
            status["motors"][i + 1] = {"position": state.position_raw}

        self._pub_joints.publish(msg)
        self._pub_status.publish(String(data=json.dumps(status)))

    def _on_joint_cmd(self, msg: JointTrajectoryPoint) -> None:
        if not self._connected:
            return

        positions = list(msg.positions[:6])
        while len(positions) < 6:
            positions.append(0.0)
        self._hw.write_joint_positions(positions)

    def _on_stop(self, _: Empty) -> None:
        self.get_logger().warn("Emergency stop received")
        if self._connected:
            self._hw.emergency_stop()

    def _on_connect_srv(self, req: SetBool.Request, res: SetBool.Response):
        port = self.get_parameter("port").value
        if req.data:
            ok = self._hw.initialize(port, 1000000, 10.0)
            self._connected = ok
            res.success = ok
            res.message = f"Connected to {port}" if ok else f"Failed to connect to {port}"
        else:
            self._hw.shutdown()
            self._connected = False
            res.success = True
            res.message = "Disconnected"
        return res

    def destroy_node(self):
        self._hw.shutdown()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RobotNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
