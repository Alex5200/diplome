#!/usr/bin/env python3
"""
Robot Control TUI using Rich library
Interactive terminal interface for monitoring and controlling the robot.

Usage:
    python3 robot_tui.py

Controls:
    ↑/↓   - Select prev/next joint
    ←/→   - Decrease/Increase position
    1-6   - Select joint directly
    H     - Go to home position
    R     - Go to ready position
    S     - Emergency stop
    T     - Toggle torque
    Q     - Quit
"""

import argparse
import json
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.prompt import Prompt
    from rich import print as rprint
    from rich.console import Group

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, String
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint


@dataclass
class JointData:
    name: str = ""
    position: float = 0.0
    velocity: float = 0.0
    effort: float = 0.0
    target: float = 0.0
    torque: bool = True


class RobotTUI:
    """ROS2 interface for robot control."""

    def __init__(self):
        self.running = True
        self.selected_joint = 0
        self.joints: List[JointData] = [JointData(name=f"joint_{i + 1}") for i in range(6)]
        self.connected = False
        self.last_update = time.time()

        rclpy.init(args=sys.argv)
        self.node = rclpy.node.Node("robot_tui")

        # Subscribers
        self.node.create_subscription(JointState, "/robot/joint_states", self._on_joint_states, 10)
        self.node.create_subscription(String, "/robot/status", self._on_status, 10)

        # Publishers
        self.pub_cmd = self.node.create_publisher(JointTrajectoryPoint, "/robot/joint_cmd", 10)
        self.pub_stop = self.node.create_publisher(Empty, "/robot/stop", 10)

        # Spin thread
        self.spin_thread = threading.Thread(target=self._spin, daemon=True)
        self.spin_thread.start()

    def _spin(self):
        while self.running and rclpy.ok():
            rclpy.spin_once(self.node, timeout_sec=0.05)

    def _on_joint_states(self, msg: JointState):
        for i, name in enumerate(msg.name):
            if i < len(self.joints):
                self.joints[i].name = name
                if i < len(msg.position):
                    self.joints[i].position = msg.position[i]
                if i < len(msg.velocity):
                    self.joints[i].velocity = msg.velocity[i]
                if i < len(msg.effort):
                    self.joints[i].effort = msg.effort[i]
        self.last_update = time.time()

    def _on_status(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.connected = data.get("connected", False)
        except:
            pass

    def move_joint(self, joint_idx: int, position: float):
        positions = [j.position for j in self.joints]
        positions[joint_idx] = position
        self._publish_cmd(positions)
        self.joints[joint_idx].target = position

    def move_all(self, positions: List[float]):
        self._publish_cmd(positions)
        for i, pos in enumerate(positions):
            if i < len(self.joints):
                self.joints[i].target = pos

    def _publish_cmd(self, positions: List[float]):
        msg = JointTrajectoryPoint()
        msg.positions = positions
        msg.velocities = [0.0] * 6
        self.pub_cmd.publish(msg)

    def stop(self):
        self.pub_stop.publish(Empty())

    def shutdown(self):
        self.running = False
        self.node.destroy_node()
        rclpy.shutdown()


class RichTUI:
    """Rich-based terminal UI for robot control."""

    HOME_POSITIONS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    READY_POSITIONS = [0.0, -0.5, 0.8, 0.0, 0.5, 0.0]

    def __init__(self, robot: RobotTUI):
        self.robot = robot
        self.console = Console()
        self.step = 0.1
        self.step_large = 0.5
        self.running = True

    def create_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="status", size=3),
            Layout(name="joints"),
            Layout(name="controls", size=8),
        )
        return layout

    def render_header(self) -> Panel:
        return Panel(
            "[bold cyan]ROBOT CONTROL TUI[/bold cyan] [dim]v2.0[/dim]",
            style="bold blue",
            expand=False,
        )

    def render_status(self) -> Panel:
        status_color = "green" if self.robot.connected else "red"
        status_text = "✓ CONNECTED" if self.robot.connected else "✗ DISCONNECTED"
        update_age = time.time() - self.robot.last_update

        return Panel(
            f"[{status_color}]{status_text}[/{status_color}]  |  "
            f"Selected: [yellow]Joint {self.robot.selected_joint + 1}[/yellow]  |  "
            f"Update: {update_age:.1f}s ago",
            style="dim",
            expand=False,
        )

    def render_joints(self) -> Table:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Joint", style="cyan")
        table.add_column("Position", justify="right")
        table.add_column("Target", justify="right")
        table.add_column("Velocity", justify="right")
        table.add_column("Effort", justify="right")

        for i, joint in enumerate(self.robot.joints):
            marker = "→" if i == self.robot.selected_joint else " "
            style = "bold" if i == self.robot.selected_joint else ""

            # Color based on error
            pos_color = "green"
            if abs(joint.position - joint.target) > 0.1:
                pos_color = "yellow"
            if abs(joint.position - joint.target) > 0.5:
                pos_color = "red"

            table.add_row(
                f"{marker}[{'bold yellow' if i == self.robot.selected_joint else 'dim'}]{i + 1}[/]",
                f"[{style} cyan]{joint.name}[/]",
                f"[{pos_color}]{joint.position:8.3f}[/]",
                f"[blue]{joint.target:8.3f}[/]",
                f"[dim]{joint.velocity:8.4f}[/]",
                f"[dim]{joint.effort:8.2f}[/]",
            )

        return table

    def render_controls(self) -> Panel:
        controls = [
            "[bold]Navigation:[/bold]",
            "  ↑/↓  or  J/K     Select joint",
            "  ←/→  or  A/Z     Decrease/Increase position",
            "  1-6              Select joint directly",
            "",
            "[bold]Commands:[/bold]",
            "  H                Home position [dim](all zeros)[/dim]",
            "  R                Ready position [dim]([0, -0.5, 0.8, 0, 0.5, 0])[/dim]",
            "  S                Emergency STOP",
            "  T                Toggle torque",
            "",
            "[bold]Quit:[/bold]  Q",
        ]

        return Panel(
            "\n".join(controls),
            title="Controls",
            style="dim",
            border_style="blue",
        )

    def render_all(self):
        """Render complete UI as a Group for Live display."""
        return Group(
            self.render_header(),
            "",
            self.render_status(),
            "",
            self.render_joints(),
            "",
            self.render_controls(),
        )

    def handle_key(self, key: str) -> bool:
        """Handle key press. Returns False if should quit."""
        joint = self.robot.selected_joint

        if key in ["q", "Q", "ctrl-c"]:
            return False

        elif key in ["j", "J", "KEY_UP"]:
            self.robot.selected_joint = (joint - 1) % 6

        elif key in ["k", "K", "KEY_DOWN"]:
            self.robot.selected_joint = (joint + 1) % 6

        elif key in ["1", "2", "3", "4", "5", "6"]:
            self.robot.selected_joint = int(key) - 1

        elif key in ["a", "A", "KEY_LEFT"]:
            step = self.step_large if key.isupper() else self.step
            pos = self.robot.joints[joint].position - step
            self.robot.move_joint(joint, pos)

        elif key in ["z", "Z", "KEY_RIGHT"]:
            step = self.step_large if key.isupper() else self.step
            pos = self.robot.joints[joint].position + step
            self.robot.move_joint(joint, pos)

        elif key in ["h", "H"]:
            self.robot.move_all(self.HOME_POSITIONS)
            self.console.print(f"[green]→ Moving to HOME position[/green]")

        elif key in ["r", "R"]:
            self.robot.move_all(self.READY_POSITIONS)
            self.console.print(f"[green]→ Moving to READY position[/green]")

        elif key in ["s", "S"]:
            self.robot.stop()
            self.console.print(f"[bold red]!!! EMERGENCY STOP !!![/bold red]")

        elif key in ["t", "T"]:
            self.robot.joints[joint].torque = not self.robot.joints[joint].torque
            self.console.print(
                f"[yellow]→ Torque for joint {joint + 1}: {'ON' if self.robot.joints[joint].torque else 'OFF'}[/yellow]"
            )

        elif key == "?":
            self.console.print("\n[bold]Quick Help:[/bold]")
            self.console.print("Use arrow keys or J/K to navigate")
            self.console.print("A/Z for small moves, SHIFT+A/Z for large moves")
            self.console.print("H=Home, R=Ready, S=Stop, Q=Quit\n")

        return True

    def run(self):
        """Main loop with Live display."""
        self.console.print("[bold green]Robot Control TUI initialized![/bold green]")
        self.console.print("[dim]Waiting for robot topics...[/dim]")
        self.console.print("[dim]Press ? for help, Q to quit[/dim]\n")

        # Wait for data
        time.sleep(1)

        try:
            with Live(self.render_all, refresh_per_second=10, screen=True) as live:
                while self.running:
                    live.update(self.render_all())

                    # Simple input handling without blocking
                    try:
                        import select

                        if select.select([sys.stdin], [], [], 0.1)[0]:
                            key = sys.stdin.readline().strip()
                            if not self.handle_key(key):
                                break
                    except (ImportError, OSError):
                        # Fallback for Windows
                        import msvcrt

                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode("utf-8", errors="ignore")
                            if key in ["q", "Q"]:
                                break
                        time.sleep(0.1)

        except KeyboardInterrupt:
            pass
        finally:
            self.console.clear()
            self.console.print("[bold red]Shutting down...[/bold red]")
            self.robot.shutdown()


