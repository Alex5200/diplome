from setuptools import setup

package_name = "servo_driver_pkg"

setup(
    name=package_name,
    version="0.0.0",
    packages=[package_name],
    install_requires=["setuptools"],
    zip_safe=True,
    author="Your Name",
    maintainer="Your Name",
    description="ROS2 Driver for ST3215 Servos",
    entry_points={
        "console_scripts": [
            "servo_driver = servo_driver_pkg.servo_driver_node:main",
        ],
    },
)
