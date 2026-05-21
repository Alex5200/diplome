from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_description = ParameterValue(
        Command([
            FindExecutable(name="xacro"), " ",
            PathJoinSubstitution([
                FindPackageShare("robot_control"), "urdf", "robot.urdf.xacro"
            ]),
        ]),
        value_type=str,
    )

    return LaunchDescription([
        DeclareLaunchArgument("port", default_value="/dev/ttyACM0"),
        DeclareLaunchArgument("baudrate", default_value="1000000"),
        DeclareLaunchArgument("offline", default_value="true"),

        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            parameters=[{"robot_description": robot_description}],
            output="screen",
        ),
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
            executable="rviz_bridge",
            name="rviz_bridge",
            output="screen",
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            arguments=["-d", PathJoinSubstitution([
                FindPackageShare("robot_controls"), "config", "moveit.rviz"
            ])],
            output="screen",
        ),
    ])
