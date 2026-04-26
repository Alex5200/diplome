"""
DrawSquare — draws a square trajectory in the XY plane via IK.

The end-effector traces a square of configurable side length at a fixed Z height.
Useful for validating IK accuracy and servo repeatability.

Usage:
    python programs/draw_square.py --port COM3 --side 80 --z 80 --reps 2
"""

from __future__ import annotations

import argparse

from app.controllers.motor_controller import MotorController
from programs.base_program import BaseProgram


class DrawSquare(BaseProgram):
    name = "Draw Square"
    description = "Traces a square trajectory in XY plane using inverse kinematics"

    def __init__(
        self,
        controller: MotorController,
        side_mm: float = 80.0,
        center_x: float = 180.0,
        center_y: float = 0.0,
        z_mm: float = 80.0,
        reps: int = 2,
        steps_per_side: int = 20,
        speed: int = 1800,
    ):
        super().__init__(controller, speed)
        self.side = side_mm
        self.cx = center_x
        self.cy = center_y
        self.z = z_mm
        self.reps = reps
        self.steps_per_side = steps_per_side

    def _execute(self) -> bool:
        h = self.side / 2.0
        corners = [
            (self.cx + h, self.cy + h),
            (self.cx - h, self.cy + h),
            (self.cx - h, self.cy - h),
            (self.cx + h, self.cy - h),
        ]
        side_names = ["top", "left", "bottom", "right"]

        self._log(f"Drawing {self.side}mm square at Z={self.z}mm, center=({self.cx},{self.cy})")

        # Move to start corner
        sx, sy = corners[0]
        if not self._go_to_xyz(sx, sy, self.z):
            return False
        if not self._wait(0.5):
            return False

        for rep in range(self.reps):
            self._log(f"Rep {rep + 1}/{self.reps}")
            for side_idx in range(4):
                if self._stopped():
                    return False
                x0, y0 = corners[side_idx]
                x1, y1 = corners[(side_idx + 1) % 4]
                self._log(
                    f"  Side {side_names[side_idx]}: ({x0:.0f},{y0:.0f}) → ({x1:.0f},{y1:.0f})"
                )
                for step in range(self.steps_per_side + 1):
                    if self._stopped():
                        return False
                    t = step / self.steps_per_side
                    xi = x0 + (x1 - x0) * t
                    yi = y0 + (y1 - y0) * t
                    if not self._go_to_xyz(xi, yi, self.z):
                        self._log(f"  IK failed at ({xi:.1f},{yi:.1f},{self.z})")
                        continue
                    self._wait(0.02)

        self._go_home()
        self._log("Square drawing complete")
        return True


def main():
    parser = argparse.ArgumentParser(description="Draw square trajectory")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--side", type=float, default=80.0, help="Square side length (mm)")
    parser.add_argument("--z", type=float, default=80.0, help="Z height (mm)")
    parser.add_argument("--cx", type=float, default=180.0, help="Center X (mm)")
    parser.add_argument("--cy", type=float, default=0.0, help="Center Y (mm)")
    parser.add_argument("--reps", type=int, default=2, help="Repetitions")
    parser.add_argument("--speed", type=int, default=1800)
    args = parser.parse_args()

    ctrl = MotorController()
    if not ctrl.connect(args.port):
        print(f"Cannot connect to {args.port}")
        return
    ctrl.scan_motors()

    prog = DrawSquare(
        ctrl,
        side_mm=args.side,
        center_x=args.cx,
        center_y=args.cy,
        z_mm=args.z,
        reps=args.reps,
        speed=args.speed,
    )
    prog.on_step = print
    prog.run()
    ctrl.disconnect()


if __name__ == "__main__":
    main()
