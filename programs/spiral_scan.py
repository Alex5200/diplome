"""
SpiralScan — scans a spiral trajectory in the XY plane.

Useful for workspace mapping, surface scanning, or camera coverage tasks.
The spiral expands from the center outward at a fixed Z height.

Usage:
    python programs/spiral_scan.py --port COM3 --radius 100 --turns 3 --z 80
"""

from __future__ import annotations

import argparse
import math

from programs.base_program import BaseProgram
from app.controllers.motor_controller import MotorController


class SpiralScan(BaseProgram):
    name = "Spiral Scan"
    description = "Traces an outward spiral trajectory for workspace mapping or surface scanning"

    def __init__(
        self,
        controller: MotorController,
        max_radius_mm: float = 100.0,
        turns: int = 3,
        center_x: float = 180.0,
        center_y: float = 0.0,
        z_mm: float = 80.0,
        points_per_turn: int = 32,
        speed: int = 1500,
        on_scan_point: callable = None,
    ):
        super().__init__(controller, speed)
        self.max_radius = max_radius_mm
        self.turns = turns
        self.cx = center_x
        self.cy = center_y
        self.z = z_mm
        self.ppt = points_per_turn
        self.on_scan_point = on_scan_point  # callback(x, y, z) at each point

    def _execute(self) -> bool:
        total_points = self.turns * self.ppt
        self._log(f"Spiral scan: r={self.max_radius}mm, {self.turns} turns, {total_points} points")

        # Move to center first
        if not self._go_to_xyz(self.cx, self.cy, self.z):
            return False
        if not self._wait(0.5):
            return False

        scanned = 0
        for i in range(total_points + 1):
            if self._stopped():
                return False
            t = i / total_points
            angle = t * self.turns * 2 * math.pi
            radius = t * self.max_radius
            x = self.cx + radius * math.cos(angle)
            y = self.cy + radius * math.sin(angle)
            ok = self._go_to_xyz(x, y, self.z)
            if ok:
                scanned += 1
                if self.on_scan_point:
                    self.on_scan_point(x, y, self.z)
                self._wait(0.05)
            else:
                self._log(f"  Point ({x:.1f},{y:.1f}) skipped — out of reach")

        self._go_home()
        self._log(f"Spiral scan complete: {scanned}/{total_points + 1} points reached")
        return True


def main():
    parser = argparse.ArgumentParser(description="Spiral scan program")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--radius", type=float, default=100.0)
    parser.add_argument("--turns", type=int, default=3)
    parser.add_argument("--z", type=float, default=80.0)
    parser.add_argument("--cx", type=float, default=180.0)
    parser.add_argument("--cy", type=float, default=0.0)
    parser.add_argument("--speed", type=int, default=1500)
    args = parser.parse_args()

    ctrl = MotorController()
    if not ctrl.connect(args.port):
        print(f"Cannot connect to {args.port}")
        return
    ctrl.scan_motors()

    prog = SpiralScan(
        ctrl,
        max_radius_mm=args.radius,
        turns=args.turns,
        center_x=args.cx,
        center_y=args.cy,
        z_mm=args.z,
        speed=args.speed,
        on_scan_point=lambda x, y, z: print(f"  scan ({x:.1f},{y:.1f},{z:.1f})"),
    )
    prog.on_step = print
    prog.run()
    ctrl.disconnect()


if __name__ == "__main__":
    main()
