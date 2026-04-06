"""
WaveDemo — demonstration wave motion program.

Performs a smooth sinusoidal wave on joints 2 and 3 (shoulder) while
rotating joint 1 (base) back and forth. Useful as a demo/attract sequence.

Usage:
    python programs/wave_demo.py --port COM3 --cycles 3
"""

from __future__ import annotations

import math
import time
import argparse

from programs.base_program import BaseProgram
from app.controllers.motor_controller import MotorController


class WaveDemo(BaseProgram):
    name = "Wave Demo"
    description = (
        "Sinusoidal wave motion on shoulder joints with base rotation — demo/attract sequence"
    )

    def __init__(self, controller: MotorController, cycles: int = 3, speed: int = 1500):
        super().__init__(controller, speed)
        self.cycles = cycles

    def _execute(self) -> bool:
        self._log(f"Wave demo: {self.cycles} cycles")
        if not self._go_home():
            return False
        if not self._wait(0.8):
            return False

        steps = 40
        for cycle in range(self.cycles):
            self._log(f"Cycle {cycle + 1}/{self.cycles}")
            for step in range(steps):
                if self._stopped():
                    return False

                t = (step / steps) * 2 * math.pi

                # Base: slow rotation ±45°
                base_angle = 45.0 * math.sin(t * 0.5)
                base_pos = int((base_angle + 180.0) / 360.0 * 4095)

                # Shoulder wave: ±30°
                shoulder_angle = 30.0 * math.sin(t)
                shoulder_pos = int((shoulder_angle + 180.0) / 360.0 * 4095)

                # Elbow counter-wave: ±20°
                elbow_angle = -20.0 * math.sin(t)
                elbow_pos = int((elbow_angle + 180.0) / 360.0 * 4095)

                positions = [
                    base_pos,  # J1 base
                    shoulder_pos,  # J2 shoulder
                    elbow_pos,  # J3 elbow
                    2048,  # J4 center
                    2048,  # J5 center
                    2048,  # J6 center
                ]
                self._move_all(positions)
                time.sleep(0.06)

        self._go_home()
        self._log("Wave demo complete")
        return True


def main():
    parser = argparse.ArgumentParser(description="Wave demo program")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--speed", type=int, default=1500)
    args = parser.parse_args()

    ctrl = MotorController()
    if not ctrl.connect(args.port):
        print(f"Cannot connect to {args.port}")
        return
    ctrl.scan_motors()

    prog = WaveDemo(ctrl, cycles=args.cycles, speed=args.speed)
    prog.on_step = print
    prog.run()
    ctrl.disconnect()


if __name__ == "__main__":
    main()
