import os
from glob import glob

from setuptools import find_packages, setup

package_name = "robot_control"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "urdf"),    glob("urdf/*.xacro") + glob("urdf/*.urdf")),
        (os.path.join("share", package_name, "meshes"), glob("meshes/*.stl") + glob("meshes/*.dae")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Alexandr Lyachov",
    description="ROS2 package for ST3215 robot control",
    license="MIT",
    entry_points={
        "console_scripts": [
            "robot_node           = robot_control.robot_node:main",
            "monitor_node         = robot_control.monitor_node:main",
            "ik_service_node      = robot_control.ik_service_node:main",
            "robot_node_v2        = robot_control.robot_node_v2:main",
            "monitor_node_v2      = robot_control.monitor_node_v2:main",
            "bag_recorder         = robot_control.bag_recorder:main",
            "ros2_control_bridge  = robot_control.ros2_control_bridge:main",
        ],
    },
)
