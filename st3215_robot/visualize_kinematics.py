#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3D Kinematics Visualization for ST3215 Robot
Interactive visualization with matplotlib
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button
from config_manager import ConfigManager
from kinematics_3d import ForwardKinematics3D


class KinematicsVisualizer:
    """Interactive 3D kinematics visualizer"""

    def __init__(self):
        self.config_mgr = ConfigManager()
        self.config_mgr.load()
        self.kinematics = ForwardKinematics3D(self.config_mgr)

        # Initial joint angles (radians)
        self.joint_angles = np.zeros(6)

        # Create figure
        self.fig = plt.figure(figsize=(12, 8))
        self.ax = self.fig.add_subplot(111, projection="3d")
        plt.subplots_adjust(bottom=0.25)  # Space for sliders

        # Colors
        self.colors = {
            "base": "#1f77b4",
            "joint": "#ff7f0e",
            "link": "#2ca02c",
            "end_effector": "#d62728",
            "trail": "#9467bd",
        }

        self.trail_history = []
        self.max_trail = 50

        self._setup_plot()
        self._create_sliders()
        self._update_plot()

    def _setup_plot(self):
        """Setup 3D plot"""
        self.ax.clear()

        # Labels
        self.ax.set_xlabel("X (mm)", fontsize=11, fontweight="bold")
        self.ax.set_ylabel("Y (mm)", fontsize=11, fontweight="bold")
        self.ax.set_zlabel("Z (mm)", fontsize=11, fontweight="bold")

        # Title
        self.ax.set_title(
            "ST3215 Robot - 3D Kinematics Visualization",
            fontsize=13,
            fontweight="bold",
            pad=20,
        )

        # View angle
        self.ax.view_init(elev=30, azim=45)

        # Grid
        grid_size = self.config_mgr.config.vis_grid_size / 2
        self.ax.set_xlim([-grid_size, grid_size])
        self.ax.set_ylim([-grid_size, grid_size])
        self.ax.set_zlim([0, grid_size])

        self.ax.grid(True, linestyle="--", alpha=0.6)

    def _create_sliders(self):
        """Create sliders for joint angles"""
        self.sliders = []

        joint_names = ["Joint 1", "Joint 2", "Joint 3", "Joint 4", "Joint 5", "Joint 6"]

        for i, name in enumerate(joint_names):
            # Slider position
            ax_slider = plt.axes([0.125, 0.18 - i * 0.025, 0.75, 0.02])

            # Create slider (in degrees for user-friendliness)
            slider = Slider(
                ax=ax_slider,
                label=f"{name} (deg)",
                valmin=-180,
                valmax=180,
                valinit=0,
                valstep=1,
            )

            # Update callback
            slider.on_changed(self._on_slider_change)
            self.sliders.append(slider)

        # Buttons
        ax_reset = plt.axes([0.8, 0.05, 0.1, 0.04])
        self.btn_reset = Button(ax_reset, "Сбросить", hovercolor="0.975")
        self.btn_reset.on_clicked(self._reset_joints)

        ax_clear = plt.axes([0.65, 0.05, 0.1, 0.04])
        self.btn_clear = Button(ax_clear, "Очистить след", hovercolor="0.975")
        self.btn_clear.on_clicked(self._clear_trail)

    def _on_slider_change(self, val):
        """Handle slider change"""
        # Update joint angles from sliders (convert to radians)
        for i, slider in enumerate(self.sliders):
            self.joint_angles[i] = np.radians(slider.val)

        self._update_plot()

    def _reset_joints(self, event):
        """Reset all joints to zero"""
        for slider in self.sliders:
            slider.reset()

    def _clear_trail(self, event):
        """Clear trail history"""
        self.trail_history = []
        self._update_plot()

    def _update_plot(self):
        """Update 3D plot"""
        self.ax.clear()
        self._setup_plot()

        # Get positions
        positions = self.kinematics.get_all_positions(self.joint_angles)
        ee_pos = positions[-1]

        # Draw grid floor
        self._draw_grid_floor()

        # Draw base
        self.ax.scatter(
            [positions[0, 0]],
            [positions[0, 1]],
            [positions[0, 2]],
            c=self.colors["base"],
            s=200,
            marker="s",
            label="Base",
            alpha=0.8,
        )

        # Draw links
        for i in range(len(positions) - 1):
            self.ax.plot(
                [positions[i, 0], positions[i + 1, 0]],
                [positions[i, 1], positions[i + 1, 1]],
                [positions[i, 2], positions[i + 1, 2]],
                color=self.colors["link"],
                linewidth=4,
                alpha=0.8,
            )

            # Draw joints
            if i > 0:
                self.ax.scatter(
                    [positions[i, 0]],
                    [positions[i, 1]],
                    [positions[i, 2]],
                    c=self.colors["joint"],
                    s=100,
                    marker="o",
                    alpha=0.9,
                )

        # Draw end-effector
        self.ax.scatter(
            [ee_pos[0]],
            [ee_pos[1]],
            [ee_pos[2]],
            c=self.colors["end_effector"],
            s=200,
            marker="*",
            label="End Effector",
            alpha=1.0,
        )

        # Update trail
        self.trail_history.append(ee_pos.copy())
        if len(self.trail_history) > self.max_trail:
            self.trail_history.pop(0)

        # Draw trail
        if len(self.trail_history) > 1:
            trail_array = np.array(self.trail_history)
            self.ax.plot(
                trail_array[:, 0],
                trail_array[:, 1],
                trail_array[:, 2],
                color=self.colors["trail"],
                linewidth=2,
                alpha=0.6,
                linestyle="-",
                label="Trail",
            )

        # Add info text
        self._add_info_text(ee_pos)

        # Legend
        self.ax.legend(loc="upper left")

        # Redraw
        self.fig.canvas.draw_idle()

    def _draw_grid_floor(self):
        """Draw grid on floor"""
        grid_size = self.config_mgr.config.vis_grid_size / 2
        z_floor = 0

        for x in np.linspace(-grid_size, grid_size, 9):
            self.ax.plot(
                [x, x],
                [-grid_size, grid_size],
                [z_floor, z_floor],
                "k-",
                alpha=0.1,
                linewidth=0.5,
            )

        for y in np.linspace(-grid_size, grid_size, 9):
            self.ax.plot(
                [-grid_size, grid_size],
                [y, y],
                [z_floor, z_floor],
                "k-",
                alpha=0.1,
                linewidth=0.5,
            )

    def _add_info_text(self, ee_pos):
        """Add information text"""
        info_text = (
            f"End-Effector Position:\n"
            f"X: {ee_pos[0]:.1f} mm\n"
            f"Y: {ee_pos[1]:.1f} mm\n"
            f"Z: {ee_pos[2]:.1f} mm\n\n"
            f"Distance: {np.linalg.norm(ee_pos):.1f} mm\n\n"
            f"Joint Angles (deg):\n"
        )

        for i, angle in enumerate(np.degrees(self.joint_angles)):
            info_text += f"J{i + 1}: {angle:6.1f}°\n"

        self.ax.text2D(
            0.02,
            0.98,
            info_text,
            transform=self.ax.transAxes,
            fontsize=9,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

    def show(self):
        """Show the visualization"""
        plt.show()

    def animate_trajectory(self, trajectory, interval=100):
        """
        Animate a trajectory

        Args:
            trajectory: list of joint angle arrays
            interval: animation interval in ms
        """
        self.ax.clear()
        self._setup_plot()

        def update(frame):
            self.joint_angles = trajectory[frame]
            self._update_plot()
            return []

        ani = animation.FuncAnimation(
            self.fig, update, frames=len(trajectory), interval=interval, blit=True
        )

        plt.show()


def test_predefined_poses():
    """Test with predefined poses"""
    config_mgr = ConfigManager()
    config_mgr.load()
    kin = ForwardKinematics3D(config_mgr)

    # Predefined poses
    poses = {
        "Home": np.zeros(6),
        "Extended": np.array([0, -np.pi / 4, np.pi / 2, 0, -np.pi / 4, 0]),
        "Folded": np.array([0, np.pi / 3, -np.pi / 2, 0, np.pi / 3, 0]),
        "Side Reach": np.array([np.pi / 4, -np.pi / 6, np.pi / 3, 0, -np.pi / 6, 0]),
        "Up": np.array([0, -np.pi / 3, np.pi / 3, 0, np.pi / 3, 0]),
    }

    print("=" * 60)
    print("ST3215 Robot - Predefined Poses")
    print("=" * 60)

    for name, joints in poses.items():
        T, states = kin.compute(joints)
        ee_pos = T[0:3, 3]

        print(f"\n{name}:")
        print(f"  Position: [{ee_pos[0]:6.1f}, {ee_pos[1]:6.1f}, {ee_pos[2]:6.1f}] mm")
        print(f"  Distance: {np.linalg.norm(ee_pos):.1f} mm")
        print(f"  Joints (deg): {[f'{np.degrees(a):5.1f}' for a in joints]}")

    print("\n" + "=" * 60)


def main():
    """Main function"""
    import sys

    print("ST3215 Robot Kinematics Visualization")
    print("=" * 50)
    print("\nВыберите режим:")
    print("1. Интерактивная визуализация (с ползунками)")
    print("2. Тест预设ованных позиций")
    print("3. Анимация траектории")

    choice = input("\nВаш выбор (1-3): ").strip()

    if choice == "1":
        print("\n🚀 Запуск интерактивной визуализации...")
        print("💡 Используйте ползунки для управления суставами")
        vis = KinematicsVisualizer()
        vis.show()

    elif choice == "2":
        print("\n📊 Тест预设ованных позиций:")
        test_predefined_poses()

    elif choice == "3":
        print("\n🎬 Анимация траектории...")

        # Create trajectory
        config_mgr = ConfigManager()
        config_mgr.load()
        kin = ForwardKinematics3D(config_mgr)

        # Define trajectory points
        trajectory = [
            np.zeros(6),
            np.array([0.5, -0.3, 0.8, 0, -0.4, 0]),
            np.array([1.0, -0.5, 1.2, 0, -0.6, 0]),
            np.array([0.5, -0.3, 0.8, 0, -0.4, 0]),
            np.zeros(6),
        ]

        vis = KinematicsVisualizer()
        vis.animate_trajectory(trajectory, interval=500)

    else:
        print("❌ Неверный выбор!")
        sys.exit(1)


if __name__ == "__main__":
    main()
