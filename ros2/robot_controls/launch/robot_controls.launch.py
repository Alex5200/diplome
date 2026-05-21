import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("robot_controls")

    return LaunchDescription([
        DeclareLaunchArgument("port", default_value="COM3", description="Serial port"),
        DeclareLaunchArgument("baudrate", default_value="1000000", description="Serial baudrate"),
        DeclareLaunchArgument("publish_rate", default_value="50.0", description="Publish rate (Hz)"),
        DeclareLaunchArgument("offline", default_value="false", description="Offline mode"),

        Node(
            package="robot_controls",
            executable="robot_controls_node",
            name="robot_controls_node",
            parameters=[{
                "port": LaunchConfiguration("port"),
                "baudrate": LaunchConfiguration("baudrate"),
                "publish_rate_hz": LaunchConfiguration("publish_rate"),
                "offline_mode": LaunchConfiguration("offline"),
            }],
            output="screen",
        ),

        Node(
            package="robot_controls",
            executable="bag_recorder",
            name="bag_recorder",
            output="screen",
        ),
    ])