class SimpleTUI:
    """Fallback TUI without Rich (for terminals without rich support)."""

    HOME_POSITIONS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    READY_POSITIONS = [0.0, -0.5, 0.8, 0.0, 0.5, 0.0]

    def __init__(self, robot: RobotTUI):
        self.robot = robot

    def clear_screen(self):
        print("\033[2J\033[H", end="")

    def run(self):
        print("Robot Control TUI - Simple Mode")
        print("=" * 50)

        while True:
            self.clear_screen()

            status = "CONNECTED" if self.robot.connected else "DISCONNECTED"
            print(f"Status: {status} | Selected: Joint {self.robot.selected_joint + 1}")
            print("-" * 50)

            for i, joint in enumerate(self.robot.joints):
                marker = ">" if i == self.robot.selected_joint else " "
                print(
                    f"{marker}{i + 1}. {joint.name:12} pos={joint.position:8.3f} tgt={joint.target:8.3f}"
                )

            print("-" * 50)
            print("j/J/k/K: select | a/z: move | h:home r:ready s:stop q:quit")

            try:
                key = input("\n> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                key = "q"

            if key == "q":
                break
            self.handle_key(key)

        print("Goodbye!")
        self.robot.shutdown()

    def handle_key(self, key: str):
        joint = self.robot.selected_joint

        if key == "j":
            self.robot.selected_joint = (joint - 1) % 6
        elif key == "k":
            self.robot.selected_joint = (joint + 1) % 6
        elif key in ["1", "2", "3", "4", "5", "6"]:
            self.robot.selected_joint = int(key) - 1
        elif key == "a":
            pos = self.robot.joints[joint].position - 0.1
            self.robot.move_joint(joint, pos)
        elif key == "z":
            pos = self.robot.joints[joint].position + 0.1
            self.robot.move_joint(joint, pos)
        elif key == "h":
            self.robot.move_all(self.HOME_POSITIONS)
        elif key == "r":
            self.robot.move_all(self.READY_POSITIONS)
        elif key == "s":
            self.robot.stop()


def main():
    parser = argparse.ArgumentParser(description="Robot Control TUI")
    parser.add_argument("--host", default="localhost", help="ROS domain host")
    parser.add_argument("--simple", action="store_true", help="Use simple text mode")
    args = parser.parse_args()

    print("Initializing Robot Control TUI...")

    try:
        robot = RobotTUI()

        if HAS_RICH and not args.simple:
            tui = RichTUI(robot)
            tui.run()
        else:
            if HAS_RICH:
                print("[yellow]Note: Falling back to simple mode[/yellow]")
            tui = SimpleTUI(robot)
            tui.run()

    except ImportError as e:
        print(f"Error: {e}")
        print("Make sure rich is installed: pip install rich")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
