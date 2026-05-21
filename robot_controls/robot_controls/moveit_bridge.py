import json
import math
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from sensor_msgs.msg import JointState
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

JOINT_NAMES = ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]


class MoveItBridge(Node):
    def __init__(self):
        super().__init__("moveit_bridge")

        self.declare_parameter("action_server_name", "/follow_joint_trajectory")
        self.declare_parameter("joint_tolerance", 0.05)
        self.declare_parameter("goal_time_seconds", 2.0)

        action_name = self.get_parameter("action_server_name").value
        self._joint_tolerance = self.get_parameter("joint_tolerance").value
        self._goal_time = self.get_parameter("goal_time_seconds").value

        self._current_joint_positions: list[float] = [0.0] * 6

        reliable = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )

        self._pub_target = self.create_publisher(
            PoseStamped, "/robot_controls/target_pose", reliable
        )
        self._pub_status = self.create_publisher(
            String, "/robot_controls/moveit/status", reliable
        )

        self.create_subscription(
            PoseStamped, "/robot_controls/moveit/goal", self._on_pose_goal, reliable
        )
        self.create_subscription(
            JointState, "/joint_states", self._on_joint_state, 10
        )

        self._action_client = ActionClient(
            self, FollowJointTrajectory, action_name
        )

        if not self._action_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().warn(
                f"Action server '{action_name}' not found. "
                "MoveIt trajectory execution disabled. "
                "Pose goals will be forwarded directly to /robot_controls/target_pose."
            )
        else:
            self.get_logger().info(
                f"Connected to action server '{action_name}'"
            )

        self.create_timer(5.0, self._publish_status)

        self.get_logger().info("MoveItBridge ready")
        self.get_logger().info("  Sub: /robot_controls/moveit/goal")
        self.get_logger().info("  Pub: /robot_controls/target_pose, /robot_controls/moveit/status")

    def _on_joint_state(self, msg: JointState):
        positions = list(msg.position)
        if len(positions) >= 6:
            self._current_joint_positions = positions[:6]

    def _on_pose_goal(self, msg: PoseStamped):
        x = msg.pose.position.x
        y = msg.pose.position.y
        z = msg.pose.position.z

        self.get_logger().info(
            f"Goal: ({x:.3f}, {y:.3f}, {z:.3f}) — "
            f"publishing to /robot_controls/target_pose"
        )

        self._pub_target.publish(msg)

        self._pub_status.publish(String(data=json.dumps({
            "success": True,
            "mode": "direct_forward",
            "goal": {"x": x, "y": y, "z": z},
        })))

    def send_joint_trajectory(self, positions_rad: list[float]):
        if not self._action_client.server_is_ready():
            self.get_logger().warn("Action server not ready, skipping trajectory")
            return False

        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = JOINT_NAMES

        point = JointTrajectoryPoint()
        point.positions = positions_rad
        point.velocities = [0.0] * 6
        point.time_from_start.sec = int(self._goal_time)
        point.time_from_start.nanosec = int((self._goal_time % 1) * 1e9)
        goal_msg.trajectory.points = [point]

        send_goal_future = self._action_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self._goal_response_callback)
        return True

    def _goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Trajectory goal rejected by MoveIt")
            return
        self.get_logger().info("Trajectory goal accepted by MoveIt")

    def _publish_status(self):
        status = String()
        status.data = json.dumps({
            "action_server_connected": self._action_client.server_is_ready(),
            "action_server": self.get_parameter("action_server_name").value,
            "current_joint_positions": [round(p, 4) for p in self._current_joint_positions],
        })
        self._pub_status.publish(status)


def main(args=None):
    rclpy.init(args=args)
    node = MoveItBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
