from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_rc = FindPackageShare("robot_control")
    pkg_rct = FindPackageShare("robot_controls")

    robot_description = ParameterValue(
        Command([
            FindExecutable(name="xacro"), " ",
            PathJoinSubstitution([pkg_rc, "urdf", "robot.urdf.xacro"]),
        ]),
        value_type=str,
    )

    robot_description_semantic = ParameterValue(
        Command([
            FindExecutable(name="cat"), " ",
            PathJoinSubstitution([pkg_rct, "config", "st3215.srdf"]),
        ]),
        value_type=str,
    )

    kinematics_path = PathJoinSubstitution([pkg_rct, "config", "kinematics.yaml"])
    ompl_path = PathJoinSubstitution([pkg_rct, "config", "ompl_planning.yaml"])

    return LaunchDescription([
        DeclareLaunchArgument("port", default_value="COM3"),
        DeclareLaunchArgument("baudrate", default_value="1000000"),
        DeclareLaunchArgument("use_rviz", default_value="true"),
        DeclareLaunchArgument("use_robot_hardware", default_value="false"),

        # ── 1. robot_state_publisher ──
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            parameters=[{"robot_description": robot_description}],
            output="screen",
        ),

        # ── 2. move_group ──
        Node(
            package="moveit_ros_move_group",
            executable="move_group",
            name="move_group",
            output="screen",
            parameters=[{
                "robot_description": robot_description,
                "robot_description_semantic": robot_description_semantic,
                "robot_description_kinematics": kinematics_path,
                "planning_pipelines": ["ompl"],
                "ompl": {"arm": {"planner_configs": ["RRTConnect", "RRTstar"]}},
                "use_sim_time": False,
                "publish_robot_description_semantic": True,
                "allow_trajectory_execution": True,
                "max_safe_path_cost": 1.0,
                "jiggle_fraction": 0.05,
            }],
        ),

        # ── 3. robot_controls_node ──
        Node(
            package="robot_controls",
            executable="robot_controls_node",
            name="robot_controls_node",
            parameters=[{
                "port": LaunchConfiguration("port"),
                "baudrate": LaunchConfiguration("baudrate"),
                "offline_mode": LaunchConfiguration("use_robot_hardware"),
            }],
            output="screen",
        ),

        # ── 4. moveit_bridge ──
        Node(
            package="robot_controls",
            executable="moveit_bridge",
            name="moveit_bridge",
            output="screen",
        ),

        # ── 5. RViz with MotionPlanning ──
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            condition=IfCondition(LaunchConfiguration("use_rviz")),
            output="screen",
        ),

        # ── 6. bag_recorder ──
        Node(
            package="robot_controls",
            executable="bag_recorder",
            name="bag_recorder",
            output="screen",
        ),
    ])
