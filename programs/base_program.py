"""
BaseProgram — abstract base class for all robot task programs.

Every program defines:
    name        — human-readable name
    description — what the program does
    run()       — execute the task (blocking)
    stop()      — interrupt execution

Programs communicate with the robot exclusively through MotorController
and KinematicsService from the shared layer.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

from app.controllers.motor_controller import MotorController
from app.models.kinematics import RobotKinematics6DOF, InverseKinematics6DOF


class BaseProgram(ABC):
    name: str = "Unnamed Program"
    description: str = ""

    def __init__(self, controller: MotorController, speed: int = 2400):
        self.controller = controller
        self.speed = speed
        self._stop_event = threading.Event()
        self._kin = RobotKinematics6DOF()
        self._ik = InverseKinematics6DOF(self._kin)
        self.on_step: Optional[Callable[[str], None]] = None  # progress callback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> bool:
        """Execute the program. Returns True on success, False if stopped/failed."""
        self._stop_event.clear()
        self._log(f"Starting: {self.name}")
        try:
            return self._execute()
        except Exception as e:
            self._log(f"Error: {e}")
            return False

    def stop(self) -> None:
        """Request graceful stop."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------
    @abstractmethod
    def _execute(self) -> bool:
        """Implement the task logic here. Check self._stopped() periodically."""
        ...

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------
    def _stopped(self) -> bool:
        return self._stop_event.is_set()

    def _log(self, msg: str) -> None:
        print(f"[{self.name}] {msg}")
        if self.on_step:
            self.on_step(msg)

    def _move_joint(
        self, joint: int, position: int, speed: Optional[int] = None
    ) -> bool:
        return self.controller.move_joint(joint, position, speed or self.speed)

    def _move_all(self, positions: list[int], speed: Optional[int] = None) -> bool:
        return self.controller.move_all_joints(positions, speed or self.speed)

    def _go_to_xyz(self, x: float, y: float, z: float) -> bool:
        """Move end-effector to Cartesian point via IK. Returns False if unreachable."""
        result = self._ik.solve(x, y, z)
        if result is None:
            self._log(f"IK failed: ({x:.1f}, {y:.1f}, {z:.1f}) unreachable")
            return False
        angles, error = result
        self._log(f"IK → ({x:.1f},{y:.1f},{z:.1f}), err={error:.2f}mm")
        positions = [int((a + 180.0) / 360.0 * 4095) for a in angles]
        return self._move_all(positions)

    def _wait(self, seconds: float) -> bool:
        """Sleep while checking for stop. Returns False if stop was requested."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self._stopped():
                return False
            time.sleep(0.05)
        return True

    def _go_home(self) -> bool:
        """Move all joints to center position (2048)."""
        self._log("Going home")
        return self._move_all([2048] * 6)
