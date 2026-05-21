from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("port", default_value="/dev/ttyACM0"),
        DeclareLaunchArgument("baudrate", default_value="1000000"),
        DeclareLaunchArgument("offline", default_value="true"),

        Node(
            package="robot_controls",
            executable="robot_controls_node",
            name="robot_controls_node",
            parameters=[{
                "port": LaunchConfiguration("port"),
                "baudrate": LaunchConfiguration("baudrate"),
                "offline_mode": LaunchConfiguration("offline"),
            }],
            output="screen",
        ),
        Node(
            package="robot_controls",
            executable="teleop_node",
            name="teleop_node",
            output="screen",
        ),
    ])
