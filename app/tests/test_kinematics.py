#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for Robot Kinematics Model
"""

import unittest
import math
import sys
from pathlib import Path

# Добавляем родительскую директорию в path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from app.models.kinematics import RobotKinematics6DOF, InverseKinematics6DOF


class TestRobotKinematics6DOF(unittest.TestCase):
    """Tests for RobotKinematics6DOF class"""

    def setUp(self):
        """Set up test fixtures"""
        self.kin = RobotKinematics6DOF()

    def test_link_lengths(self):
        """Test that link lengths match specification"""
        self.assertEqual(self.kin.L0, 19.0)   # База
        self.assertEqual(self.kin.L1, 134.0)  # Плечо 1
        self.assertEqual(self.kin.L2, 95.0)   # Плечо 2
        self.assertEqual(self.kin.L3, 34.0)   # Локоть
        self.assertEqual(self.kin.L4, 35.0)   # Запястье 1
        self.assertEqual(self.kin.L5, 0.0)    # Запястье 2

    def test_total_reach(self):
        """Test maximum reach calculation"""
        expected = 19 + 134 + 95 + 34 + 35 + 0
        self.assertEqual(self.kin.get_total_reach(), expected)

    def test_set_joint_angles(self):
        """Test setting joint angles"""
        angles = [30, -45, 60, -30, 45, 0]
        self.kin.set_joint_angles(angles)
        self.assertEqual(self.kin.joint_angles, angles)

    def test_set_joint_angles_wrong_length(self):
        """Test setting wrong number of angles"""
        with self.assertRaises(ValueError):
            self.kin.set_joint_angles([30, 45, 60])  # Only 3 angles

    def test_set_joint_angle(self):
        """Test setting individual joint angle"""
        self.kin.set_joint_angle(0, 45.0)
        self.assertEqual(self.kin.joint_angles[0], 45.0)

    def test_set_joint_angle_invalid_index(self):
        """Test setting angle with invalid joint index"""
        with self.assertRaises(ValueError):
            self.kin.set_joint_angle(6, 45.0)

    def test_forward_kinematics_zero_angles(self):
        """Test forward kinematics with all zero angles"""
        positions, orientations = self.kin.forward_kinematics([0, 0, 0, 0, 0, 0])

        self.assertEqual(len(positions), 6)
        self.assertEqual(len(orientations), 6)

        # First joint should be at (0, 0, L0)
        self.assertAlmostEqual(positions[0][0], 0.0, places=2)
        self.assertAlmostEqual(positions[0][1], 0.0, places=2)
        self.assertAlmostEqual(positions[0][2], self.kin.L0, places=2)

    def test_forward_kinematics_end_effector_position(self):
        """Test end effector position calculation"""
        end_pos = self.kin.get_end_effector_position([0, 0, 0, 0, 0, 0])

        # With zero angles, robot extends along X axis
        expected_x = self.kin.L1 + self.kin.L2 + self.kin.L3 + self.kin.L4 + self.kin.L5
        self.assertAlmostEqual(end_pos[0], expected_x, places=2)
        self.assertAlmostEqual(end_pos[1], 0.0, places=2)
        self.assertAlmostEqual(end_pos[2], self.kin.L0, places=2)

    def test_all_joint_positions(self):
        """Test getting all joint positions"""
        positions = self.kin.get_all_joint_positions([0, 0, 0, 0, 0, 0])

        # Should have 7 positions (base + 6 joints)
        self.assertEqual(len(positions), 7)

        # Base should be at origin
        self.assertEqual(positions[0], (0.0, 0.0, 0.0))

    def test_link_vectors(self):
        """Test getting link vectors"""
        vectors = self.kin.get_link_vectors([0, 0, 0, 0, 0, 0])

        self.assertEqual(len(vectors), 6)

        # Sum of vector lengths should equal total reach
        total_length = sum(math.sqrt(v[0]**2 + v[1]**2 + v[2]**2) for v in vectors)
        self.assertAlmostEqual(total_length, self.kin.get_total_reach(), places=1)

    def test_workspace_bounds(self):
        """Test workspace bounds calculation"""
        bounds = self.kin.get_workspace_bounds()
        max_reach = self.kin.get_total_reach()

        x_min, x_max, y_min, y_max, z_min, z_max = bounds

        self.assertEqual(x_min, -max_reach)
        self.assertEqual(x_max, max_reach)
        self.assertEqual(y_min, -max_reach)
        self.assertEqual(y_max, max_reach)
        self.assertEqual(z_min, 0)
        self.assertGreaterEqual(z_max, max_reach)

    def test_position_to_motor_angle(self):
        """Test position to angle conversion"""
        # Center position (2048) should be 0 degrees
        angle = RobotKinematics6DOF.position_to_motor_angle(2048)
        self.assertAlmostEqual(angle, 0.0, places=1)

        # Minimum position (0) should be -180 degrees
        angle = RobotKinematics6DOF.position_to_motor_angle(0)
        self.assertAlmostEqual(angle, -180.0, places=1)

        # Maximum position (4095) should be 180 degrees
        angle = RobotKinematics6DOF.position_to_motor_angle(4095)
        self.assertAlmostEqual(angle, 180.0, places=1)

    def test_angle_to_motor_position(self):
        """Test angle to position conversion"""
        # 0 degrees should be center position (approximately 2048)
        pos = RobotKinematics6DOF.angle_to_motor_position(0.0)
        self.assertAlmostEqual(pos, 2048, delta=1)  # Allow for rounding

        # -180 degrees should be minimum
        pos = RobotKinematics6DOF.angle_to_motor_position(-180.0)
        self.assertEqual(pos, 0)

        # 180 degrees should be maximum
        pos = RobotKinematics6DOF.angle_to_motor_position(180.0)
        self.assertEqual(pos, 4095)

    def test_position_angle_roundtrip(self):
        """Test roundtrip conversion position -> angle -> position"""
        for position in [0, 1024, 2048, 3072, 4095]:
            angle = RobotKinematics6DOF.position_to_motor_angle(position)
            back_to_position = RobotKinematics6DOF.angle_to_motor_position(angle)
            self.assertEqual(position, back_to_position)

    def test_clamping_position(self):
        """Test position clamping"""
        # Below minimum
        angle = RobotKinematics6DOF.position_to_motor_angle(-100)
        self.assertAlmostEqual(angle, -180.0, places=1)

        # Above maximum
        angle = RobotKinematics6DOF.position_to_motor_angle(5000)
        self.assertAlmostEqual(angle, 180.0, places=1)

    def test_clamping_angle(self):
        """Test angle clamping"""
        # Below minimum
        pos = RobotKinematics6DOF.angle_to_motor_position(-200.0)
        self.assertEqual(pos, 0)

        # Above maximum
        pos = RobotKinematics6DOF.angle_to_motor_position(200.0)
        self.assertEqual(pos, 4095)

    def test_forward_kinematics_with_angles(self):
        """Test forward kinematics with specific angles"""
        angles = [30, -45, 60, -30, 45, 0]
        positions, orientations = self.kin.forward_kinematics(angles)

        # Verify we got valid results
        self.assertEqual(len(positions), 6)
        self.assertEqual(len(orientations), 6)

        # All positions should be within workspace
        max_reach = self.kin.get_total_reach()
        for pos in positions:
            self.assertLessEqual(abs(pos[0]), max_reach)
            self.assertLessEqual(abs(pos[1]), max_reach)
            self.assertLessEqual(abs(pos[2]), max_reach)

    def test_symmetry(self):
        """Test symmetry of kinematics"""
        # Base rotation should affect X and Y symmetrically
        angles_pos = [45, 0, 0, 0, 0, 0]
        angles_neg = [-45, 0, 0, 0, 0, 0]

        pos_pos = self.kin.get_end_effector_position(angles_pos)
        pos_neg = self.kin.get_end_effector_position(angles_neg)

        # X should be same, Y should be opposite
        self.assertAlmostEqual(pos_pos[0], pos_neg[0], places=2)
        self.assertAlmostEqual(pos_pos[1], -pos_neg[1], places=2)
        self.assertAlmostEqual(pos_pos[2], pos_neg[2], places=2)


class TestInverseKinematics6DOF(unittest.TestCase):
    """Tests for InverseKinematics6DOF class"""

    def setUp(self):
        """Set up test fixtures"""
        self.kin = RobotKinematics6DOF()
        self.ik = InverseKinematics6DOF(self.kin)

    def test_solve_reachable_position(self):
        """Test solving for a reachable position"""
        # Start with known angles and get position
        known_angles = [30, -20, 40, -10, 20, 0]
        target_pos = self.kin.get_end_effector_position(known_angles)

        # Try to solve inverse kinematics
        solution = self.ik.solve(
            target_pos[0], target_pos[1], target_pos[2],
            max_iterations=100,
            tolerance=1.0
        )

        # Solution may not be exact same angles but should reach same position
        if solution:
            reached_pos = self.kin.get_end_effector_position(solution)
            error = math.sqrt(
                (target_pos[0] - reached_pos[0])**2 +
                (target_pos[1] - reached_pos[1])**2 +
                (target_pos[2] - reached_pos[2])**2
            )
            self.assertLess(error, 5.0)  # Within 5mm

    def test_solve_origin(self):
        """Test solving for position near origin"""
        solution = self.ik.solve(
            200, 0, 100,
            max_iterations=100,
            tolerance=1.0
        )

        if solution:
            pos = self.kin.get_end_effector_position(solution)
            # Check we're close to target
            self.assertLess(abs(pos[0] - 200), 5.0)
            self.assertLess(abs(pos[1] - 0), 5.0)
            self.assertLess(abs(pos[2] - 100), 5.0)


class TestKinematicsEdgeCases(unittest.TestCase):
    """Edge case tests for kinematics"""

    def setUp(self):
        """Set up test fixtures"""
        self.kin = RobotKinematics6DOF()

    def test_gimbal_lock_detection(self):
        """Test that gimbal lock is handled"""
        # Angles that might cause gimbal lock
        angles = [0, 90, 0, 0, 90, 0]

        positions, orientations = self.kin.forward_kinematics(angles)

        # Should still produce valid results
        self.assertEqual(len(positions), 6)
        for pos in positions:
            self.assertIsInstance(pos[0], float)
            self.assertIsInstance(pos[1], float)
            self.assertIsInstance(pos[2], float)

    def test_extreme_angles(self):
        """Test with extreme joint angles"""
        extreme_angles = [180, -180, 180, -180, 180, -180]

        positions, orientations = self.kin.forward_kinematics(extreme_angles)

        # Should produce valid results
        self.assertEqual(len(positions), 6)
        self.assertEqual(len(orientations), 6)

    def test_all_positive_angles(self):
        """Test with all positive angles"""
        angles = [90, 90, 90, 90, 90, 90]
        positions, _ = self.kin.forward_kinematics(angles)

        max_reach = self.kin.get_total_reach()
        for pos in positions:
            self.assertLessEqual(abs(pos[0]), max_reach)
            self.assertLessEqual(abs(pos[1]), max_reach)
            self.assertLessEqual(abs(pos[2]), max_reach)

    def test_all_negative_angles(self):
        """Test with all negative angles"""
        angles = [-90, -90, -90, -90, -90, -90]
        positions, _ = self.kin.forward_kinematics(angles)

        max_reach = self.kin.get_total_reach()
        for pos in positions:
            self.assertLessEqual(abs(pos[0]), max_reach)
            self.assertLessEqual(abs(pos[1]), max_reach)
            self.assertLessEqual(abs(pos[2]), max_reach)


if __name__ == '__main__':
    unittest.main()
