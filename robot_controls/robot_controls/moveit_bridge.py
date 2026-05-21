import json
import math
from typing import Optional

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

try:
    from moveit_commander import MoveGroupInterface, PlanningSceneInterface, RobotCommander
    from moveit_commander.exception import MoveItCommanderException
    _HAS_MOVEIT = True
except ImportError:
    _HAS_MOVEIT = False


class MoveItBridge(Node):
    def __init__(self):
        super().__init__("moveit_bridge")

        self.declare_parameter("move_group_name", "arm")
        self.declare_parameter("planning_frame", "base_link")
        self.declare_parameter("max_planning_attempts", 10)

        move_group_name = self.get_parameter("move_group_name").value
        self._planning_frame = self.get_parameter("planning_frame").value
        max_attempts = self.get_parameter("max_planning_attempts").value

        self._move_group: Optional[MoveGroupInterface] = None
        self._connected = False

        if not _HAS_MOVEIT:
            self.get_logger().error(
                "moveit_commander not available. Install: sudo apt install ros-humble-moveit-commander"
            )
        else:
            try:
                self._move_group = MoveGroupInterface(move_group_name)
                self._move_group.set_planning_time(5.0)
                self._move_group.set_num_planning_attempts(max_attempts)
                self._move_group.set_pose_reference_frame(self._planning_frame)
                self._connected = True
                self.get_logger().info(
                    f"Connected to MoveGroup '{move_group_name}' | "
                    f"frame: {self._planning_frame}"
                )
            except MoveItCommanderException as e:
                self.get_logger().error(f"Failed to connect to MoveGroup: {e}")
            except RuntimeError as e:
                self.get_logger().error(
                    f"Cannot connect to move_group. Is it running? {e}"
                )

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
            PoseStamped, "/robot_controls/moveit/goal", self._on_goal, reliable
        )

        self.create_timer(5.0, self._publish_status)

        self.get_logger().info("MoveItBridge ready")
        self.get_logger().info("  Sub: /robot_controls/moveit/goal")
        self.get_logger().info("  Pub: /robot_controls/target_pose")

    def _on_goal(self, msg: PoseStamped):
        if not self._connected or self._move_group is None:
            self.get_logger().warn("MoveGroup not connected — skipping goal")
            return

        try:
            self._move_group.set_pose_target(msg)

            plan = self._move_group.plan()

            if not plan or (isinstance(plan, tuple) and not plan[0]):
                self.get_logger().error("MoveIt planning failed — unreachable goal")
                self._pub_status.publish(String(data=json.dumps({
                    "success": False,
                    "error": "planning_failed",
                    "goal": {
                        "x": msg.pose.position.x,
                        "y": msg.pose.position.y,
                        "z": msg.pose.position.z,
                    }
                })))
                return

            self.get_logger().info(
                f"MoveIt plan success — forwarding to hardware: "
                f"({msg.pose.position.x:.3f}, {msg.pose.position.y:.3f}, {msg.pose.position.z:.3f})"
            )

            self._pub_target.publish(msg)

            self._move_group.stop()
            self._move_group.clear_pose_targets()

            self._pub_status.publish(String(data=json.dumps({
                "success": True,
                "goal": {
                    "x": msg.pose.position.x,
                    "y": msg.pose.position.y,
                    "z": msg.pose.position.z,
                }
            })))

        except MoveItCommanderException as e:
            self.get_logger().error(f"MoveIt error: {e}")
        except Exception as e:
            self.get_logger().error(f"Unexpected error: {e}")

    def _publish_status(self):
        status = String()
        status.data = json.dumps({
            "connected": self._connected,
            "move_group": self.get_parameter("move_group_name").value if self._connected else None,
            "planning_frame": self._planning_frame if self._connected else None,
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
