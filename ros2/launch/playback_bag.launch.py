#!/usr/bin/env python3
"""
Bag Playback Launch File.

Воспроизводит записанный rosbag2 файл без подключения к реальному железу.
Полезно для отладки, тестирования и визуализации данных.

Usage:
    ros2 launch robot_control playback_bag.launch.py bag_path:=robot_bag_20240101_120000
    ros2 launch robot_control playback_bag.launch.py bag_path:=./bags/session1 rate:=0.5

Arguments:
    bag_path  — путь к директории с bag-файлом (обязательный)
    rate      — скорость воспроизведения (default: 1.0, 0.5 = замедленно)
    loop      — зациклить воспроизведение (default: false)

After launch:
    ros2 topic echo /robot/joint_states   — наблюдать позиции
    ros2 topic echo /robot/status         — наблюдать статус
    rviz2                                 — 3D-визуализация (если настроен)
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    LogInfo,
)
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.conditions import IfCondition


def generate_launch_description():
    # ── Arguments ───────────────────────────────────────────────────────
    bag_path_arg = DeclareLaunchArgument(
        "bag_path",
        description="Path to the rosbag2 directory to play back",
    )
    rate_arg = DeclareLaunchArgument(
        "rate",
        default_value="1.0",
        description="Playback rate multiplier (1.0 = real-time, 0.5 = half speed)",
    )
    loop_arg = DeclareLaunchArgument(
        "loop",
        default_value="false",
        description="Loop playback (true/false)",
    )

    bag_path = LaunchConfiguration("bag_path")
    rate     = LaunchConfiguration("rate")
    loop     = LaunchConfiguration("loop")

    # ── ros2 bag play (normal) ───────────────────────────────────────────
    play_bag = ExecuteProcess(
        cmd=[
            "ros2", "bag", "play",
            bag_path,
            "--rate", rate,
            "--topics",
            "/robot/joint_states",
            "/robot/joint_cmd",
            "/robot/status",
            "/robot/diagnostics",
            "/robot/temperature",
            "/robot/alarms",
        ],
        output="screen",
        condition=IfCondition(
            PythonExpression(["'", loop, "' != 'true'"])
        ),
    )

    # ── ros2 bag play (loop) ─────────────────────────────────────────────
    play_bag_loop = ExecuteProcess(
        cmd=[
            "ros2", "bag", "play",
            bag_path,
            "--rate", rate,
            "--loop",
            "--topics",
            "/robot/joint_states",
            "/robot/joint_cmd",
            "/robot/status",
            "/robot/diagnostics",
            "/robot/temperature",
            "/robot/alarms",
        ],
        output="screen",
        condition=IfCondition(
            PythonExpression(["'", loop, "' == 'true'"])
        ),
    )

    log_info = LogInfo(
        msg=["Playing bag: ", bag_path, "  rate=", rate, "  loop=", loop]
    )

    return LaunchDescription([
        bag_path_arg,
        rate_arg,
        loop_arg,
        log_info,
        play_bag,
        play_bag_loop,
    ])
