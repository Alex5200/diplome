#!/usr/bin/env python3
"""
Extended unit tests for RobotHWInterface.

Tests beyond the basic test_hw_interface.py:
  - Singleton reset/reinit cycle
  - write_joint_positions validation (wrong count)
  - get_all_motor_data without initialization
  - emergency_stop without connection
  - JOINT_NAMES match URDF definition
"""

import os
import sys
import threading
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robot_control"))
sys.path.insert(0, _ROOT)

from hardware_interface import RobotHWInterface, JointState

# URDF-defined joint names (joint_0..joint_5)
EXPECTED_JOINT_NAMES = ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]


class TestHWInterfaceOffline(unittest.TestCase):
    """Tests that must pass without any hardware connected."""

    def setUp(self):
        RobotHWInterface._instance = None

    def tearDown(self):
        inst = RobotHWInterface._instance
        if inst:
            inst.shutdown()
        RobotHWInterface._instance = None

    def test_get_all_motor_data_uninitialized(self):
        """get_all_motor_data returns empty dict when not initialized."""
        hw = RobotHWInterface.get_instance()
        result = hw.get_all_motor_data()
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_get_motor_data_uninitialized(self):
        """get_motor_data returns None when not initialized."""
        hw = RobotHWInterface.get_instance()
        result = hw.get_motor_data(1)
        self.assertIsNone(result)

    def test_is_connected_uninitialized(self):
        """is_connected returns False before initialization."""
        hw = RobotHWInterface.get_instance()
        self.assertFalse(hw.is_connected())

    def test_emergency_stop_no_crash_when_uninitialized(self):
        """emergency_stop must not raise when not initialized."""
        hw = RobotHWInterface.get_instance()
        try:
            hw.emergency_stop()
        except Exception as e:
            self.fail(f"emergency_stop raised unexpectedly: {e}")

    def test_shutdown_no_crash_when_uninitialized(self):
        """shutdown must not raise when not initialized."""
        hw = RobotHWInterface.get_instance()
        try:
            hw.shutdown()
        except Exception as e:
            self.fail(f"shutdown raised unexpectedly: {e}")

    def test_write_joint_positions_returns_false_when_unconnected(self):
        """write_joint_positions returns False when not connected."""
        hw = RobotHWInterface.get_instance()
        result = hw.write_joint_positions([0.0] * 6)
        self.assertFalse(result)

    def test_write_joint_positions_wrong_count(self):
        """write_joint_positions returns False for wrong position count."""
        hw = RobotHWInterface.get_instance()
        hw._initialize_internal()
        # Too few
        self.assertFalse(hw.write_joint_positions([0.0] * 3))
        # Too many
        self.assertFalse(hw.write_joint_positions([0.0] * 9))
        # Empty
        self.assertFalse(hw.write_joint_positions([]))

    def test_read_joint_states_returns_six(self):
        """read_joint_states always returns exactly 6 states."""
        hw = RobotHWInterface.get_instance()
        states = hw.read_joint_states()
        self.assertEqual(len(states), 6)

    def test_read_joint_states_all_are_joint_state(self):
        """Every element returned is a JointState instance."""
        hw = RobotHWInterface.get_instance()
        states = hw.read_joint_states()
        for s in states:
            self.assertIsInstance(s, JointState)

    def test_read_joint_states_offline_defaults(self):
        """Offline joint states have zero position and default raw value."""
        hw = RobotHWInterface.get_instance()
        for state in hw.read_joint_states():
            self.assertEqual(state.position_rad, 0.0)
            self.assertEqual(state.velocity_rad_s, 0.0)
            self.assertEqual(state.effort, 0.0)
            self.assertEqual(state.position_raw, 2048)


class TestSingletonLifecycle(unittest.TestCase):
    """Singleton creation, reset, and re-init."""

    def setUp(self):
        RobotHWInterface._instance = None

    def tearDown(self):
        inst = RobotHWInterface._instance
        if inst:
            inst.shutdown()
        RobotHWInterface._instance = None

    def test_singleton_identity(self):
        """Multiple get_instance() calls return the identical object."""
        hw1 = RobotHWInterface.get_instance()
        hw2 = RobotHWInterface.get_instance()
        hw3 = RobotHWInterface()
        self.assertIs(hw1, hw2)
        self.assertIs(hw1, hw3)

    def test_shutdown_clears_instance(self):
        """After shutdown, a new instance can be created."""
        hw1 = RobotHWInterface.get_instance()
        hw1._initialize_internal()
        hw1.shutdown()
        # Instance must be cleared
        self.assertIsNone(RobotHWInterface._instance)
        # New instance should work
        hw2 = RobotHWInterface.get_instance()
        self.assertIsNotNone(hw2)

    def test_initialize_internal_idempotent(self):
        """Calling _initialize_internal twice does not double-init."""
        hw = RobotHWInterface.get_instance()
        hw._initialize_internal()
        ctrl_ref = hw._ctrl  # capture first init
        hw._initialize_internal()
        self.assertIs(hw._ctrl, ctrl_ref)  # same controller object

    def test_concurrent_singleton_creation(self):
        """Concurrent creation must yield a single instance."""
        instances = []
        lock = threading.Lock()

        def get():
            inst = RobotHWInterface.get_instance()
            with lock:
                instances.append(id(inst))

        threads = [threading.Thread(target=get) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(set(instances)), 1, "Multiple singleton instances created")


class TestJointNameConsistency(unittest.TestCase):
    """Ensure JOINT_NAMES in all nodes match the URDF joint names."""

    def test_robot_node_joint_names(self):
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "robot_node",
            str(pathlib.Path(__file__).parent.parent / "robot_control" / "robot_node.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        # Avoid executing main; just load constants
        # We only need JOINT_NAMES, so do a restricted exec
        src = pathlib.Path(__file__).parent.parent / "robot_control" / "robot_node.py"
        namespace: dict = {}
        for line in src.read_text().splitlines():
            if line.startswith("JOINT_NAMES"):
                exec(line, namespace)
                break
        self.assertEqual(namespace["JOINT_NAMES"], EXPECTED_JOINT_NAMES)

    def test_robot_node_v2_joint_names(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "robot_control" / "robot_node_v2.py"
        namespace: dict = {}
        for line in src.read_text().splitlines():
            if line.startswith("JOINT_NAMES"):
                exec(line, namespace)
                break
        self.assertEqual(namespace["JOINT_NAMES"], EXPECTED_JOINT_NAMES)

    def test_bridge_joint_names(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "robot_control" / "ros2_control_bridge.py"
        namespace: dict = {}
        for line in src.read_text().splitlines():
            if line.startswith("JOINT_NAMES"):
                exec(line, namespace)
                break
        self.assertEqual(namespace["JOINT_NAMES"], EXPECTED_JOINT_NAMES)


if __name__ == "__main__":
    unittest.main()
