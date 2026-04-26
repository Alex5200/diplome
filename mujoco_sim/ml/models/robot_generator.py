"""
MuJoCo Robot Model Generator for mujoco_sim
Generates MJCF XML from robot_config.json and STL meshes
"""

import json
from pathlib import Path
from typing import Optional

# Project root - go up from mujoco_sim/ml/models/
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent  # diplome root
STL_DIR = ROOT_DIR / "mujoco_sim" / "models"
CONFIG_FILE = ROOT_DIR / "robot_config.json"

# Joint to STL mapping (from robot_config.json + STL files)
JOINT_STL_MAP = {
    0: "основание.stl",  # base
    1: "плечо1.stl",  # shoulder1
    2: "плечо2.stl",  # shoulder2
    3: "локоть.stl",  # elbow
    4: "кисть1.stl",  # wrist1
    5: "кисть2.stl",  # wrist2 (gripper)
}

# Inverted joints (from robot_config.json: joint_0 and joint_2 have inverted: true)
INVERTED_JOINTS = {0, 2}

# Joint axes (standard 6-DOF)
JOINT_AXES = {
    0: "0 0 1",  # base - rotation around Z
    1: "0 1 0",  # shoulder1 - rotation around Y
    2: "0 1 0",  # shoulder2 - rotation around Y
    3: "0 1 0",  # elbow - rotation around Y
    4: "1 0 0",  # wrist1 - rotation around X
    5: "1 0 0",  # wrist2 - rotation around X
}

# Joint limits in radians (from robot_config.json: ~120 degrees range)
DEFAULT_JOINT_LIMITS = (-2.09, 2.09)  # ~120 degrees


