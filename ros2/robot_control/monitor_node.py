"""
monitor_node — publishes motor diagnostics to ROS2 topics.

Published topics:
    /robot/diagnostics  (std_msgs/String)  — full JSON diagnostics at 1 Hz
    /robot/temperature  (std_msgs/String)  — JSON map {motor_id: temp_c}
    /robot/alarms       (std_msgs/String)  — active alarms list

Usage:
    ros2 run robot_control monitor_node --ros-args -p port:=COM3
"""

from __future__ import annotations

import json
import os
import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.config.constants import TEMP_CRITICAL, TEMP_WARNING
from app.controllers.motor_controller import MotorController
from app.controllers.motor_monitor import MotorMonitor


class MonitorNode(Node):
    def __init__(self):
        super().__init__("monitor_node")

        self.declare_parameter("port", "COM3")
        self.declare_parameter("baudrate", 1_000_000)
        self.declare_parameter("publish_rate_hz", 1.0)

        port = self.get_parameter("port").value
        baudrate = self.get_parameter("baudrate").value
        rate_hz = self.get_parameter("publish_rate_hz").value

        self._ctrl = MotorController()
        self._monitor: MotorMonitor | None = None

        if self._ctrl.connect(port, baudrate):
            motors = self._ctrl.scan_motors()
            self._monitor = MotorMonitor(self._ctrl, motor_ids=motors, interval=0.5)
            self._monitor.start()
            self.get_logger().info(f"MonitorNode connected on {port}, motors: {motors}")
        else:
            self.get_logger().warn(f"Could not connect to {port}")

        self._pub_diag = self.create_publisher(String, "/robot/diagnostics", 10)
        self._pub_temps = self.create_publisher(String, "/robot/temperature", 10)
        self._pub_alarm = self.create_publisher(String, "/robot/alarms", 10)

        self.create_timer(1.0 / rate_hz, self._publish)

    def _publish(self) -> None:
        if not self._ctrl.is_connected:
            return

        motors = self._ctrl.get_connected_motors()
        diag: dict = {}
        temps: dict = {}
        alarms: list = []

        for mid in motors:
            data = self._ctrl.get_motor_data(mid)
            if not data:
                continue
            diag[str(mid)] = {
                "position": data.position,
                "temperature": data.temperature,
                "voltage": data.voltage,
                "current": data.current,
                "load": data.load,
                "status": str(data.status),
            }
            temps[str(mid)] = data.temperature
            if data.temperature >= TEMP_CRITICAL:
                alarms.append({"motor": mid, "type": "TEMP_CRITICAL", "value": data.temperature})
            elif data.temperature >= TEMP_WARNING:
                alarms.append({"motor": mid, "type": "TEMP_WARNING", "value": data.temperature})

        self._pub_diag.publish(String(data=json.dumps(diag)))
        self._pub_temps.publish(String(data=json.dumps(temps)))
        self._pub_alarm.publish(String(data=json.dumps(alarms)))

    def destroy_node(self):
        if self._monitor:
            self._monitor.stop()
        if self._ctrl.is_connected:
            self._ctrl.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
