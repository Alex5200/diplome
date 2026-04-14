#!/usr/bin/env python3
"""
monitor_node_v2 — publishes motor diagnostics using shared hardware interface.

Published topics:
    /robot/diagnostics  (std_msgs/String)  — full JSON diagnostics at 1 Hz
    /robot/temperature  (std_msgs/String)  — JSON map {motor_id: temp_c}
    /robot/alarms       (std_msgs/String)  — active alarms list

Usage:
    ros2 run robot_control monitor_node_v2
"""

from __future__ import annotations

import json
import os
import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hardware_interface import RobotHWInterface

# Temperature thresholds
TEMP_WARNING = 70
TEMP_CRITICAL = 80
LOAD_WARNING = 80


class MonitorNodeV2(Node):
    """Monitor node using shared hardware interface."""

    def __init__(self):
        super().__init__("monitor_node_v2")

        self.declare_parameter("publish_rate_hz", 1.0)
        rate_hz = self.get_parameter("publish_rate_hz").value

        # Use singleton hardware interface
        self._hw = RobotHWInterface.get_instance()

        # Wait for initialization
        if not self._hw.is_initialized():
            self.get_logger().warn("HW not initialized yet - will use when available")
        else:
            self.get_logger().info("Using existing hardware interface")

        # Publishers
        self._pub_diag = self.create_publisher(String, "/robot/diagnostics", 10)
        self._pub_temps = self.create_publisher(String, "/robot/temperature", 10)
        self._pub_alarm = self.create_publisher(String, "/robot/alarms", 10)

        # Timer
        self.create_timer(1.0 / rate_hz, self._publish)

        self.get_logger().info("monitor_node_v2 started")

    def _publish(self) -> None:
        """Publish diagnostics from shared cache."""
        if not self._hw.is_initialized():
            return

        motor_data = self._hw.get_all_motor_data()

        diag: dict = {}
        temps: dict = {}
        alarms: list = []

        for mid, data in motor_data.items():
            diag[str(mid)] = {
                "position": data.position,
                "temperature": data.temperature,
                "voltage": data.voltage,
                "current": data.current,
                "load": data.load,
                "mode": data.mode,
                "moving": data.moving,
                "status": data.status.value,
            }

            temps[str(mid)] = data.temperature

            # Check alarms
            if data.temperature >= TEMP_CRITICAL:
                alarms.append({"motor": mid, "type": "TEMP_CRITICAL", "value": data.temperature})
            elif data.temperature >= TEMP_WARNING:
                alarms.append({"motor": mid, "type": "TEMP_WARNING", "value": data.temperature})

            if data.load >= LOAD_WARNING:
                alarms.append({"motor": mid, "type": "OVERLOAD", "value": data.load})

        self._pub_diag.publish(String(data=json.dumps(diag)))
        self._pub_temps.publish(String(data=json.dumps(temps)))
        self._pub_alarm.publish(String(data=json.dumps(alarms)))


def main(args=None):
    rclpy.init(args=args)
    node = MonitorNodeV2()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
