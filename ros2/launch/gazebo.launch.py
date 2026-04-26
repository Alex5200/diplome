#!/usr/bin/env python3
"""
Gazebo Classic simulation launch — ST3215 6-DOF Robot.

Запускает:
  1. Gazebo (пустой мир)
  2. robot_state_publisher — TF из URDF
  3. spawn_entity — спаунит робота в Gazebo
  4. joint_state_broadcaster — hardware state → /joint_states
  5. joint_trajectory_controller — принимает JointTrajectory команды

Управление ros2_control осуществляется через gazebo_ros2_control plugin
(не mock_components). controller_manager запускается внутри Gazebo.

Требования:
  sudo apt install ros-humble-gazebo-ros-pkgs \\
                   ros-humble-gazebo-ros2-control

Usage:
  ros2 launch robot_control gazebo.launch.py
  ros2 launch robot_control gazebo.launch.py use_meshes:=true
  ros2 launch robot_control gazebo.launch.py world:=/path/to/my.world

После запуска:
  ros2 control list_controllers
  ros2 control list_hardware_interfaces
  ros2 action list
  ros2 topic echo /joint_states
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # ── Arguments ─────────────────────────────────────────────────────────
    world_arg = DeclareLaunchArgument(
        "world",
        default_value="",
        description="Path to a custom Gazebo world file. Empty = default empty world.",
    )
    use_meshes_arg = DeclareLaunchArgument(
        "use_meshes",
        default_value="false",
        description="Use STL mesh visuals (true) or cylinder primitives (false). "
                    "Set true after placing real STL files in meshes/.",
    )
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="true",
        description="Use Gazebo simulation clock.",
    )

    world       = LaunchConfiguration("world")
    use_meshes  = LaunchConfiguration("use_meshes")
    use_sim_time = LaunchConfiguration("use_sim_time")

    pkg_share = FindPackageShare("robot_control")

    # ── Controllers config path ────────────────────────────────────────────
    robot_controllers = PathJoinSubstitution([
        pkg_share, "config", "robot_controllers.yaml"
    ])

    # ── Robot description: xacro → URDF string ────────────────────────────
    # robot_controllers path is injected into xacro so the Gazebo plugin
    # can find the yaml at runtime.
    robot_description_content = Command([
        FindExecutable(name="xacro"), " ",
        PathJoinSubstitution([pkg_share, "urdf", "robot_gazebo.urdf.xacro"]),
        " use_meshes:=",      use_meshes,
        " robot_controllers:=", robot_controllers,
    ])
    robot_description = {"robot_description": robot_description_content}

    # ── 1. robot_state_publisher ───────────────────────────────────────────
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        parameters=[
            robot_description,
            {"use_sim_time": use_sim_time},
        ],
        output="screen",
    )

    # ── 2. Gazebo (Classic) ────────────────────────────────────────────────
    # Includes the standard gazebo_ros launch which sets up ROS2↔Gazebo bridge.
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare("gazebo_ros"),
                "launch",
                "gazebo.launch.py",
            ])
        ]),
        launch_arguments={
            "world":   world,
            "verbose": "false",
            "pause":   "false",
        }.items(),
    )

    # ── 3. spawn_entity: загрузить URDF в Gazebo ─────────────────────────
    spawn_entity = Node(
        package="gazebo_ros",
        executable="spawn_entity.py",
        name="spawn_robot",
        arguments=[
            "-topic",  "robot_description",
            "-entity", "st3215_robot",
            "-x", "0.0",
            "-y", "0.0",
            "-z", "0.05",
            "-R", "0.0",
            "-P", "0.0",
            "-Y", "0.0",
        ],
        output="screen",
    )

    # ── 4. joint_state_broadcaster ────────────────────────────────────────
    # Ждёт пока spawn_entity завершится, потом стартует через 1 сек.
    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        name="joint_state_broadcaster_spawner",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager", "/controller_manager",
        ],
        parameters=[{"use_sim_time": use_sim_time}],
        output="screen",
    )

    # ── 5. joint_trajectory_controller ───────────────────────────────────
    # Стартует после того, как joint_state_broadcaster активен.
    joint_trajectory_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        name="joint_trajectory_controller_spawner",
        arguments=[
            "joint_trajectory_controller",
            "--controller-manager", "/controller_manager",
        ],
        parameters=[{"use_sim_time": use_sim_time}],
        output="screen",
    )

    # ── Последовательность запуска ─────────────────────────────────────────
    # spawn → wait 1s → JSB spawner → JSB exits → JTC spawner

    start_jsb_after_spawn = RegisterEventHandler(
        OnProcessExit(
            target_action=spawn_entity,
            on_exit=[
                TimerAction(
                    period=1.5,
                    actions=[joint_state_broadcaster_spawner],
                )
            ],
        )
    )

    start_jtc_after_jsb = RegisterEventHandler(
        OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[
                TimerAction(
                    period=1.0,
                    actions=[joint_trajectory_controller_spawner],
                )
            ],
        )
    )

    return LaunchDescription([
        # Arguments
        world_arg,
        use_meshes_arg,
        use_sim_time_arg,

        # Nodes
        robot_state_publisher,
        gazebo,
        spawn_entity,

        # Controller chain
        start_jsb_after_spawn,
        start_jtc_after_jsb,
    ])
