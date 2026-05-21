#!/usr/bin/env python3
"""
ros2_control Launch File — ST3215 6-DOF Robot.

Запускает полный стек ros2_control:
  1. robot_state_publisher   — публикует TF из URDF
  2. controller_manager      — загружает hardware + управляет контроллерами
  3. joint_state_broadcaster — читает hardware state → /joint_states
  4. joint_trajectory_controller — принимает JointTrajectory → пишет в hardware
  5. ros2_control_bridge     — мост: hardware state → реальные ST3215 моторы

Схема управления:
  Client
    → /joint_trajectory_controller/follow_joint_trajectory (Action)
    → JointTrajectoryController
    → mock_components/GenericSystem (hardware state)
    → ros2_control_bridge
    → RobotHWInterface → MotorController → ST3215 (UART)

Usage:
    ros2 launch robot_control ros2_control.launch.py
    ros2 launch robot_control ros2_control.launch.py port:=/dev/ttyUSB0
    ros2 launch robot_control ros2_control.launch.py port:=COM3 baudrate:=1000000

После запуска:
    ros2 control list_controllers
    ros2 control list_hardware_interfaces
    ros2 action list
"""

from pathlib import Path

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    RegisterEventHandler,
    TimerAction,
)
from launch.event_handlers import OnProcessStart
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # ── Arguments ───────────────────────────────────────────────────────
    port_arg     = DeclareLaunchArgument("port",     default_value="COM3")
    baudrate_arg = DeclareLaunchArgument("baudrate", default_value="1000000")

    port     = LaunchConfiguration("port")
    baudrate = LaunchConfiguration("baudrate")

    pkg_share = FindPackageShare("robot_control")

    # ── Robot description (xacro → URDF) ────────────────────────────────
    robot_description_content = Command([
        FindExecutable(name="xacro"), " ",
        PathJoinSubstitution([pkg_share, "urdf", "robot.urdf.xacro"]),
    ])
    robot_description = {"robot_description": robot_description_content}

    # ── Controllers config ───────────────────────────────────────────────
    robot_controllers = PathJoinSubstitution([
        pkg_share, "config", "robot_controllers.yaml"
    ])

    # ── 1. robot_state_publisher ─────────────────────────────────────────
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        parameters=[robot_description],
        output="screen",
    )

    # ── 2. controller_manager ────────────────────────────────────────────
    controller_manager = Node(
        package="controller_manager",
        executable="ros2_control_node",
        name="controller_manager",
        parameters=[
            robot_description,
            robot_controllers,
        ],
        output="screen",
    )

    # ── 3. joint_state_broadcaster ───────────────────────────────────────
    # Spawned after controller_manager is ready (1 s delay)
    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager", "/controller_manager",
        ],
        output="screen",
    )

    # ── 4. joint_trajectory_controller ───────────────────────────────────
    # Spawned after joint_state_broadcaster is active
    joint_trajectory_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_trajectory_controller",
            "--controller-manager", "/controller_manager",
        ],
        output="screen",
    )

    # ── 5. ros2_control_bridge ───────────────────────────────────────────
    # Bridge: forwards JTC desired positions to real hardware
    ros2_control_bridge = Node(
        package="robot_control",
        executable="ros2_control_bridge",
        name="ros2_control_bridge",
        parameters=[{
            "port":            port,
            "baudrate":        baudrate,
            "monitor_rate_hz": 50.0,
            "command_timeout": 1.0,
        }],
        output="screen",
    )

    # ── Event: start JSB after controller_manager starts ─────────────────
    start_jsb_after_cm = RegisterEventHandler(
        OnProcessStart(
            target_action=controller_manager,
            on_start=[
                TimerAction(
                    period=1.0,
                    actions=[joint_state_broadcaster_spawner],
                )
            ],
        )
    )

    # ── Event: start JTC after JSB spawner starts ────────────────────────
    start_jtc_after_jsb = RegisterEventHandler(
        OnProcessStart(
            target_action=joint_state_broadcaster_spawner,
            on_start=[
                TimerAction(
                    period=2.0,
                    actions=[joint_trajectory_controller_spawner],
                )
            ],
        )
    )

    return LaunchDescription([
        port_arg,
        baudrate_arg,
        robot_state_publisher,
        controller_manager,
        start_jsb_after_cm,
        start_jtc_after_jsb,
        ros2_control_bridge,
    ])
