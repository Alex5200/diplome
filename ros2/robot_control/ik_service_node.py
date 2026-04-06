"""
ik_service_node — exposes IK solver as a ROS2 service.

Service:
    /robot/ik  (custom: IKSolve)
        Request:  float64 x, float64 y, float64 z
        Response: float64[] angles_deg, float64 error_mm, bool success

Since custom .srv files require colcon build, we use std_msgs/String as
a simple JSON-over-ROS2 transport for prototyping:
    Request:  String  '{"x": 150, "y": 0, "z": 100}'
    Response: String  '{"angles_deg": [...], "error_mm": 0.3, "success": true}'

Usage:
    ros2 run robot_control ik_service_node
    ros2 service call /robot/ik std_msgs/String '{"data": "{\"x\":150,\"y\":0,\"z\":100}"}'
"""

from __future__ import annotations

import json
import sys
import os

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger  # used as a ping; actual IK uses String topic pair
from std_msgs.msg import String

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.models.kinematics import RobotKinematics6DOF, InverseKinematics6DOF


class IKServiceNode(Node):
    def __init__(self):
        super().__init__("ik_service_node")

        self._kin = RobotKinematics6DOF()
        self._ik = InverseKinematics6DOF(self._kin)

        # Request subscriber + response publisher (JSON-over-topics pattern)
        self._pub = self.create_publisher(String, "/robot/ik/response", 10)
        self.create_subscription(String, "/robot/ik/request", self._on_request, 10)

        self.get_logger().info("ik_service_node ready — listening on /robot/ik/request")

    def _on_request(self, msg: String) -> None:
        try:
            req = json.loads(msg.data)
            x, y, z = float(req["x"]), float(req["y"]), float(req["z"])
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self._pub.publish(
                String(data=json.dumps({"success": False, "error": str(e)}))
            )
            return

        result = self._ik.solve(x, y, z)
        if result is None:
            self._pub.publish(
                String(data=json.dumps({"success": False, "error": "unreachable"}))
            )
        else:
            angles, error = result
            self._pub.publish(
                String(
                    data=json.dumps(
                        {
                            "success": True,
                            "angles_deg": [round(a, 4) for a in angles],
                            "error_mm": round(error, 4),
                        }
                    )
                )
            )


def main(args=None):
    rclpy.init(args=args)
    node = IKServiceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
