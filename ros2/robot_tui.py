#!/usr/bin/env python3
"""
Robot Control Terminal UI
Interactive terminal interface for monitoring and controlling the robot.

Usage:
    python3 robot_tui.py [--host HOST] [--port PORT]

Controls:
    j/J - Decrease/Increase joint selection
    a/z - Decrease/Increase position of selected joint
    1-6 - Select joint directly
    h   - Go to home position
    r   - Go to ready position
    s   - Emergency stop
    t   - Toggle torque on/off for selected joint
    q   - Quit
"""

import argparse
import json
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, String
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint

try:
    import npyscreen

    HAS_NPYSCREEN = True
except ImportError:
    HAS_NPYSCREEN = False


@dataclass
class JointData:
    name: str = ""
    position: float = 0.0
    velocity: float = 0.0
    effort: float = 0.0
    target: float = 0.0


class RobotTUI:
    """Terminal UI for robot control."""

    def __init__(self):
        self.running = True
        self.selected_joint = 0
        self.joints = [JointData(name=f"joint_{i + 1}") for i in range(6)]
        self.connected = False
        self.torque_enabled = [True] * 6

        # Initialize ROS
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
            rclpy.spin_once(self.node, timeout_sec=0.1)

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

    def _on_status(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.connected = data.get("connected", False)
        except:
            pass

    def move_joint(self, joint_idx: int, position: float):
        """Send position command for single joint."""
        positions = [j.position for j in self.joints]
        positions[joint_idx] = position
        self._publish_cmd(positions)

    def move_all(self, positions: list):
        """Send position command for all joints."""
        self._publish_cmd(positions)

    def _publish_cmd(self, positions: list):
        msg = JointTrajectoryPoint()
        msg.positions = positions
        msg.velocities = [0.0] * 6
        self.pub_cmd.publish(msg)

    def stop(self):
        """Emergency stop."""
        self.pub_stop.publish(Empty())

    def shutdown(self):
        """Clean shutdown."""
        self.running = False
        self.node.destroy_node()
        rclpy.shutdown()


class SimpleTUI:
    """Simple text-based TUI using only stdlib."""

    def __init__(self, robot: RobotTUI):
        self.robot = robot
        self.joint_step = 0.1  # radians

    def clear_screen(self):
        print("\033[2J\033[H", end="")

    def print_header(self):
        print("=" * 60)
        print("  ROBOT CONTROL TUI - ROS2 Topic Interface")
        print("=" * 60)
        status = "CONNECTED" if self.robot.connected else "DISCONNECTED"
        print(f"  Status: {status}")
        print("=" * 60)

    def print_joints(self):
        print("\n  JOINT STATES:")
        print("  " + "-" * 56)
        print("  #  Name          Position    Target      Velocity    Effort")
        print("  " + "-" * 56)

        for i, joint in enumerate(self.robot.joints):
            marker = ">" if i == self.robot.selected_joint else " "
            name = joint.name[:14].ljust(14)
            pos = f"{joint.position:8.3f}"
            tgt = f"{joint.target:8.3f}"
            vel = f"{joint.velocity:8.4f}"
            eff = f"{joint.effort:8.2f}"
            print(f"  {marker}{i + 1}  {name}  {pos}  {tgt}  {vel}  {eff}")

    def print_controls(self):
        print("\n  CONTROLS:")
        print("  " + "-" * 56)
        print("  j/J      - Select prev/next joint")
        print("  a/z      - Decrease/Increase position (0.1 rad)")
        print("  A/Z      - Decrease/Increase position (1.0 rad)")
        print("  1-6      - Select joint directly")
        print("  h        - Go to HOME (all zeros)")
        print("  r        - Go to READY position")
        print("  t        - Toggle torque")
        print("  s        - EMERGENCY STOP")
        print("  q        - Quit")
        print("  " + "-" * 56)

    def print_help(self):
        print("\n  Tips:")
        print("  - Use 'j' and 'J' to change selected joint (marked with >)")
        print("  - Use 'a' and 'z' to move selected joint slowly")
        print("  - Use arrow keys for fine control")
        print("  - Home: [0, 0, 0, 0, 0, 0] radians")
        print("  - Ready: [0, -0.5, 0.8, 0, 0.5, 0] radians")

    def run(self):
        """Main TUI loop."""
        self.clear_screen()

        while True:
            self.clear_screen()
            self.print_header()
            self.print_joints()
            self.print_controls()

            try:
                key = input("\n  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                key = "q"

            self.handle_input(key)

            if key == "q":
                break

        print("\n\nShutting down...")
        self.robot.shutdown()

    def handle_input(self, key: str):
        """Handle user input."""
        joint = self.robot.selected_joint

        if key == "j":
            self.robot.selected_joint = (joint - 1) % 6
        elif key == "j":
            self.robot.selected_joint = (joint + 1) % 6
        elif key == "j":
            self.robot.selected_joint = max(0, joint - 1)
        elif key == "l":
            self.robot.selected_joint = min(5, joint + 1)
        elif key in ["1", "2", "3", "4", "5", "6"]:
            self.robot.selected_joint = int(key) - 1
        elif key == "a":
            pos = self.robot.joints[joint].position - self.joint_step
            self.robot.move_joint(joint, pos)
            self.robot.joints[joint].target = pos
        elif key == "z":
            pos = self.robot.joints[joint].position + self.joint_step
            self.robot.move_joint(joint, pos)
            self.robot.joints[joint].target = pos
        elif key == "A":
            pos = self.robot.joints[joint].position - 1.0
            self.robot.move_joint(joint, pos)
            self.robot.joints[joint].target = pos
        elif key == "Z":
            pos = self.robot.joints[joint].position + 1.0
            self.robot.move_joint(joint, pos)
            self.robot.joints[joint].target = pos
        elif key == "h":
            home = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            self.robot.move_all(home)
            for i, j in enumerate(self.robot.joints):
                j.target = 0.0
            print("  >> Moving to HOME position...")
        elif key == "r":
            ready = [0.0, -0.5, 0.8, 0.0, 0.5, 0.0]
            self.robot.move_all(ready)
            for i, pos in enumerate(ready):
                self.robot.joints[i].target = pos
            print("  >> Moving to READY position...")
        elif key == "t":
            print(f"  >> Toggle torque for joint {joint + 1}...")
        elif key == "s":
            print("  >> EMERGENCY STOP!")
            self.robot.stop()
        elif key == "?":
            self.print_help()
        else:
            if key:
                print(f"  >> Unknown command: {key}")


def main():
    parser = argparse.ArgumentParser(description="Robot Control TUI")
    parser.add_argument("--host", default="localhost", help="ROS domain host")
    args = parser.parse_args()

    print("Initializing Robot Control TUI...")
    print(f"Connecting to ROS domain: {args.host}")

    try:
        robot = RobotTUI()
        tui = SimpleTUI(robot)

        # Wait for connection
        print("Waiting for robot topics...")
        time.sleep(2)

        tui.run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
