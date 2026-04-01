#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick Kinematics Visualization
Simple and fast 3D plot
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from config_manager import ConfigManager
from kinematics_3d import ForwardKinematics3D


def quick_visualize(joint_angles_degrees):
    """
    Quick visualization of robot pose

    Args:
        joint_angles_degrees: list of 6 joint angles in degrees
    """
    # Load config
    config_mgr = ConfigManager()
    config_mgr.load()

    # Create kinematics
    kin = ForwardKinematics3D(config_mgr)

    # Convert to radians
    joint_angles = np.radians(joint_angles_degrees)

    # Compute forward kinematics
    positions = kin.get_all_positions(joint_angles)
    ee_pos = positions[-1]

    # Create 3D plot
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    # Draw robot
    ax.plot(
        positions[:, 0],
        positions[:, 1],
        positions[:, 2],
        "o-",
        linewidth=3,
        markersize=10,
        color="#2ca02c",
    )

    # Highlight end-effector
    ax.scatter(
        [ee_pos[0]],
        [ee_pos[1]],
        [ee_pos[2]],
        c="red",
        s=200,
        marker="*",
        label="End Effector",
    )

    # Labels
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z (mm)")
    ax.set_title(f"Robot Pose\nJoints: {joint_angles_degrees}°")

    # Grid
    grid_size = config_mgr.config.vis_grid_size / 2
    ax.set_xlim([-grid_size, grid_size])
    ax.set_ylim([-grid_size, grid_size])
    ax.set_zlim([0, grid_size])
    ax.grid(True)

    # Info text
    info = (
        f"Position:\n"
        f"X: {ee_pos[0]:.1f}\n"
        f"Y: {ee_pos[1]:.1f}\n"
        f"Z: {ee_pos[2]:.1f}\n"
        f"Dist: {np.linalg.norm(ee_pos):.1f}"
    )

    ax.text2D(
        0.02,
        0.98,
        info,
        transform=ax.transAxes,
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    plt.legend()
    plt.tight_layout()
    plt.show()

    # Print info
    print("=" * 50)
    print(f"Joint Angles: {joint_angles_degrees}°")
    print(f"End-Effector Position:")
    print(f"  X: {ee_pos[0]:.2f} mm")
    print(f"  Y: {ee_pos[1]:.2f} mm")
    print(f"  Z: {ee_pos[2]:.2f} mm")
    print(f"  Distance from base: {np.linalg.norm(ee_pos):.2f} mm")
    print("=" * 50)


if __name__ == "__main__":
    # Example usage
    print("Quick Kinematics Visualization")
    print("=" * 50)

    # Option 1: Default pose
    print("\n1. Home position (all zeros)")
    print("2. Extended position")
    print("3. Custom position")

    choice = input("\nChoose (1-3): ").strip()

    if choice == "1":
        joints = [0, 0, 0, 0, 0, 0]
    elif choice == "2":
        joints = [0, -45, 90, 0, -45, 0]
    elif choice == "3":
        joints = []
        for i in range(6):
            val = float(input(f"  Joint {i + 1} (deg): "))
            joints.append(val)
    else:
        print("Invalid choice!")
        exit(1)

    quick_visualize(joints)
