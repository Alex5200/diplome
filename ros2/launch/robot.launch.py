"""
Launch file: starts all three robot_control nodes simultaneously.

Usage:
    ros2 launch robot_control robot.launch.py port:=COM3
    ros2 launch robot_control robot.launch.py port:=/dev/ttyUSB0 baudrate:=1000000
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    port_arg     = DeclareLaunchArgument("port",     default_value="COM3")
    baudrate_arg = DeclareLaunchArgument("baudrate", default_value="1000000")

    port     = LaunchConfiguration("port")
    baudrate = LaunchConfiguration("baudrate")

    robot_node = Node(
        package="robot_control",
        executable="robot_node",
        name="robot_node",
        parameters=[{"port": port, "baudrate": baudrate, "monitor_rate_hz": 10.0}],
        output="screen",
    )

    monitor_node = Node(
        package="robot_control",
        executable="monitor_node",
        name="monitor_node",
        parameters=[{"port": port, "baudrate": baudrate, "publish_rate_hz": 1.0}],
        output="screen",
    )

    ik_service_node = Node(
        package="robot_control",
        executable="ik_service_node",
        name="ik_service_node",
        output="screen",
    )

    return LaunchDescription([
        port_arg,
        baudrate_arg,
        robot_node,
        monitor_node,
        ik_service_node,
    ])
