#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3D Kinematics and Visualization for ST3215 Robot
Using matplotlib for 3D scatter and line plots
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.animation as animation
from typing import List, Tuple, Optional
from dataclasses import dataclass
from config_manager import ConfigManager, KinematicLink


@dataclass
class JointState:
    """State of a single joint"""

    joint_id: int
    angle: float  # radians
    position: Tuple[float, float, float]  # x, y, z in mm
    transform_matrix: np.ndarray


class ForwardKinematics3D:
    """Forward kinematics using DH parameters"""

    def __init__(self, config_manager: ConfigManager):
        self.config_mgr = config_manager
        self.links = config_manager.get_kinematic_links()

    def dh_transform(
        self, alpha: float, a: float, d: float, theta: float
    ) -> np.ndarray:
        """
        Denavit-Hartenberg transformation matrix

        Args:
            alpha: link twist
            a: link length
            d: link offset
            theta: joint angle

        Returns:
            4x4 homogeneous transformation matrix
        """
        ct = np.cos(theta)
        st = np.sin(theta)
        ca = np.cos(alpha)
        sa = np.sin(alpha)

        return np.array(
            [
                [ct, -st * ca, st * sa, a * ct],
                [st, ct * ca, -ct * sa, a * st],
                [0, sa, ca, d],
                [0, 0, 0, 1],
            ]
        )

    def compute(self, joint_angles: np.ndarray) -> Tuple[np.ndarray, List[JointState]]:
        """
        Compute forward kinematics

        Args:
            joint_angles: array of joint angles in radians

        Returns:
            end_effector_pose: 4x4 transformation matrix
            joint_states: list of joint states with positions
        """
        T = np.eye(4)
        joint_states = []

        # Apply base transformation
        base_x, base_y, base_z = (
            self.config_mgr.config.base_x,
            self.config_mgr.config.base_y,
            self.config_mgr.config.base_z,
        )

        T_base = np.eye(4)
        T_base[0, 3] = base_x
        T_base[1, 3] = base_y
        T_base[2, 3] = base_z
        T = T @ T_base

        for i, link in enumerate(self.links):
            if i >= len(joint_angles):
                break

            theta = joint_angles[i] + link.theta_offset

            Ti = self.dh_transform(link.alpha, link.a, link.d, theta)

            T = T @ Ti

            # Extract position
            pos = T[0:3, 3]

            joint_states.append(
                JointState(
                    joint_id=link.link_id,
                    angle=joint_angles[i],
                    position=(pos[0], pos[1], pos[2]),
                    transform_matrix=T.copy(),
                )
            )

        return T, joint_states

    def get_end_effector_position(self, joint_angles: np.ndarray) -> np.ndarray:
        """Get end-effector position"""
        T, _ = self.compute(joint_angles)
        return T[0:3, 3]

    def get_all_positions(self, joint_angles: np.ndarray) -> np.ndarray:
        """Get positions of all joints including base and end-effector"""
        _, joint_states = self.compute(joint_angles)

        positions = []
        # Base
        positions.append(
            [
                self.config_mgr.config.base_x,
                self.config_mgr.config.base_y,
                self.config_mgr.config.base_z,
            ]
        )

        # Joints
        for state in joint_states:
            positions.append(list(state.position))

        return np.array(positions)


