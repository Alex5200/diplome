"""
Calibration — automated joint calibration program.

Sweeps each joint from min to max position to:
1. Verify range of motion
2. Measure temperature rise
3. Detect mechanical limits / backlash

Results are printed and optionally saved to a JSON report.

Usage:
    python programs/calibration.py --port COM3 --output calibration_report.json
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from programs.base_program import BaseProgram
from app.controllers.motor_controller import MotorController

SWEEP_STEPS = 10  # positions per direction
SWEEP_SPEED = 1200  # slow for safety
SETTLE_TIME = 0.4  # seconds to wait after move
JOINT_LIMITS = [  # (min_pos, max_pos) per joint
    (400, 3695),  # J1 base
    (700, 3400),  # J2 shoulder
    (700, 3400),  # J3 elbow
    (600, 3495),  # J4 wrist
    (600, 3495),  # J5 wrist
    (0, 4095),  # J6 gripper
]


@dataclass
class JointReport:
    joint: int
    min_pos_target: int
    max_pos_target: int
    min_pos_actual: Optional[int] = None
    max_pos_actual: Optional[int] = None
    temp_start: float = 0.0
    temp_end: float = 0.0
    temp_delta: float = 0.0
    max_error: int = 0
    passed: bool = False
    notes: list[str] = field(default_factory=list)


class Calibration(BaseProgram):
    name = "Calibration"
    description = "Sweeps each joint min→max, measures position error and temperature"

    def __init__(self, controller: MotorController, output: Optional[str] = None):
        super().__init__(controller, speed=SWEEP_SPEED)
        self.output = output
        self.report: list[JointReport] = []

    def _execute(self) -> bool:
        self._log("Starting calibration sequence")
        motors = self.controller.get_connected_motors()
        if not motors:
            self._log("No motors connected")
            return False

        for i, mid in enumerate(motors[:6]):
            if self._stopped():
                break
            jr = self._calibrate_joint(i + 1, mid)
            self.report.append(jr)
            self._log(
                f"J{i + 1}: {'PASS' if jr.passed else 'FAIL'}  "
                f"err={jr.max_error}  ΔT={jr.temp_delta:.1f}°C"
            )

        # Return all joints to center
        self._go_home()

        # Save report
        if self.output:
            data = [asdict(r) for r in self.report]
            with open(self.output, "w") as f:
                json.dump(data, f, indent=2)
            self._log(f"Report saved to {self.output}")

        passed = sum(1 for r in self.report if r.passed)
        self._log(f"Calibration done: {passed}/{len(self.report)} joints passed")
        return passed == len(self.report)

    def _calibrate_joint(self, joint_idx: int, motor_id: int) -> JointReport:
        lo, hi = JOINT_LIMITS[joint_idx - 1]
        jr = JointReport(joint=joint_idx, min_pos_target=lo, max_pos_target=hi)
        self._log(f"  Calibrating J{joint_idx} (motor {motor_id}): {lo}→{hi}")

        # Read start temperature
        data = self.controller.get_motor_data(motor_id)
        if data:
            jr.temp_start = data.temperature

        # Go to center first
        self._move_joint(joint_idx, 2048)
        self._wait(0.5)

        # Sweep min → max
        errors = []
        for step in range(SWEEP_STEPS + 1):
            target = lo + int((hi - lo) * step / SWEEP_STEPS)
            self._move_joint(joint_idx, target)
            time.sleep(SETTLE_TIME)
            actual_data = self.controller.get_motor_data(motor_id)
            if actual_data:
                err = abs(actual_data.position - target)
                errors.append(err)
                if step == 0:
                    jr.min_pos_actual = actual_data.position
                if step == SWEEP_STEPS:
                    jr.max_pos_actual = actual_data.position

        # Return to center
        self._move_joint(joint_idx, 2048)
        self._wait(0.4)

        # Read end temperature
        data = self.controller.get_motor_data(motor_id)
        if data:
            jr.temp_end = data.temperature
        jr.temp_delta = jr.temp_end - jr.temp_start
        jr.max_error = max(errors) if errors else 9999

        # Pass threshold: max position error < 50 steps (~4.4°), temp rise < 10°C
        jr.passed = jr.max_error < 50 and jr.temp_delta < 10.0
        if jr.max_error >= 50:
            jr.notes.append(f"High position error: {jr.max_error} steps")
        if jr.temp_delta >= 10.0:
            jr.notes.append(f"High temperature rise: {jr.temp_delta:.1f}°C")
        return jr


def main():
    parser = argparse.ArgumentParser(description="Joint calibration")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--output", default=None, help="JSON report output path")
    args = parser.parse_args()

    ctrl = MotorController()
    if not ctrl.connect(args.port):
        print(f"Cannot connect to {args.port}")
        return
    ctrl.scan_motors()

    prog = Calibration(ctrl, output=args.output)
    prog.on_step = print
    prog.run()
    ctrl.disconnect()


if __name__ == "__main__":
    main()
