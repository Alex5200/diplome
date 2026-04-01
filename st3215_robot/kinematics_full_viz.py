#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Kinematics Visualization for ST3215 Robot
FIXED VERSION - Shows all 6 joints correctly
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.widgets import Slider, Button, CheckButtons
import sys
import os


class ST3215KinematicsViz:
    """Complete kinematics visualization with corrected parameters"""

    def __init__(self):
        """Initialize visualization with CORRECT DH parameters"""

        # CORRECT DH Parameters for ST3215 (in mm and radians)
        # Based on the technical drawing you provided
        self.dh_params = [
            # alpha,     a (mm),    d (mm),    theta_offset
            [-np.pi / 2, 0, 94.0, 0],  # J1: Base
            [0, 0, 0, -np.pi / 2],  # J2: Shoulder
            [0, 265.8, 0, 0],  # J3: Elbow
            [-np.pi / 2, 222.0, 51.0, 0],  # J4: Wrist Roll
            [np.pi / 2, 0, 0, 0],  # J5: Wrist Pitch
            [-np.pi / 2, 0, 0, 0],  # J6: Wrist Yaw
        ]

        # End effector offset
        self.ee_offset = 125.0  # mm

        # Joint angles (radians) - start with interesting pose
        self.joint_angles = np.array([0, -np.pi / 6, np.pi / 3, 0, -np.pi / 6, 0])

        # Joint information
        self.joints_info = [
            {
                "id": 1,
                "name": "Base",
                "axis": "Z",
                "range": "±360°",
                "motor": "YM080-230",
                "color": "#e41a1c",
            },
            {
                "id": 2,
                "name": "Shoulder",
                "axis": "Y",
                "range": "±360°",
                "motor": "YM080-230",
                "color": "#377eb8",
            },
            {
                "id": 3,
                "name": "Elbow",
                "axis": "Y",
                "range": "±150°",
                "motor": "YM070-210",
                "color": "#4daf4a",
            },
            {
                "id": 4,
                "name": "Wrist Roll",
                "axis": "X",
                "range": "±360°",
                "motor": "YM070-210",
                "color": "#984ea3",
            },
            {
                "id": 5,
                "name": "Wrist Pitch",
                "axis": "Y",
                "range": "±360°",
                "motor": "YM070-210",
                "color": "#ff7f00",
            },
            {
                "id": 6,
                "name": "Wrist Yaw",
                "axis": "Z",
                "range": "±360°",
                "motor": "YM070-210",
                "color": "#ffff33",
            },
        ]

        # Trail
        self.trail_history = []
        self.max_trail = 100
        self.show_trail = True

        # Create figure
        self.fig = plt.figure(figsize=(16, 10))

        # Create subplots
        self.ax_3d = self.fig.add_subplot(121, projection="3d")
        self.ax_params = self.fig.add_subplot(222)
        self.ax_angles = self.fig.add_subplot(224)

        plt.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.25)

        # Create sliders
        self._create_sliders()

        # Initial plot
        self._update_all_plots()

        print("✅ ST3215 Kinematics Visualization Initialized")
        print("💡 Use sliders to control each joint")
        print("📏 Link lengths: J2-J3 = 265.8mm, J3-J4 = 222.0mm")

    def dh_transform(self, alpha, a, d, theta):
        """Denavit-Hartenberg transformation matrix"""
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

    def forward_kinematics(self, joint_angles):
        """Compute forward kinematics and return all joint positions"""
        T = np.eye(4)
        positions = [np.array([0, 0, 0])]  # Base position

        transforms = []

        for i in range(6):
            alpha, a, d, theta_offset = self.dh_params[i]
            theta = joint_angles[i] + theta_offset

            Ti = self.dh_transform(alpha, a, d, theta)
            T = T @ Ti
            transforms.append(T.copy())

            # Extract position
            pos = T[0:3, 3]
            positions.append(pos.copy())

        # End effector
        T_ee = np.eye(4)
        T_ee[2, 3] = self.ee_offset
        T = T @ T_ee
        ee_pos = T[0:3, 3]
        positions.append(ee_pos)

        return positions, transforms, T

    def _create_sliders(self):
        """Create sliders for all 6 joints"""
        self.sliders = []
        slider_colors = [joint["color"] for joint in self.joints_info]

        for i in range(6):
            # Slider axis position
            ax_slider = plt.axes(
                [0.55 + (i % 2) * 0.22, 0.18 - (i // 2) * 0.04, 0.18, 0.025]
            )

            # Initial value in degrees
            init_deg = np.degrees(self.joint_angles[i])

            # Create slider
            slider = Slider(
                ax=ax_slider,
                label=f"J{i + 1}\n{self.joints_info[i]['name']}",
                valmin=-180,
                valmax=180,
                valinit=init_deg,
                valstep=1,
                color=slider_colors[i],
            )

            slider.on_changed(self._on_slider_change)
            self.sliders.append(slider)

        # Buttons
        ax_reset = plt.axes([0.75, 0.05, 0.10, 0.04])
        self.btn_reset = Button(ax_reset, "🏠 Home", hovercolor="0.975")
        self.btn_reset.on_clicked(self._reset_joints)

        ax_clear = plt.axes([0.87, 0.05, 0.10, 0.04])
        self.btn_clear = Button(ax_clear, "🗑️ Trail", hovercolor="0.975")
        self.btn_clear.on_clicked(self._clear_trail)

    def _on_slider_change(self, val):
        """Handle slider change"""
        for i, slider in enumerate(self.sliders):
            self.joint_angles[i] = np.radians(slider.val)
        self._update_all_plots()

    def _reset_joints(self, event):
        """Reset to home position"""
        home_angles = [0, -np.pi / 6, np.pi / 3, 0, -np.pi / 6, 0]
        for i, slider in enumerate(self.sliders):
            slider.set_val(np.degrees(home_angles[i]))

    def _clear_trail(self, event):
        """Clear trail"""
        self.trail_history = []
        self._update_all_plots()

    def _update_all_plots(self):
        """Update all subplots"""
        self._update_3d_plot()
        self._update_params_plot()
        self._update_angles_plot()
        self.fig.canvas.draw_idle()

    def _update_3d_plot(self):
        """Update 3D robot visualization - FIXED"""
        self.ax_3d.clear()

        # Get positions
        positions, transforms, T_ee = self.forward_kinematics(self.joint_angles)
        ee_pos = positions[-1]

        # Setup axes with CORRECT scale
        self.ax_3d.set_xlabel("X (mm)", fontsize=11, fontweight="bold")
        self.ax_3d.set_ylabel("Y (mm)", fontsize=11, fontweight="bold")
        self.ax_3d.set_zlabel("Z (mm)", fontsize=11, fontweight="bold")
        self.ax_3d.set_title(
            "🤖 ST3215 Robot - All 6 Joints", fontsize=13, fontweight="bold"
        )

        # View angle
        self.ax_3d.view_init(elev=25, azim=45)

        # Grid size based on robot reach
        grid_size = 600  # mm
        self.ax_3d.set_xlim([-grid_size, grid_size])
        self.ax_3d.set_ylim([-grid_size, grid_size])
        self.ax_3d.set_zlim([0, grid_size])

        self.ax_3d.grid(True, alpha=0.3, linestyle="--")

        # Draw floor grid
        self._draw_floor_grid(grid_size)

        # Draw base
        self.ax_3d.scatter(
            [0],
            [0],
            [0],
            c="#1f77b4",
            s=400,
            marker="s",
            label="Base",
            alpha=0.8,
            edgecolors="black",
            linewidth=2,
        )

        # Draw ALL links and joints
        for i in range(len(positions) - 1):
            pos1 = positions[i]
            pos2 = positions[i + 1]

            # Draw link
            color = (
                self.joints_info[i]["color"] if i < len(self.joints_info) else "gray"
            )
            self.ax_3d.plot(
                [pos1[0], pos2[0]],
                [pos1[1], pos2[1]],
                [pos1[2], pos2[2]],
                color=color,
                linewidth=8,
                alpha=0.8,
                solid_capstyle="round",
            )

            # Draw joint (except base and end effector)
            if i > 0 and i < len(positions) - 1:
                self.ax_3d.scatter(
                    [pos2[0]],
                    [pos2[1]],
                    [pos2[2]],
                    c=color,
                    s=300,
                    marker="o",
                    label=f"J{i + 1}",
                    alpha=0.9,
                    edgecolors="black",
                    linewidth=2,
                )

                # Joint number
                self.ax_3d.text(
                    pos2[0],
                    pos2[1],
                    pos2[2] + 30,
                    f"J{i + 1}",
                    fontsize=11,
                    fontweight="bold",
                    ha="center",
                    va="bottom",
                    color="black",
                )

                # Draw coordinate frame
                self._draw_coordinate_frame(
                    pos2, transforms[i - 1] if i > 0 else np.eye(4)
                )

        # End effector
        self.ax_3d.scatter(
            [ee_pos[0]],
            [ee_pos[1]],
            [ee_pos[2]],
            c="red",
            s=500,
            marker="*",
            label="End Effector",
            edgecolors="darkred",
            linewidth=3,
        )

        # Trail
        if self.show_trail:
            self.trail_history.append(ee_pos.copy())
            if len(self.trail_history) > self.max_trail:
                self.trail_history.pop(0)

            if len(self.trail_history) > 1:
                trail_array = np.array(self.trail_history)
                self.ax_3d.plot(
                    trail_array[:, 0],
                    trail_array[:, 1],
                    trail_array[:, 2],
                    color="purple",
                    linewidth=3,
                    alpha=0.6,
                    label="Trail",
                )

        # Legend
        self.ax_3d.legend(loc="upper left", fontsize=9)

        # Info text
        self._add_info_text(ee_pos)

        print(
            f"\r📍 EE Position: X={ee_pos[0]:6.1f} Y={ee_pos[1]:6.1f} Z={ee_pos[2]:6.1f} mm",
            end="",
        )

    def _draw_floor_grid(self, grid_size):
        """Draw floor grid"""
        z_floor = 0
        for x in np.linspace(-grid_size, grid_size, 13):
            self.ax_3d.plot(
                [x, x],
                [-grid_size, grid_size],
                [z_floor, z_floor],
                "k-",
                alpha=0.1,
                linewidth=0.5,
            )
        for y in np.linspace(-grid_size, grid_size, 13):
            self.ax_3d.plot(
                [-grid_size, grid_size],
                [y, y],
                [z_floor, z_floor],
                "k-",
                alpha=0.1,
                linewidth=0.5,
            )

    def _draw_coordinate_frame(self, position, transform):
        """Draw coordinate frame at joint"""
        scale = 50  # mm
        R = transform[0:3, 0:3]

        axes_colors = ["red", "green", "blue"]
        axes_labels = ["X", "Y", "Z"]

        for i in range(3):
            axis_end = position + R[:, i] * scale
            self.ax_3d.plot(
                [position[0], axis_end[0]],
                [position[1], axis_end[1]],
                [position[2], axis_end[2]],
                color=axes_colors[i],
                linewidth=2,
                alpha=0.7,
            )

            # Label
            label_pos = axis_end + R[:, i] * 10
            self.ax_3d.text(
                label_pos[0],
                label_pos[1],
                label_pos[2],
                axes_labels[i],
                fontsize=8,
                fontweight="bold",
                color=axes_colors[i],
            )

    def _add_info_text(self, ee_pos):
        """Add information text"""
        info_text = (
            f"📍 End-Effector:\n"
            f"X: {ee_pos[0]:7.1f} mm\n"
            f"Y: {ee_pos[1]:7.1f} mm\n"
            f"Z: {ee_pos[2]:7.1f} mm\n\n"
            f"📏 Distance: {np.linalg.norm(ee_pos):7.1f} mm\n\n"
            f"🔧 Joints:\n"
        )

        for i, angle in enumerate(np.degrees(self.joint_angles)):
            info_text += f"J{i + 1}: {angle:6.1f}°\n"

        self.ax_3d.text2D(
            0.02,
            0.98,
            info_text,
            transform=self.ax_3d.transAxes,
            fontsize=9,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        )

    def _update_params_plot(self):
        """Update DH parameters table"""
        self.ax_params.clear()
        self.ax_params.axis("off")

        # Table data
        table_data = []
        for i in range(6):
            alpha, a, d, theta_off = self.dh_params[i]
            angle_deg = np.degrees(self.joint_angles[i])
            row = [
                f"J{i + 1}",
                self.joints_info[i]["name"],
                f"{alpha:.2f}",
                f"{a:6.1f}",
                f"{d:6.1f}",
                f"{angle_deg:6.1f}°",
            ]
            table_data.append(row)

        columns = ["Joint", "Name", "α (rad)", "a (mm)", "d (mm)", "θ (deg)"]

        table = self.ax_params.table(
            cellText=table_data, colLabels=columns, loc="center", cellLoc="center"
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.0, 1.5)

        # Style
        for i in range(len(table_data) + 1):
            for j in range(len(columns)):
                if i == 0:
                    table[(i, j)].set_facecolor("#377eb8")
                    table[(i, j)].set_text_props(color="white", fontweight="bold")
                else:
                    table[(i, j)].set_facecolor("#f0f0f0" if i % 2 == 0 else "white")

        self.ax_params.set_title(
            "📋 DH Parameters", fontsize=12, fontweight="bold", pad=15
        )

    def _update_angles_plot(self):
        """Update joint angles bar chart"""
        self.ax_angles.clear()

        angles_deg = np.degrees(self.joint_angles)
        colors = [joint["color"] for joint in self.joints_info]
        names = [f"J{i + 1}" for i in range(6)]

        bars = self.ax_angles.bar(
            names, angles_deg, color=colors, edgecolors="black", linewidth=1.5
        )

        # Add value labels
        for bar, angle in zip(bars, angles_deg):
            height = bar.get_height()
            va = "bottom" if height >= 0 else "top"
            self.ax_angles.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{angle:.0f}°",
                ha="center",
                va=va,
                fontsize=9,
                fontweight="bold",
            )

        # Limits
        self.ax_angles.axhline(y=0, color="black", linewidth=1)
        self.ax_angles.set_ylim([-180, 180])
        self.ax_angles.set_ylabel("Angle (degrees)", fontsize=10, fontweight="bold")
        self.ax_angles.set_title("⚙️ Joint Angles", fontsize=12, fontweight="bold")
        self.ax_angles.grid(True, alpha=0.3, axis="y")

    def show(self):
        """Show the visualization"""
        plt.show()


def main():
    """Main function"""
    print("\n" + "=" * 70)
    print(" " * 15 + "🤖 ST3215 ROBOT - 6 JOINTS VISUALIZATION")
    print("=" * 70)
    print("\n📏 Robot Specifications:")
    print("  • Link 2-3: 265.8 mm")
    print("  • Link 3-4: 222.0 mm")
    print("  • Base height: 94.0 mm")
    print("  • End effector: 125.0 mm")
    print("\n🎮 Controls:")
    print("  • Use sliders to move each joint")
    print("  • 'Home' button - reset to home position")
    print("  • 'Trail' shows end-effector path")
    print("=" * 70 + "\n")

    viz = ST3215KinematicsViz()
    viz.show()

    print("\n\n✅ Visualization closed")


if __name__ == "__main__":
    main()