class RobotVisualizer3D:
    """3D visualization using matplotlib"""

    def __init__(self, config_manager: ConfigManager):
        self.config_mgr = config_manager
        self.kinematics = ForwardKinematics3D(config_manager)

        self.fig = None
        self.ax = None
        self.scatter_joint = None
        self.scatter_ee = None
        self.line_links = None
        self.trail_points = None
        self.trail_line = None

        self.trail_history = []
        self.max_trail_length = config_manager.config.vis_trail_length

        # Colors
        self.colors = {
            "base": "#1f77b4",  # blue
            "joint": "#ff7f0e",  # orange
            "end_effector": "#d62728",  # red
            "link": "#2ca02c",  # green
            "trail": "#9467bd",  # purple
            "grid": "#cccccc",
        }

    def create_figure(self, figsize: Tuple[int, int] = (10, 8)):
        """Create 3D figure"""
        self.fig = plt.figure(figsize=figsize)
        self.ax = self.fig.add_subplot(111, projection="3d")

        # Labels
        self.ax.set_xlabel("X (mm)", fontsize=11, fontweight="bold")
        self.ax.set_ylabel("Y (mm)", fontsize=11, fontweight="bold")
        self.ax.set_zlabel("Z (mm)", fontsize=11, fontweight="bold")

        # Title
        self.ax.set_title(
            f"{self.config_mgr.config.robot_name} - 3D Visualization",
            fontsize=13,
            fontweight="bold",
            pad=20,
        )

        # View angle
        self.ax.view_init(elev=30, azim=45)

        # Grid settings
        grid_size = self.config_mgr.config.vis_grid_size / 2
        self.ax.set_xlim([-grid_size, grid_size])
        self.ax.set_ylim([-grid_size, grid_size])
        self.ax.set_zlim([0, grid_size])

        # Grid appearance
        self.ax.grid(True, linestyle="--", alpha=0.6, color=self.colors["grid"])
        self.ax.set_axisbelow(True)

        # Background
        self.ax.set_facecolor("#f8f8f8")
        self.fig.patch.set_facecolor("white")

        return self.fig, self.ax

    def update_visualization(self, joint_angles: np.ndarray, update_trail: bool = True):
        """
        Update 3D visualization with new joint angles

        Args:
            joint_angles: array of joint angles in radians
            update_trail: whether to update trail history
        """
        if self.ax is None:
            self.create_figure()

        # Get positions
        positions = self.kinematics.get_all_positions(joint_angles)
        ee_pos = positions[-1]

        # Clear previous elements
        self.ax.clear()

        # Re-setup axes
        self._setup_axes()

        # Draw grid floor
        self._draw_grid_floor()

        # Draw base
        self._draw_base(positions[0])

        # Draw links
        self._draw_links(positions)

        # Draw joints as scatter points
        self._draw_joints(positions[1:-1])  # Exclude base and EE

        # Draw end-effector
        self._draw_end_effector(ee_pos)

        # Update trail
        if update_trail and self.config_mgr.config.vis_show_trail:
            self._update_trail(ee_pos)

        # Draw trail
        if self.config_mgr.config.vis_show_trail and self.trail_history:
            self._draw_trail()

        # Add info text
        self._add_info_text(ee_pos, joint_angles)

        # Redraw
        self.fig.canvas.draw_idle()

    def _setup_axes(self):
        """Setup axes with same settings"""
        self.ax.set_xlabel("X (mm)", fontsize=11, fontweight="bold")
        self.ax.set_ylabel("Y (mm)", fontsize=11, fontweight="bold")
        self.ax.set_zlabel("Z (mm)", fontsize=11, fontweight="bold")

        self.ax.set_title(
            f"{self.config_mgr.config.robot_name} - 3D Visualization",
            fontsize=13,
            fontweight="bold",
            pad=20,
        )

        self.ax.view_init(elev=30, azim=45)

        grid_size = self.config_mgr.config.vis_grid_size / 2
        self.ax.set_xlim([-grid_size, grid_size])
        self.ax.set_ylim([-grid_size, grid_size])
        self.ax.set_zlim([0, grid_size])

        self.ax.grid(True, linestyle="--", alpha=0.6, color=self.colors["grid"])

    def _draw_grid_floor(self):
        """Draw grid on the floor (z=0)"""
        grid_size = self.config_mgr.config.vis_grid_size / 2
        z_floor = 0

        # Grid lines X
        for x in np.linspace(-grid_size, grid_size, 9):
            self.ax.plot(
                [x, x],
                [-grid_size, grid_size],
                [z_floor, z_floor],
                "k-",
                alpha=0.1,
                linewidth=0.5,
            )

        # Grid lines Y
        for y in np.linspace(-grid_size, grid_size, 9):
            self.ax.plot(
                [-grid_size, grid_size],
                [y, y],
                [z_floor, z_floor],
                "k-",
                alpha=0.1,
                linewidth=0.5,
            )

    def _draw_base(self, base_pos):
        """Draw robot base"""
        x, y, z = base_pos

        # Base as a scatter point
        self.ax.scatter(
            [x],
            [y],
            [z],
            c=self.colors["base"],
            s=200,
            marker="s",
            label="Base",
            alpha=0.8,
            depthshade=True,
        )

        # Base label
        self.ax.text(
            x, y, z - 20, "Base", ha="center", va="top", fontsize=9, fontweight="bold"
        )

    def _draw_links(self, positions: np.ndarray):
        """Draw links between joints"""
        link_width = self.config_mgr.config.vis_link_width

        for i in range(len(positions) - 1):
            self.ax.plot(
                [positions[i, 0], positions[i + 1, 0]],
                [positions[i, 1], positions[i + 1, 1]],
                [positions[i, 2], positions[i + 1, 2]],
                color=self.colors["link"],
                linewidth=link_width,
                alpha=0.8,
                solid_capstyle="round",
            )

    def _draw_joints(self, joint_positions: np.ndarray):
        """Draw joints as scatter points"""
        point_size = self.config_mgr.config.vis_point_size

        if len(joint_positions) > 0:
            self.ax.scatter(
                joint_positions[:, 0],
                joint_positions[:, 1],
                joint_positions[:, 2],
                c=self.colors["joint"],
                s=point_size,
                marker="o",
                label="Joints",
                alpha=0.9,
                depthshade=True,
                edgecolors="black",
                linewidths=0.5,
            )

    def _draw_end_effector(self, ee_pos: np.ndarray):
        """Draw end-effector"""
        point_size = self.config_mgr.config.vis_point_size * 2
        point_color = self.config_mgr.config.vis_point_color

        self.ax.scatter(
            [ee_pos[0]],
            [ee_pos[1]],
            [ee_pos[2]],
            c=point_color,
            s=point_size,
            marker="*",
            label="End Effector",
            alpha=1.0,
            depthshade=True,
            edgecolors="darkred",
            linewidths=1.5,
        )

        # Position label
        self.ax.text(
            ee_pos[0],
            ee_pos[1],
            ee_pos[2] + 20,
            f"EE\n({ee_pos[0]:.0f}, {ee_pos[1]:.0f}, {ee_pos[2]:.0f})",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            color="darkred",
        )

    def _update_trail(self, ee_pos: np.ndarray):
        """Update trail history"""
        self.trail_history.append(ee_pos.copy())

        # Limit trail length
        max_len = self.config_mgr.config.vis_trail_length
        if len(self.trail_history) > max_len:
            self.trail_history.pop(0)

    def _draw_trail(self):
        """Draw end-effector trail"""
        if len(self.trail_history) < 2:
            return

        trail_array = np.array(self.trail_history)

        # Draw trail line
        self.ax.plot(
            trail_array[:, 0],
            trail_array[:, 1],
            trail_array[:, 2],
            color=self.colors["trail"],
            linewidth=2,
            alpha=0.6,
            linestyle="-",
        )

        # Draw trail points
        if len(trail_array) > 1:
            self.ax.scatter(
                trail_array[:: max(1, len(trail_array) // 10), 0],
                trail_array[:: max(1, len(trail_array) // 10), 1],
                trail_array[:: max(1, len(trail_array) // 10), 2],
                c=self.colors["trail"],
                s=20,
                alpha=0.4,
                marker=".",
            )

    def _add_info_text(self, ee_pos: np.ndarray, joint_angles: np.ndarray):
        """Add information text to the plot"""
        # Position info
        info_text = (
            f"Position:\n"
            f"X: {ee_pos[0]:.1f} mm\n"
            f"Y: {ee_pos[1]:.1f} mm\n"
            f"Z: {ee_pos[2]:.1f} mm\n\n"
            f"Distance from base:\n"
            f"{np.linalg.norm(ee_pos):.1f} mm"
        )

        self.ax.text2D(
            0.02,
            0.98,
            info_text,
            transform=self.ax.transAxes,
            fontsize=9,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        # Joint angles info
        angles_text = "Joint Angles (deg):\n"
        for i, angle in enumerate(np.degrees(joint_angles)):
            angles_text += f"J{i + 1}: {angle:6.1f}°\n"

        self.ax.text2D(
            0.98,
            0.98,
            angles_text,
            transform=self.ax.transAxes,
            fontsize=8,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.5),
        )

    def clear_trail(self):
        """Clear trail history"""
        self.trail_history = []

    def animate_trajectory(
        self, joint_trajectory: List[np.ndarray], interval: int = 100
    ):
        """
        Animate a trajectory

        Args:
            joint_trajectory: list of joint configurations
            interval: animation interval in ms

        Returns:
            animation object
        """
        if self.fig is None:
            self.create_figure()

        def update(frame):
            self.update_visualization(joint_trajectory[frame])
            return []

        ani = animation.FuncAnimation(
            self.fig,
            update,
            frames=len(joint_trajectory),
            interval=interval,
            blit=True,
            repeat=False,
        )

        return ani

    def show(self):
        """Show the plot"""
        plt.tight_layout()
        plt.show()

    def save(self, filename: str = "robot_3d.png", dpi: int = 300):
        """Save visualization to file"""
        if self.fig:
            self.fig.savefig(filename, dpi=dpi, bbox_inches="tight")
            print(f"💾 Saved visualization to {filename}")


def test_kinematics_and_visualization():
    """Test kinematics and visualization"""
    from config_manager import ConfigManager

    # Create config
    config_mgr = ConfigManager()
    config = config_mgr.load()

    # Create kinematics
    kin = ForwardKinematics3D(config_mgr)

    # Test configurations
    test_configs = {
        "Home": np.zeros(6),
        "Extended": np.array([0, -np.pi / 4, np.pi / 2, 0, -np.pi / 4, 0]),
        "Folded": np.array([0, np.pi / 3, -np.pi / 2, 0, np.pi / 3, 0]),
        "Side": np.array([np.pi / 4, -np.pi / 6, np.pi / 3, 0, -np.pi / 6, 0]),
    }

    print("=" * 60)
    print("Testing Forward Kinematics")
    print("=" * 60)

    for name, joints in test_configs.items():
        T, states = kin.compute(joints)
        ee_pos = T[0:3, 3]

        print(f"\n{name}:")
        print(
            f"  End-effector position: [{ee_pos[0]:.1f}, {ee_pos[1]:.1f}, {ee_pos[2]:.1f}] mm"
        )
        print(f"  Distance from base: {np.linalg.norm(ee_pos):.1f} mm")

    # Visualization
    print("\n" + "=" * 60)
    print("Creating 3D visualization...")
    print("=" * 60)

    vis = RobotVisualizer3D(config_mgr)
    vis.create_figure()

    # Show extended position
    vis.update_visualization(test_configs["Extended"])
    vis.show()


if __name__ == "__main__":
    test_kinematics_and_visualization()
