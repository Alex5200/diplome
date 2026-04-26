#!/usr/bin/env python3
"""
ROS2 Bag Recorder Node.

Records all robot topics to a rosbag2 file using the rosbag2_py API.
Supports recording, status query, and clean shutdown.

Topics recorded by default:
    /robot/joint_states     — sensor_msgs/JointState
    /robot/joint_cmd        — trajectory_msgs/JointTrajectoryPoint
    /robot/status           — std_msgs/String
    /robot/stop             — std_msgs/Empty
    /robot/diagnostics      — std_msgs/String
    /robot/temperature      — std_msgs/String
    /robot/alarms           — std_msgs/String

Parameters:
    bag_path        (str)   — output directory (default: "robot_bag_<timestamp>")
    storage_id      (str)   — storage format: "sqlite3" or "mcap" (default: "sqlite3")
    topics          (list)  — list of topics to record (default: all robot topics)

Usage:
    ros2 run robot_control bag_recorder
    ros2 run robot_control bag_recorder --ros-args -p bag_path:=my_session
"""

from __future__ import annotations

import sys
import os
import time
import threading
from datetime import datetime

import rclpy
from rclpy.node import Node
from rclpy.serialization import serialize_message

from std_msgs.msg import String, Empty
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint

try:
    import rosbag2_py
    _HAS_ROSBAG2 = True
except ImportError:
    _HAS_ROSBAG2 = False


# Default topics to record with their message types
DEFAULT_TOPICS: dict[str, str] = {
    "/robot/joint_states": "sensor_msgs/msg/JointState",
    "/robot/joint_cmd":    "trajectory_msgs/msg/JointTrajectoryPoint",
    "/robot/status":       "std_msgs/msg/String",
    "/robot/stop":         "std_msgs/msg/Empty",
    "/robot/diagnostics":  "std_msgs/msg/String",
    "/robot/temperature":  "std_msgs/msg/String",
    "/robot/alarms":       "std_msgs/msg/String",
}


class BagRecorder(Node):
    """
    Records robot topics to a rosbag2 file.

    Subscribes to all robot topics and writes incoming messages to disk.
    Publishes recording status on /bag_recorder/status.
    """

    def __init__(self) -> None:
        super().__init__("bag_recorder")

        # ── Parameters ──────────────────────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.declare_parameter("bag_path",  f"robot_bag_{timestamp}")
        self.declare_parameter("storage_id", "sqlite3")
        self.declare_parameter("topics",    list(DEFAULT_TOPICS.keys()))

        self._bag_path   = self.get_parameter("bag_path").value
        self._storage_id = self.get_parameter("storage_id").value
        self._topics     = self.get_parameter("topics").value

        # ── State ────────────────────────────────────────────────────────
        self._writer: rosbag2_py.SequentialWriter | None = None
        self._write_lock = threading.Lock()
        self._msg_count: dict[str, int] = {t: 0 for t in self._topics}
        self._recording = False

        # ── Status publisher ─────────────────────────────────────────────
        self._status_pub = self.create_publisher(String, "/bag_recorder/status", 10)

        if not _HAS_ROSBAG2:
            self.get_logger().error(
                "rosbag2_py not available — install 'ros-humble-rosbag2-py'. "
                "Recording disabled."
            )
            return

        self._open_bag()
        self._create_subscriptions()

        # Status timer: publish recording stats every 5 s
        self.create_timer(5.0, self._publish_status)
        self.get_logger().info(
            f"BagRecorder started → '{self._bag_path}' "
            f"(storage: {self._storage_id}, topics: {len(self._topics)})"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Bag lifecycle
    # ──────────────────────────────────────────────────────────────────────

    def _open_bag(self) -> None:
        """Open rosbag2 writer and register all topics."""
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

        # Register topic schemas
        for topic, msg_type in DEFAULT_TOPICS.items():
            if topic in self._topics:
                topic_meta = rosbag2_py.TopicMetadata(
                    name=topic,
                    type=msg_type,
                    serialization_format="cdr",
                )
                self._writer.create_topic(topic_meta)

        self._recording = True

    def _close_bag(self) -> None:
        """Flush and close the bag file."""
        with self._write_lock:
            self._recording = False
            if self._writer:
                del self._writer
                self._writer = None

        total = sum(self._msg_count.values())
        self.get_logger().info(
            f"Bag closed: '{self._bag_path}' — {total} messages total"
        )
        for topic, count in self._msg_count.items():
            if count > 0:
                self.get_logger().info(f"  {topic}: {count} messages")

    # ──────────────────────────────────────────────────────────────────────
    # Subscriptions
    # ──────────────────────────────────────────────────────────────────────

    def _create_subscriptions(self) -> None:
        """Create subscriptions for all configured topics."""
        type_map: dict[str, type] = {
            "/robot/joint_states": JointState,
            "/robot/joint_cmd":    JointTrajectoryPoint,
            "/robot/status":       String,
            "/robot/stop":         Empty,
            "/robot/diagnostics":  String,
            "/robot/temperature":  String,
            "/robot/alarms":       String,
        }
        self._subs = []
        for topic in self._topics:
            msg_cls = type_map.get(topic)
            if msg_cls is None:
                self.get_logger().warn(f"Unknown topic type for {topic}, skipping")
                continue
            cb = self._make_callback(topic)
            sub = self.create_subscription(msg_cls, topic, cb, 10)
            self._subs.append(sub)
            self.get_logger().debug(f"  Subscribed to {topic}")

    def _make_callback(self, topic: str):
        """Factory: returns a callback that writes messages for a given topic."""
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

    # ──────────────────────────────────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────────────────────────────────

    def _publish_status(self) -> None:
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

    # ──────────────────────────────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────────────────────────────

    def destroy_node(self) -> None:
        if self._recording:
            self._close_bag()
        super().destroy_node()


def main(args=None) -> None:
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
