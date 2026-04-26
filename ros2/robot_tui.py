#!/usr/bin/env python3
"""
Robot Control TUI — simple print/input terminal interface.

Works in any terminal including Docker containers (no raw-TTY required).
Press Enter after each command.

Controls:
    1-6     select joint
    a / z   move selected joint -0.1 / +0.1 rad
    A / Z   move selected joint -0.5 / +0.5 rad
    h       HOME  position  [0, 0, 0, 0, 0, 0]
    r       READY position  [0, -0.5, 0.8, 0, 0.5, 0]
    s       EMERGENCY STOP
    p       print current state
    ?       help
    q       quit
"""

from __future__ import annotations

import json
import sys
import threading
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty, String
from trajectory_msgs.msg import JointTrajectoryPoint

# ── Constants ────────────────────────────────────────────────────────────────

JOINT_NAMES = ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]

HOME_POSITIONS  = [0.0,  0.0, 0.0, 0.0, 0.0, 0.0]
READY_POSITIONS = [0.0, -0.5, 0.8, 0.0, 0.5, 0.0]

STEP_SMALL = 0.1   # rad
STEP_LARGE = 0.5   # rad

HELP_TEXT = """
  Commands
  ────────
  1-6       select joint (current selected marked with >)
  a / z     move selected joint  -0.1 / +0.1 rad
  A / Z     move selected joint  -0.5 / +0.5 rad
  h         go to HOME  [0, 0, 0, 0, 0, 0]
  r         go to READY [0, -0.5, 0.8, 0, 0.5, 0]
  s         EMERGENCY STOP
  p         print current joint state
  ?         show this help
  q         quit
"""

# ── ROS2 node ────────────────────────────────────────────────────────────────


class RobotTUI(Node):
    """Thin ROS2 node: subscribes to joint states, publishes commands."""

    def __init__(self) -> None:
        super().__init__("robot_tui")

        self._lock = threading.Lock()
        self._positions: list[float] = [0.0] * 6
        self._targets:   list[float] = [0.0] * 6
        self._connected: bool = False
        self._last_update: float = 0.0

        self.create_subscription(JointState, "/robot/joint_states", self._on_joints, 10)
        self.create_subscription(String,     "/robot/status",        self._on_status, 10)

        self._pub_cmd  = self.create_publisher(JointTrajectoryPoint, "/robot/joint_cmd", 10)
        self._pub_stop = self.create_publisher(Empty,                "/robot/stop",      10)

    # ── Callbacks ──────────────────────────────────────────────────────────

    def _on_joints(self, msg: JointState) -> None:
        with self._lock:
            for i, pos in enumerate(msg.position[:6]):
                self._positions[i] = pos
            self._last_update = time.time()

    def _on_status(self, msg: String) -> None:
        try:
            self._connected = json.loads(msg.data).get("connected", False)
        except Exception:
            pass

    # ── Commands ───────────────────────────────────────────────────────────

    def send_positions(self, positions: list[float]) -> None:
        msg = JointTrajectoryPoint()
        msg.positions  = list(positions)
        msg.velocities = [0.0] * 6
        self._pub_cmd.publish(msg)
        with self._lock:
            self._targets = list(positions)

    def move_joint(self, joint_idx: int, delta: float) -> None:
        with self._lock:
            new_targets = list(self._targets)
        new_targets[joint_idx] = round(new_targets[joint_idx] + delta, 4)
        self.send_positions(new_targets)

    def emergency_stop(self) -> None:
        self._pub_stop.publish(Empty())

    # ── State accessors ────────────────────────────────────────────────────

    @property
    def positions(self) -> list[float]:
        with self._lock:
            return list(self._positions)

    @property
    def targets(self) -> list[float]:
        with self._lock:
            return list(self._targets)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def data_age_sec(self) -> float:
        if self._last_update == 0.0:
            return -1.0
        return time.time() - self._last_update


# ── UI helpers ───────────────────────────────────────────────────────────────


