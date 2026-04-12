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
import os
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty, String
from std_srvs.srv import SetBool
from trajectory_msgs.msg import JointTrajectoryPoint

# Allow importing shared layer without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.controllers.motor_controller import MotorController
from app.controllers.motor_monitor import MotorMonitor
from app.utils.config_manager import ConfigManager

JOINT_NAMES = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]


class RobotNode(Node):
    def __init__(self):
        super().__init__("robot_node")

        # Parameters
        self.declare_parameter("port", "COM3")
        self.declare_parameter("baudrate", 1_000_000)
        self.declare_parameter("monitor_rate_hz", 10.0)

        port = self.get_parameter("port").value
        baudrate = self.get_parameter("baudrate").value
        rate_hz = self.get_parameter("monitor_rate_hz").value

        # Hardware
        self._ctrl = MotorController()
        self._monitor: MotorMonitor | None = None
        self._cfg = ConfigManager()

        # Connect
        if self._ctrl.connect(port):
            self._ctrl.scan_servos()
            self.get_logger().info(f"Connected to robot on {port}")
            self._start_monitor(rate_hz)
        else:
            self.get_logger().warn(f"Could not connect to {port} — running in offline mode")

        # Publishers
        self._pub_joints = self.create_publisher(JointState, "/robot/joint_states", 10)
        self._pub_status = self.create_publisher(String, "/robot/status", 10)

        # Subscribers
        self.create_subscription(JointTrajectoryPoint, "/robot/joint_cmd", self._on_joint_cmd, 10)
        self.create_subscription(Empty, "/robot/stop", self._on_stop, 10)

        # Service
        self.create_service(SetBool, "/robot/connect", self._on_connect_srv)

        # Publish timer
        self.create_timer(1.0 / rate_hz, self._publish_state)

        self.get_logger().info("robot_node started")

    # ------------------------------------------------------------------
    def _start_monitor(self, rate_hz: float) -> None:
        interval = 1.0 / rate_hz
        motor_ids = self._ctrl.scan_servos()
        if not isinstance(motor_ids, list):
            return

        self._monitor = MotorMonitor(
            motor_controller=self._ctrl,
            update_callback=None,
        )

    def _publish_state(self) -> None:
        if not self._ctrl.connected:
            return
        motors = self._ctrl.found_servos  # Corrected method call to scan_servos instead of connect
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = JOINT_NAMES[: len(motors)]
        for mid in motors:
            data = self._ctrl.read_motor_data(mid)  # Corrected method call to read_motor_data
            pos_rad = 0.0
            if data:
                angle_deg = (data["position"] / 4095.0) * 360.0 - 180.0
                pos_rad = math.radians(angle_deg)
            msg.position.append(pos_rad)

        # JSON status
        status: dict = {"connected": True, "motors": {}}
        for mid in motors:
            data = self._ctrl.read_motor_data(
                sts_id=mid
            )  # Corrected method call to read_motor_data
            if data:
                status["motors"][str(mid)] = {
                    "position": data.get("position", None),
                    "temperature": data.get("temperature", None),
                }
        self._pub_status.publish(String(data=json.dumps(status)))

    def _on_joint_cmd(self, msg: JointTrajectoryPoint) -> None:
        if not self._ctrl.connected:
            return
        import math

        motors = self._ctrl.found_servos
        for i, pos_rad in enumerate(msg.positions):
            if i >= len(motors):
                break
            angle_deg = math.degrees(pos_rad)
            position = int((angle_deg + 180.0) / 360.0 * 4095)
            position = max(0, min(4095, position))
            self._ctrl.move_joint(motors[i], position)

    def _on_stop(self, _: Empty) -> None:
        self.get_logger().warn("Emergency stop received")
        if self._ctrl.connected:
            self._ctrl.emergency_stop_all()

    def _on_connect_srv(self, req: SetBool.Request, res: SetBool.Response):
        port = self.get_parameter("port").value
        if req.data:
            ok = self._ctrl.connect(port)
            if ok:
                self._ctrl.scan_servos()
                self._start_monitor(self.get_parameter("monitor_rate_hz").value)
            res.success = ok
            res.message = f"Connected to {port}" if ok else f"Failed to connect to {port}"
        else:
            if self._monitor:
                self._monitor.stop()
            self._ctrl.disconnect()
            res.success = True
            res.message = "Disconnected"
        return res

    def destroy_node(self):
        if self._monitor:
            self._monitor.stop()
        if self._ctrl.connected:
            self._ctrl.disconnect()
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
