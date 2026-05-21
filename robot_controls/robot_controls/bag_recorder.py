import sys
import time
import threading
from datetime import datetime

import rclpy
from rclpy.node import Node
from rclpy.serialization import serialize_message
from std_msgs.msg import String, Empty
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseStamped

try:
    import rosbag2_py
    _HAS_ROSBAG2 = True
except ImportError:
    _HAS_ROSBAG2 = False

ROBOT_TOPICS: dict[str, str] = {
    "/joint_states":                       "sensor_msgs/msg/JointState",
    "/robot_controls/joint_states":        "sensor_msgs/msg/JointState",
    "/robot_controls/target_pose":         "geometry_msgs/msg/PoseStamped",
    "/robot_controls/parameters/cmd":      "std_msgs/msg/String",
    "/robot_controls/parameters/state":    "std_msgs/msg/String",
    "/robot_controls/status":              "std_msgs/msg/String",
    "/robot_controls/stop":                "std_msgs/msg/Empty",
}


class BagRecorder(Node):
    def __init__(self):
        super().__init__("bag_recorder")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.declare_parameter("bag_path", f"robot_bag_{timestamp}")
        self.declare_parameter("storage_id", "sqlite3")
        self.declare_parameter("topics", list(ROBOT_TOPICS.keys()))

        self._bag_path = self.get_parameter("bag_path").value
        self._storage_id = self.get_parameter("storage_id").value
        self._topics = self.get_parameter("topics").value

        self._writer = None
        self._write_lock = threading.Lock()
        self._msg_count: dict[str, int] = {t: 0 for t in self._topics}
        self._recording = False
        self._subs = []

        self._status_pub = self.create_publisher(String, "/robot_controls/bag/status", 10)

        if not _HAS_ROSBAG2:
            self.get_logger().error(
                "rosbag2_py not available — install 'ros-humble-rosbag2-py'. Recording disabled."
            )
            return

        self._open_bag()
        self._create_subscriptions()
        self.create_timer(5.0, self._publish_status)
        self.get_logger().info(
            f"BagRecorder: recording to '{self._bag_path}' "
            f"(storage: {self._storage_id}, topics: {len(self._topics)})"
        )

    def _open_bag(self):
        storage_options = rosbag2_py.StorageOptions(
            uri=self._bag_path,
            storage_id=self._storage_id,
        )
        converter_options = rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        )
        self._writer = rosbag2_py.SequentialWriter()
        self._writer.open(storage_options, converter_options)

        for topic, msg_type in ROBOT_TOPICS.items():
            if topic in self._topics:
                topic_meta = rosbag2_py.TopicMetadata(
                    name=topic,
                    type=msg_type,
                    serialization_format="cdr",
                )
                self._writer.create_topic(topic_meta)

        self._recording = True

    def _close_bag(self):
        with self._write_lock:
            self._recording = False
            if self._writer:
                del self._writer
                self._writer = None
        total = sum(self._msg_count.values())
        self.get_logger().info(f"Bag closed: '{self._bag_path}' — {total} messages total")
        for topic, count in self._msg_count.items():
            if count > 0:
                self.get_logger().info(f"  {topic}: {count} messages")

    def _create_subscriptions(self):
        type_map: dict[str, type] = {
            "/joint_states":                    JointState,
            "/robot_controls/joint_states":     JointState,
            "/robot_controls/target_pose":      PoseStamped,
            "/robot_controls/parameters/cmd":   String,
            "/robot_controls/parameters/state": String,
            "/robot_controls/status":           String,
            "/robot_controls/stop":             Empty,
        }
        for topic in self._topics:
            msg_cls = type_map.get(topic)
            if msg_cls is None:
                self.get_logger().warn(f"Unknown topic type for {topic}, skipping")
                continue
            cb = self._make_callback(topic)
            sub = self.create_subscription(msg_cls, topic, cb, 10)
            self._subs.append(sub)

    def _make_callback(self, topic: str):
        def callback(msg) -> None:
            if not self._recording or self._writer is None:
                return
            timestamp_ns = self.get_clock().now().nanoseconds
            serialized = serialize_message(msg)
            with self._write_lock:
                if self._writer and self._recording:
                    self._writer.write(topic, serialized, timestamp_ns)
                    self._msg_count[topic] += 1
        return callback

    def _publish_status(self):
        total = sum(self._msg_count.values())
        status = String()
        per_topic = ", ".join(
            f"{t.split('/')[-1]}:{c}"
            for t, c in self._msg_count.items()
            if c > 0
        )
        status.data = (
            f"recording={self._recording} bag={self._bag_path} "
            f"total={total} [{per_topic}]"
        )
        self._status_pub.publish(status)

    def destroy_node(self):
        if self._recording:
            self._close_bag()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = BagRecorder()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
