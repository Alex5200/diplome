import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'robot_controls'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml') + glob('config/*.srdf') + glob('config/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='alex',
    maintainer_email='alex@example.com',
    description='ROS2 package for ST3215 6-axis robot control',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'robot_controls_node = robot_controls.robot_controls_node:main',
            'bag_recorder        = robot_controls.bag_recorder:main',
            'moveit_bridge       = robot_controls.moveit_bridge:main',
            'teleop_node         = robot_controls.teleop_node:main',
        ],
    },
)
