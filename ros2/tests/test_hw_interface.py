#!/usr/bin/env python3
"""
Unit tests for RobotHWInterface.

Tests:
1. Singleton pattern
2. Thread safety
3. Offline mode
4. Position conversions
"""

import unittest
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robot_control"))

from hardware_interface import RobotHWInterface, JointState


class TestRobotHWInterface(unittest.TestCase):
    """Test suite for RobotHWInterface."""

    def setUp(self):
        """Reset singleton before each test."""
        # Clear singleton
        RobotHWInterface._instance = None

    def tearDown(self):
        """Cleanup after each test."""
        if RobotHWInterface._instance:
            RobotHWInterface._instance.shutdown()

    def test_singleton_pattern(self):
        """Test that multiple instantiations return same object."""
        hw1 = RobotHWInterface.get_instance()
        hw2 = RobotHWInterface.get_instance()

        self.assertIs(hw1, hw2)
        self.assertEqual(id(hw1), id(hw2))

    def test_singleton_thread_safety(self):
        """Test singleton creation is thread-safe."""
        instances = []
        lock = threading.Lock()

        def create_instance():
            hw = RobotHWInterface.get_instance()
            with lock:
                instances.append(hw)

        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be same instance
        self.assertEqual(len(set(id(i) for i in instances)), 1)

    def test_offline_mode(self):
        """Test system works without motors connected."""
        hw = RobotHWInterface.get_instance()

        # Not initialized - should return default states
        states = hw.read_joint_states()
        self.assertEqual(len(states), 6)

        for state in states:
            self.assertIsInstance(state, JointState)
            self.assertEqual(state.position_rad, 0.0)
            self.assertEqual(state.position_raw, 2048)

    def test_position_conversion(self):
        """Test position <-> radian conversions."""
        # Test center position
        center_rad = RobotHWInterface._position_to_rad(2048)
        self.assertAlmostEqual(center_rad, 0.0, places=2)

        # Test min position
        min_rad = RobotHWInterface._position_to_rad(0)
        self.assertAlmostEqual(min_rad, -3.14159, places=2)

        # Test max position
        max_rad = RobotHWInterface._position_to_rad(4095)
        self.assertAlmostEqual(max_rad, 3.14159, places=2)

        # Test round-trip
        test_positions = [0, 1024, 2048, 3072, 4095]
        for pos in test_positions:
            rad = RobotHWInterface._position_to_rad(pos)
            back = RobotHWInterface._rad_to_position(rad)
            self.assertAlmostEqual(pos, back, delta=2)

    def test_cache_freshness(self):
        """Test cache freshness detection."""
        from hardware_interface import MotorCache

        cache = MotorCache()

        # Fresh cache (just created)
        self.assertTrue(cache.is_fresh)

        # Wait to make stale
        time.sleep(0.6)
        cache.timestamp = time.time() - 0.6  # Force old timestamp
        self.assertFalse(cache.is_fresh)

    def test_is_initialized(self):
        """Test initialization state tracking."""
        hw = RobotHWInterface.get_instance()

        # Not initialized yet
        self.assertFalse(hw.is_initialized())

        # Initialize (will fail without motors, but sets flag)
        hw._initialize_internal()
        self.assertTrue(hw.is_initialized())


class TestThreadSafety(unittest.TestCase):
    """Test thread safety of hardware interface."""

    def setUp(self):
        RobotHWInterface._instance = None

    def tearDown(self):
        if RobotHWInterface._instance:
            RobotHWInterface._instance.shutdown()

    def test_concurrent_reads(self):
        """Test concurrent reads don't corrupt data."""
        hw = RobotHWInterface.get_instance()
        hw._initialize_internal()

        results = []
        lock = threading.Lock()

        def reader():
            for _ in range(100):
                states = hw.read_joint_states()
                with lock:
                    results.append(len(states))
                time.sleep(0.001)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should return 6 states
        self.assertEqual(len(results), 500)
        self.assertTrue(all(r == 6 for r in results))


if __name__ == "__main__":
    unittest.main()
