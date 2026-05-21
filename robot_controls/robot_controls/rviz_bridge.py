import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped, PoseStamped
from visualization_msgs.msg import Marker
from std_msgs.msg import ColorRGBA
from builtin_interfaces.msg import Duration


class RvizBridge(Node):
    def __init__(self):
        super().__init__("rviz_bridge")

        self._pub_pose = self.create_publisher(PoseStamped, "/robot_controls/target_pose", 10)
        self._pub_marker = self.create_publisher(Marker, "/robot_controls/target_marker", 10)

        self.create_subscription(PointStamped, "/clicked_point", self._on_clicked_point, 10)

        self.get_logger().info("RvizBridge ready")
        self.get_logger().info("  Click in RViz with Publish Point → robot moves")

    def _on_clicked_point(self, msg: PointStamped):
        x, y, z = msg.point.x, msg.point.y, msg.point.z

        self.get_logger().info(f"Clicked: ({x:.3f}, {y:.3f}, {z:.3f})")

        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = msg.header.frame_id
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = z
        pose.pose.orientation.w = 1.0
        self._pub_pose.publish(pose)

        self._publish_marker(x, y, z)

    def _publish_marker(self, x, y, z):
        marker = Marker()
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.header.frame_id = "base_link"
        marker.ns = "target"
        marker.id = 0
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        marker.pose.position.x = x
        marker.pose.position.y = y
        marker.pose.position.z = z
        marker.pose.orientation.w = 1.0
        marker.scale.x = 0.02
        marker.scale.y = 0.02
        marker.scale.z = 0.02
        marker.color = ColorRGBA(r=0.0, g=1.0, b=0.0, a=0.8)
        marker.lifetime = Duration(sec=5)
        self._pub_marker.publish(marker)


def main(args=None):
    rclpy.init(args=args)
    node = RvizBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
