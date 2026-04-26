#!/usr/bin/env python3
"""
Bag Recording Launch File.

Запускает роботные узлы и параллельно записывает все топики в rosbag2.

Usage:
    ros2 launch robot_control record_bag.launch.py
    ros2 launch robot_control record_bag.launch.py port:=/dev/ttyUSB0
    ros2 launch robot_control record_bag.launch.py bag_path:=session_2024

Arguments:
    port        — serial port (default: COM3)
    baudrate    — serial baudrate (default: 1000000)
    bag_path    — output bag directory (default: auto-generated timestamp name)
    storage_id  — storage format: sqlite3 or mcap (default: sqlite3)

Topics recorded:
    /robot/joint_states, /robot/joint_cmd, /robot/status,
    /robot/stop, /robot/diagnostics, /robot/temperature, /robot/alarms
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # ── Arguments ───────────────────────────────────────────────────────
    port_arg       = DeclareLaunchArgument("port",       default_value="COM3")
    baudrate_arg   = DeclareLaunchArgument("baudrate",   default_value="1000000")
    bag_path_arg   = DeclareLaunchArgument("bag_path",   default_value="")
    storage_id_arg = DeclareLaunchArgument("storage_id", default_value="sqlite3")

    port       = LaunchConfiguration("port")
    baudrate   = LaunchConfiguration("baudrate")
    bag_path   = LaunchConfiguration("bag_path")
    storage_id = LaunchConfiguration("storage_id")

    # ── Robot Node (v2 — shared hardware) ───────────────────────────────
    robot_node = Node(
        package="robot_control",
        executable="robot_node_v2",
        name="robot_node_v2",
        parameters=[{
            "port":             port,
            "baudrate":         baudrate,
            "monitor_rate_hz":  50.0,
        }],
        output="screen",
    )

    # ── Monitor Node ─────────────────────────────────────────────────────
    monitor_node = Node(
        package="robot_control",
        executable="monitor_node_v2",
        name="monitor_node_v2",
        parameters=[{"publish_rate_hz": 1.0}],
        output="screen",
    )

    # ── Bag Recorder Node ────────────────────────────────────────────────
    bag_recorder_node = Node(
        package="robot_control",
        executable="bag_recorder",
        name="bag_recorder",
        parameters=[{
            "bag_path":   bag_path,
            "storage_id": storage_id,
        }],
        output="screen",
    )

    return LaunchDescription([
        port_arg,
        baudrate_arg,
        bag_path_arg,
        storage_id_arg,
        robot_node,
        monitor_node,
        bag_recorder_node,
    ])
