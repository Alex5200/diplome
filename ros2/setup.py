from setuptools import setup, find_packages
import os
from glob import glob

package_name = "robot_control"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Alexandr Lyachov",
    description="ROS2 package for ST3215 robot control",
    license="MIT",
    entry_points={
        "console_scripts": [
            "robot_node      = robot_control.robot_node:main",
            "monitor_node    = robot_control.monitor_node:main",
            "ik_service_node = robot_control.ik_service_node:main",
        ],
    },
)
