#!/usr/bin/env python3
"""
Launch file for robot_control_v2.

Starts robot_node_v2 and monitor_node_v2 with shared hardware interface.

Usage:
    ros2 launch robot_control robot_v2.launch.py port:=COM3
    ros2 launch robot_control robot_v2.launch.py port:=/dev/ttyUSB0 baudrate:=1000000
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Launch arguments
    port_arg = DeclareLaunchArgument("port", default_value="COM3")
    baudrate_arg = DeclareLaunchArgument("baudrate", default_value="1000000")

    port = LaunchConfiguration("port")
    baudrate = LaunchConfiguration("baudrate")

    # Robot node (initializes hardware)
    robot_node = Node(
        package="robot_control",
        executable="robot_node_v2",
        name="robot_node_v2",
        parameters=[{"port": port, "baudrate": baudrate, "monitor_rate_hz": 50.0}],
        output="screen",
    )

    # Monitor node (uses shared hardware)
    monitor_node = Node(
        package="robot_control",
        executable="monitor_node_v2",
        name="monitor_node_v2",
        parameters=[{"publish_rate_hz": 1.0}],
        output="screen",
    )

    return LaunchDescription(
        [
            port_arg,
            baudrate_arg,
            robot_node,
            monitor_node,
        ]
    )
