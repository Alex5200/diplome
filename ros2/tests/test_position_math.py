#!/usr/bin/env python3
"""
Tests for position/radian conversion logic in RobotHWInterface.

Covers: boundary values, clamping, round-trips, symmetry.
"""

import math
import os
import sys
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robot_control"))
sys.path.insert(0, _ROOT)  # diplome/ — so 'app' package is importable

from hardware_interface import RobotHWInterface


class TestPositionToRad(unittest.TestCase):
    """_position_to_rad: motor position (0-4095) → radians."""

    def test_center_position(self):
        """Position 2048 should be close to 0 rad (center)."""
        rad = RobotHWInterface._position_to_rad(2048)
        # (2048/4095)*360 - 180 ≈ 0.0176°, acceptable tolerance
        self.assertAlmostEqual(rad, 0.0, delta=0.002)

    def test_min_position(self):
        """Position 0 → -π rad."""
        rad = RobotHWInterface._position_to_rad(0)
        self.assertAlmostEqual(rad, -math.pi, places=2)

    def test_max_position(self):
        """Position 4095 → +π rad."""
        rad = RobotHWInterface._position_to_rad(4095)
        self.assertAlmostEqual(rad, math.pi, places=2)

    def test_quarter_position(self):
        """Position 1024 → roughly -π/2."""
        rad = RobotHWInterface._position_to_rad(1024)
        self.assertAlmostEqual(rad, -math.pi / 2, delta=0.05)

    def test_three_quarter_position(self):
        """Position 3072 → roughly +π/2."""
        rad = RobotHWInterface._position_to_rad(3072)
        self.assertAlmostEqual(rad, math.pi / 2, delta=0.05)

    def test_output_range(self):
        """All valid positions must map to [-π, π]."""
        for pos in range(0, 4096, 64):
            rad = RobotHWInterface._position_to_rad(pos)
            self.assertGreaterEqual(rad, -math.pi - 0.001)
            self.assertLessEqual(rad, math.pi + 0.001)


class TestRadToPosition(unittest.TestCase):
    """_rad_to_position: radians → motor position (0-4095)."""

    def test_zero_rad(self):
        """0 rad → center position (~2048)."""
        pos = RobotHWInterface._rad_to_position(0.0)
        self.assertAlmostEqual(pos, 2048, delta=2)

    def test_plus_pi(self):
        """π rad → max position 4095."""
        pos = RobotHWInterface._rad_to_position(math.pi)
        self.assertEqual(pos, 4095)

    def test_minus_pi(self):
        """-π rad → min position 0."""
        pos = RobotHWInterface._rad_to_position(-math.pi)
        self.assertEqual(pos, 0)

    def test_clamp_above_pi(self):
        """Values > π must clamp to 4095."""
        pos = RobotHWInterface._rad_to_position(math.pi + 1.0)
        self.assertEqual(pos, 4095)

    def test_clamp_below_minus_pi(self):
        """Values < -π must clamp to 0."""
        pos = RobotHWInterface._rad_to_position(-math.pi - 1.0)
        self.assertEqual(pos, 0)

    def test_output_integer(self):
        """Result must always be an int."""
        for val in [-math.pi, -1.0, 0.0, 1.0, math.pi]:
            result = RobotHWInterface._rad_to_position(val)
            self.assertIsInstance(result, int)

    def test_output_in_range(self):
        """Result must be in [0, 4095]."""
        for val in [-math.pi, -1.57, 0.0, 1.57, math.pi]:
            result = RobotHWInterface._rad_to_position(val)
            self.assertGreaterEqual(result, 0)
            self.assertLessEqual(result, 4095)


class TestRoundTrip(unittest.TestCase):
    """Round-trip: position → rad → position must recover original ±2 ticks."""

    SAMPLE_POSITIONS = [0, 512, 1024, 1536, 2048, 2560, 3072, 3584, 4095]

    def test_position_roundtrip(self):
        for pos in self.SAMPLE_POSITIONS:
            rad = RobotHWInterface._position_to_rad(pos)
            back = RobotHWInterface._rad_to_position(rad)
            self.assertAlmostEqual(pos, back, delta=2, msg=f"Round-trip failed for position {pos}")

    def test_rad_roundtrip(self):
        """rad → position → rad must recover within 0.002 rad."""
        test_rads = [-math.pi, -math.pi / 2, -1.0, 0.0, 1.0, math.pi / 2, math.pi]
        for rad in test_rads:
            pos = RobotHWInterface._rad_to_position(rad)
            back = RobotHWInterface._position_to_rad(pos)
            self.assertAlmostEqual(rad, back, delta=0.002, msg=f"Round-trip failed for {rad:.3f} rad")

    def test_symmetry(self):
        """pos_to_rad(x) ≈ -pos_to_rad(4095 - x) (antisymmetry around center)."""
        for pos in [0, 256, 1024, 2048]:
            mirror = 4095 - pos
            rad_a = RobotHWInterface._position_to_rad(pos)
            rad_b = RobotHWInterface._position_to_rad(mirror)
            self.assertAlmostEqual(rad_a, -rad_b, delta=0.005, msg=f"Symmetry failed at pos={pos}")


if __name__ == "__main__":
    unittest.main()