class RobotGenerator:
    """Generates MuJoCo MJCF XML from robot configuration and STL meshes."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.robot_config = None
        self.motor_mapping = {}

    def load_config(self) -> dict:
        """Load robot configuration from JSON."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.robot_config = json.load(f)

        # Extract motor mapping
        self.motor_mapping = self.robot_config.get("motor_mapping", {})

        return self.robot_config

    def validate_stl_files(self) -> bool:
        """Validate that all STL files exist."""
        missing = []
        for stl_file in JOINT_STL_MAP.values():
            stl_path = STL_DIR / stl_file
            if not stl_path.exists():
                missing.append(stl_file)

        if missing:
            raise FileNotFoundError(f"Missing STL files: {missing}")

        return True

    def generate_mjcf(self) -> str:
        """
        Generate complete MuJoCo MJCF XML string.

        Returns:
            str: MJCF XML content
        """
        if self.robot_config is None:
            self.load_config()

        self.validate_stl_files()

        # Build XML
        xml_lines = []

        # Header
        xml_lines.append('<?xml version="1.0" encoding="utf-8"?>')
        xml_lines.append('<mujoco model="arm6dof">')

        # Compiler settings
        xml_lines.append('  <compiler angle="radian" autolimits="true"/>')

        # Option (physics)
        xml_lines.append('  <option gravity="0 0 -9.81" timestep="0.002">')
        xml_lines.append('    <flag contact="enable"/>')
        xml_lines.append("  </option>")

        # Default settings
        xml_lines.append("  <default>")
        xml_lines.append('    <joint damping="0.5" armature="0.01"/>')
        xml_lines.append('    <geom condim="3" friction="0.8 0.3 0.01"/>')
        xml_lines.append('    <motor ctrlrange="-2.09 2.09" ctrllimited="true"/>')
        xml_lines.append("  </default>")

        # Assets (textures and materials)
        xml_lines.append("  <asset>")
        xml_lines.append('    <material name="robot_mat" rgba="0.2 0.4 0.8 1"/>')
        xml_lines.append('    <material name="floor_mat" rgba="0.3 0.3 0.35 1"/>')
        xml_lines.append("  </asset>")

        # Worldbody
        xml_lines.append("  <worldbody>")

        # Floor
        xml_lines.append(
            '    <geom name="floor" type="plane" size="1 1 0.01" material="floor_mat" pos="0 0 0"/>'
        )

        # Lights
        xml_lines.append('    <light name="sun" pos="0 0 3" dir="0 0 -1" diffuse="0.8 0.8 0.8"/>')
        xml_lines.append(
            '    <light name="fill" pos="2 2 2" dir="-0.5 -0.5 -0.5" diffuse="0.3 0.3 0.3"/>'
        )

        # Cameras
        xml_lines.append('    <camera name="top_down" pos="0 0 1.5" fovy="60" mode="fixed"/>')
        xml_lines.append(
            '    <camera name="egocentric" pos="0.3 0 0.3" xyaxes="0 -1 0 0 0 1" fovy="60"/>'
        )
        xml_lines.append('    <camera name="agentview" pos="0.5 0.5 0.8" fovy="60"/>')

        # Robot kinematic chain
        xml_lines.extend(self._build_robot_chain())

        # End of worldbody
        xml_lines.append("  </worldbody>")

        # Actuators
        xml_lines.append("  <actuator>")
        for joint_idx in range(6):
            joint_name = f"joint_{joint_idx}"
            xml_lines.append(
                f'    <position name="act_{joint_name}" joint="{joint_name}" kp="100" kv="10"/>'
            )
        xml_lines.append("  </actuator>")

        # Sensors
        xml_lines.append("  <sensor>")
        for joint_idx in range(6):
            joint_name = f"joint_{joint_idx}"
            xml_lines.append(f'    <jointpos name="sens_{joint_name}" joint="{joint_name}"/>')
        xml_lines.append("  </sensor>")

        # End of model
        xml_lines.append("</mujoco>")

        return "\n".join(xml_lines)

    def _build_robot_chain(self) -> list:
        """Build the robot kinematic chain as XML lines."""
        lines = []

        # Base (fixed to world)
        lines.append('    <body name="base" pos="0 0 0.1">')
        lines.append(
            '      <geom name="base_geom" type="cylinder" size="0.05 0.02" material="robot_mat" mass="0.5"/>'
        )

        # Joint 0: Base rotation (Z axis) - INVERTED
        lines.append(self._create_joint_body(0, "0 0 0.02", "0 0 1", True))

        # Joint 1: Shoulder 1 (Y axis)
        lines.append(self._create_joint_body(1, "0.2 0 0", "0 1 0", False))

        # Joint 2: Shoulder 2 (Y axis) - INVERTED
        lines.append(self._create_joint_body(2, "0.15 0 0", "0 1 0", True))

        # Joint 3: Elbow (Y axis)
        lines.append(self._create_joint_body(3, "0.1 0 0", "0 1 0", False))

        # Joint 4: Wrist 1 (X axis)
        lines.append(self._create_joint_body(4, "0.08 0 0", "1 0 0", False))

        # Joint 5: Wrist 2 / Gripper (X axis)
        lines.append(self._create_joint_body(5, "0.05 0 0", "1 0 0", False, is_gripper=True))

        # Close base body
        lines.append("    </body>")

        return lines

    def _create_joint_body(
        self, joint_idx: int, pos: str, axis: str, inverted: bool, is_gripper: bool = False
    ) -> str:
        """Create a joint+body XML element."""
        joint_name = f"joint_{joint_idx}"
        body_name = f"link_{joint_idx}"

        # Get STL mesh name
        stl_mesh = JOINT_STL_MAP[joint_idx].replace(".stl", "")

        # Create joint element
        lines = []
        lines.append(f'      <body name="{body_name}" pos="{pos}">')
        lines.append(
            f'        <joint name="{joint_name}" type="hinge" axis="{axis}" range="-2.09 2.09" damping="{1.0 - joint_idx * 0.1}"/>'
        )

        if is_gripper:
            # Gripper geometry
            lines.append(
                f'        <geom name="gripper_geom" type="box" size="0.02 0.01 0.02" material="robot_mat" mass="0.1"/>'
            )
            lines.append(f'        <site name="ee_site" pos="0 0 0.03" size="0.005"/>')
        else:
            # Link geometry (using capsule for now, can be swapped to STL mesh)
            lines.append(
                f'        <geom name="{joint_name}_geom" type="capsule" size="0.015" fromto="0 0 0 0.1 0 0" material="robot_mat" mass="{0.3 - joint_idx * 0.02}"/>'
            )

        lines.append("      </body>")

        return "\n".join(lines)

    def save(self, output_path: Optional[Path] = None) -> str:
        """Save generated MJCF to file."""
        if output_path is None:
            output_path = STL_DIR.parent / "robot_6dof.xml"

        xml_content = self.generate_mjcf()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        return str(output_path)


def generate_robot_mjcf() -> str:
    """
    Convenience function to generate robot MJCF.

    Returns:
        str: MJCF XML string
    """
    generator = RobotGenerator()
    return generator.generate_mjcf()


if __name__ == "__main__":
    # Test generation
    gen = RobotGenerator()
    xml = gen.generate_mjcf()

    # Save to file
    output = STL_DIR.parent / "robot_6dof.xml"
    with open(output, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"✓ Generated: {output}")
    print(f"  Joints: 6")
    print(f"  STL files: {len(JOINT_STL_MAP)}")
    print(f"  Inverted: {INVERTED_JOINTS}")