def print_state(node: RobotTUI, selected: int) -> None:
    """Print a clean table of joint states."""
    status = "CONNECTED" if node.connected else "DISCONNECTED"
    age    = node.data_age_sec
    age_str = f"{age:.1f}s ago" if age >= 0 else "no data"

    print()
    print(f"  Status: {status}  |  data: {age_str}  |  selected: joint_{selected}")
    print("  " + "─" * 56)
    print(f"  {'':3} {'Joint':<10} {'Position':>10} {'Target':>10}  err")
    print("  " + "─" * 56)

    positions = node.positions
    targets   = node.targets

    for i in range(6):
        marker = ">" if i == selected else " "
        err    = abs(positions[i] - targets[i])
        flag   = " !" if err > 0.1 else "  "
        print(f"  {marker}{i+1}  joint_{i:<6} {positions[i]:>10.3f} {targets[i]:>10.3f} {flag}")

    print("  " + "─" * 56)
    print("  [1-6] select  [a/z] ±0.1  [A/Z] ±0.5  [h]ome  [r]eady  [s]top  [?]help  [q]uit")


# ── Main loop ────────────────────────────────────────────────────────────────


def run_tui(node: RobotTUI) -> None:
    selected = 0  # 0-indexed joint

    print("\n" + "=" * 60)
    print("  ROBOT CONTROL TUI  (type ? for help, q to quit)")
    print("=" * 60)
    print("  Waiting for robot topics… (robot_node_v2 must be running)")
    time.sleep(1)
    print_state(node, selected)

    while True:
        try:
            raw = input("\n  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Interrupted — shutting down.")
            break

        if not raw:
            print_state(node, selected)
            continue

        cmd = raw[0]  # use first character

        # ── navigation ──────────────────────────────────────────────────
        if cmd in "123456":
            selected = int(cmd) - 1
            print(f"  Selected: joint_{selected}")
            print_state(node, selected)

        # ── move small ──────────────────────────────────────────────────
        elif cmd == "a":
            node.move_joint(selected, -STEP_SMALL)
            print(f"  joint_{selected} → {node.targets[selected]:.3f}")
            print_state(node, selected)

        elif cmd == "z":
            node.move_joint(selected, +STEP_SMALL)
            print(f"  joint_{selected} → {node.targets[selected]:.3f}")
            print_state(node, selected)

        # ── move large ──────────────────────────────────────────────────
        elif cmd == "A":
            node.move_joint(selected, -STEP_LARGE)
            print(f"  joint_{selected} → {node.targets[selected]:.3f}")
            print_state(node, selected)

        elif cmd == "Z":
            node.move_joint(selected, +STEP_LARGE)
            print(f"  joint_{selected} → {node.targets[selected]:.3f}")
            print_state(node, selected)

        # ── presets ─────────────────────────────────────────────────────
        elif cmd in "hH":
            node.send_positions(HOME_POSITIONS)
            print("  → Moving to HOME [0, 0, 0, 0, 0, 0]")
            print_state(node, selected)

        elif cmd in "rR":
            node.send_positions(READY_POSITIONS)
            print("  → Moving to READY [0, -0.5, 0.8, 0, 0.5, 0]")
            print_state(node, selected)

        # ── emergency stop ──────────────────────────────────────────────
        elif cmd in "sS":
            node.emergency_stop()
            print("  !!! EMERGENCY STOP sent !!!")
            print_state(node, selected)

        # ── print state ─────────────────────────────────────────────────
        elif cmd in "pP":
            print_state(node, selected)

        # ── help ────────────────────────────────────────────────────────
        elif cmd == "?":
            print(HELP_TEXT)

        # ── quit ────────────────────────────────────────────────────────
        elif cmd in "qQ":
            print("  Goodbye!")
            break

        else:
            print(f"  Unknown command '{raw}'. Type ? for help.")


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    rclpy.init(args=sys.argv)
    node = RobotTUI()

    # Spin ROS2 in a background thread so input() doesn't block it
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    try:
        run_tui(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
