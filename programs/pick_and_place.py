"""
PickAndPlace — pick-and-place task program.

Moves the end-effector between a pick point and a place point via IK,
simulating a grab-move-release cycle. Gripper open/close is sent on J6.

Typical usage:
    python programs/pick_and_place.py --port COM3 --cycles 5

Coordinate system (mm):
    X — forward from robot base
    Y — left/right
    Z — up/down (Z=0 is base plane)
"""

from __future__ import annotations

import argparse

from programs.base_program import BaseProgram
from app.controllers.motor_controller import MotorController

# Gripper positions (J6)
GRIPPER_OPEN = 1200  # ~ -90° relative
GRIPPER_CLOSED = 2800  # ~ +55° relative
GRIPPER_SPEED = 3000

# Safe transit height above pick/place points
TRANSIT_Z_OFFSET = 40.0  # mm


class PickAndPlace(BaseProgram):
    name = "Pick and Place"
    description = "Picks an object at pick_point and places it at place_point using IK"

    def __init__(
        self,
        controller: MotorController,
        pick_point: tuple[float, float, float] = (180.0, 60.0, 30.0),
        place_point: tuple[float, float, float] = (180.0, -60.0, 30.0),
        cycles: int = 3,
        speed: int = 2000,
    ):
        super().__init__(controller, speed)
        self.pick_point = pick_point
        self.place_point = place_point
        self.cycles = cycles

    # ------------------------------------------------------------------
    def _execute(self) -> bool:
        self._log(f"Pick-and-place: {self.cycles} cycles")
        self._log(f"  Pick:  {self.pick_point}")
        self._log(f"  Place: {self.place_point}")

        if not self._go_home():
            return False
        self._open_gripper()
        if not self._wait(0.5):
            return False

        for i in range(self.cycles):
            self._log(f"Cycle {i + 1}/{self.cycles}")
            if not self._pick():
                return False
            if not self._place():
                return False

        if not self._go_home():
            return False
        self._log("Pick-and-place complete")
        return True

    def _pick(self) -> bool:
        px, py, pz = self.pick_point
        # Approach from above
        if not self._go_to_xyz(px, py, pz + TRANSIT_Z_OFFSET):
            return False
        if not self._wait(0.4):
            return False
        # Descend to pick height
        if not self._go_to_xyz(px, py, pz):
            return False
        if not self._wait(0.3):
            return False
        # Grip
        self._close_gripper()
        if not self._wait(0.5):
            return False
        # Lift
        if not self._go_to_xyz(px, py, pz + TRANSIT_Z_OFFSET):
            return False
        if not self._wait(0.3):
            return False
        return True

    def _place(self) -> bool:
        lx, ly, lz = self.place_point
        # Move over place point
        if not self._go_to_xyz(lx, ly, lz + TRANSIT_Z_OFFSET):
            return False
        if not self._wait(0.4):
            return False
        # Descend
        if not self._go_to_xyz(lx, ly, lz):
            return False
        if not self._wait(0.3):
            return False
        # Release
        self._open_gripper()
        if not self._wait(0.5):
            return False
        # Lift
        if not self._go_to_xyz(lx, ly, lz + TRANSIT_Z_OFFSET):
            return False
        if not self._wait(0.3):
            return False
        return True

    def _open_gripper(self):
        self._log("Gripper open")
        self.controller.move_joint(6, GRIPPER_OPEN, GRIPPER_SPEED)

    def _close_gripper(self):
        self._log("Gripper close")
        self.controller.move_joint(6, GRIPPER_CLOSED, GRIPPER_SPEED)


def main():
    parser = argparse.ArgumentParser(description="Pick and place program")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--speed", type=int, default=2000)
    args = parser.parse_args()

    ctrl = MotorController()
    if not ctrl.connect(args.port):
        print(f"Cannot connect to {args.port}")
        return
    ctrl.scan_motors()

    prog = PickAndPlace(ctrl, cycles=args.cycles, speed=args.speed)
    prog.on_step = print
    prog.run()
    ctrl.disconnect()


if __name__ == "__main__":
    main()
