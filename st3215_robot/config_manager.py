#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Manager for ST3215 Robot
Handles motor limits, kinematics parameters, and 3D visualization settings
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class MotorLimits:
    """Limits for a single motor"""

    min_position: int = 0
    max_position: int = 4095
    min_speed: int = 0
    max_speed: int = 3400
    max_temperature: float = 80.0
    max_load: float = 100.0
    max_current: float = 2000.0  # mA
    enabled: bool = True


@dataclass
class KinematicLink:
    """DH parameters for a kinematic link"""

    link_id: int
    alpha: float = 0.0  # Link twist (radians)
    a: float = 0.0  # Link length (mm)
    d: float = 0.0  # Link offset (mm)
    theta_offset: float = 0.0  # Joint angle offset (radians)
    motor_id: Optional[int] = None


@dataclass
class RobotConfig:
    """Complete robot configuration"""

    robot_name: str = "ST3215 Robot"
    serial_port: str = "COM3"
    baudrate: int = 1000000
    timeout: float = 1.0

    # Motor configurations (key: motor_id, value: MotorLimits)
    motor_limits: Dict[int, MotorLimits] = field(default_factory=dict)

    # Kinematic chain
    kinematic_links: List[KinematicLink] = field(default_factory=list)

    # 3D Visualization settings
    vis_grid_size: float = 800.0
    vis_update_interval: float = 0.1
    vis_show_trail: bool = True
    vis_trail_length: int = 100
    vis_point_size: int = 50
    vis_point_color: str = "red"
    vis_link_width: int = 4

    # Base position in 3D space
    base_x: float = 0.0
    base_y: float = 0.0
    base_z: float = 0.0

    def __post_init__(self):
        """Initialize default values"""
        if not self.motor_limits:
            # Default motor limits for IDs 1-6
            for i in range(1, 7):
                self.motor_limits[i] = MotorLimits()

        if not self.kinematic_links:
            # Default 6-DOF kinematic chain
            self.kinematic_links = [
                KinematicLink(link_id=1, alpha=-1.5708, a=0, d=94.0, motor_id=1),
                KinematicLink(
                    link_id=2, alpha=0, a=0, d=0, theta_offset=-1.5708, motor_id=2
                ),
                KinematicLink(link_id=3, alpha=0, a=265.8, d=0, motor_id=3),
                KinematicLink(link_id=4, alpha=-1.5708, a=222.0, d=51.0, motor_id=4),
                KinematicLink(link_id=5, alpha=1.5708, a=0, d=0, motor_id=5),
                KinematicLink(link_id=6, alpha=-1.5708, a=0, d=0, motor_id=6),
            ]


class ConfigManager:
    """Manages robot configuration with file persistence"""

    def __init__(self, config_file: str = "robot_config.json"):
        self.config_file = config_file
        self.config: Optional[RobotConfig] = None
        self.load()

    def load(self) -> RobotConfig:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Reconstruct RobotConfig
                config_dict = {}

                # Simple fields
                for key in [
                    "robot_name",
                    "serial_port",
                    "baudrate",
                    "timeout",
                    "vis_grid_size",
                    "vis_update_interval",
                    "vis_show_trail",
                    "vis_trail_length",
                    "vis_point_size",
                    "vis_point_color",
                    "vis_link_width",
                    "base_x",
                    "base_y",
                    "base_z",
                ]:
                    if key in data:
                        config_dict[key] = data[key]

                # Motor limits
                motor_limits = {}
                if "motor_limits" in data:
                    for mid, mdata in data["motor_limits"].items():
                        motor_limits[int(mid)] = MotorLimits(**mdata)
                config_dict["motor_limits"] = motor_limits

                # Kinematic links
                kin_links = []
                if "kinematic_links" in data:
                    for kdata in data["kinematic_links"]:
                        kin_links.append(KinematicLink(**kdata))
                config_dict["kinematic_links"] = kin_links

                self.config = RobotConfig(**config_dict)
                print(f"✅ Configuration loaded from {self.config_file}")

            except Exception as e:
                print(f"⚠️ Error loading config: {e}")
                self.config = RobotConfig()
        else:
            print(f"📝 Creating new configuration: {self.config_file}")
            self.config = RobotConfig()
            self.save()

        return self.config

    def save(self) -> bool:
        """Save configuration to file"""
        if not self.config:
            return False

        try:
            # Convert to dict
            data = {
                "robot_name": self.config.robot_name,
                "serial_port": self.config.serial_port,
                "baudrate": self.config.baudrate,
                "timeout": self.config.timeout,
                "vis_grid_size": self.config.vis_grid_size,
                "vis_update_interval": self.config.vis_update_interval,
                "vis_show_trail": self.config.vis_show_trail,
                "vis_trail_length": self.config.vis_trail_length,
                "vis_point_size": self.config.vis_point_size,
                "vis_point_color": self.config.vis_point_color,
                "vis_link_width": self.config.vis_link_width,
                "base_x": self.config.base_x,
                "base_y": self.config.base_y,
                "base_z": self.config.base_z,
            }

            # Motor limits
            data["motor_limits"] = {
                str(mid): asdict(limits)
                for mid, limits in self.config.motor_limits.items()
            }

            # Kinematic links
            data["kinematic_links"] = [
                asdict(link) for link in self.config.kinematic_links
            ]

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"💾 Configuration saved to {self.config_file}")
            return True

        except Exception as e:
            print(f"❌ Error saving config: {e}")
            return False

    def update_motor_limits(self, motor_id: int, limits: MotorLimits):
        """Update motor limits"""
        self.config.motor_limits[motor_id] = limits
        self.save()

    def update_kinematic_link(self, link_id: int, **kwargs):
        """Update kinematic link parameters"""
        for link in self.config.kinematic_links:
            if link.link_id == link_id:
                for key, value in kwargs.items():
                    if hasattr(link, key):
                        setattr(link, key, value)
                self.save()
                return True
        return False

    def get_motor_limits(self, motor_id: int) -> Optional[MotorLimits]:
        """Get motor limits"""
        return self.config.motor_limits.get(motor_id)

    def get_all_motor_limits(self) -> Dict[int, MotorLimits]:
        """Get all motor limits"""
        return self.config.motor_limits

    def get_kinematic_links(self) -> List[KinematicLink]:
        """Get kinematic chain"""
        return self.config.kinematic_links

    def get_visualization_settings(self) -> dict:
        """Get visualization settings"""
        return {
            "grid_size": self.config.vis_grid_size,
            "update_interval": self.config.vis_update_interval,
            "show_trail": self.config.vis_show_trail,
            "trail_length": self.config.vis_trail_length,
            "point_size": self.config.vis_point_size,
            "point_color": self.config.vis_point_color,
            "link_width": self.config.vis_link_width,
            "base_position": (
                self.config.base_x,
                self.config.base_y,
                self.config.base_z,
            ),
        }


# Example usage
if __name__ == "__main__":
    config_mgr = ConfigManager()
    config = config_mgr.load()

    print(f"\nRobot: {config.robot_name}")
    print(f"Motors configured: {len(config.motor_limits)}")
    print(f"Kinematic links: {len(config.kinematic_links)}")

    # Show first motor limits
    if config.motor_limits:
        mid = list(config.motor_limits.keys())[0]
        limits = config.motor_limits[mid]
        print(f"\nMotor {mid} limits:")
        print(f"  Position: {limits.min_position} - {limits.max_position}")
        print(f"  Speed: {limits.min_speed} - {limits.max_speed}")
        print(f"  Max Temp: {limits.max_temperature}°C")
