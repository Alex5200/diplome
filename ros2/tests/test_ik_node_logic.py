#!/usr/bin/env python3
"""
Tests for IKServiceNode JSON parsing logic.

We test _on_request behaviour by mocking the publisher and IK solver,
without needing a live ROS2 context (rclpy is mocked).
"""

import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ── Stub rclpy so the module loads without a ROS installation ──────────────
rclpy_stub = types.ModuleType("rclpy")
rclpy_stub.node = types.ModuleType("rclpy.node")
rclpy_stub.node.Node = object  # base class stub
rclpy_stub.init = lambda args=None: None
rclpy_stub.spin = lambda node: None
rclpy_stub.shutdown = lambda: None
sys.modules.setdefault("rclpy", rclpy_stub)
sys.modules.setdefault("rclpy.node", rclpy_stub.node)

std_msgs_stub = types.ModuleType("std_msgs")
std_msgs_msg = types.ModuleType("std_msgs.msg")


class _String:
    def __init__(self, data=""):
        self.data = data


std_msgs_msg.String = _String
std_msgs_stub.msg = std_msgs_msg
sys.modules.setdefault("std_msgs", std_msgs_stub)
sys.modules.setdefault("std_msgs.msg", std_msgs_msg)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robot_control"))

# ── Stub the kinematics dependency ─────────────────────────────────────────
app_stub = types.ModuleType("app")
app_models = types.ModuleType("app.models")
app_kin = types.ModuleType("app.models.kinematics")


class _FakeKinematics:
    pass


class _FakeIK:
    def __init__(self, kin):
        pass

    def solve(self, x, y, z):
        # Default: return a plausible result
        return ([10.0, -20.0, 30.0, 0.0, 0.0, 0.0], 0.5)


app_kin.RobotKinematics6DOF = _FakeKinematics
app_kin.InverseKinematics6DOF = _FakeIK
app_models.kinematics = app_kin
app_stub.models = app_models
sys.modules.setdefault("app", app_stub)
sys.modules.setdefault("app.models", app_models)
sys.modules.setdefault("app.models.kinematics", app_kin)

from ik_service_node import IKServiceNode  # noqa: E402 — must come after stubs


def _make_node() -> IKServiceNode:
    """Instantiate IKServiceNode with all ROS calls mocked."""
    node = IKServiceNode.__new__(IKServiceNode)
    node.get_logger = MagicMock(return_value=MagicMock())
    node._pub = MagicMock()
    node._kin = _FakeKinematics()
    node._ik = _FakeIK(node._kin)
    return node


class TestIKNodeParsing(unittest.TestCase):
    """Test _on_request JSON parsing without a live ROS context."""

    def _last_published(self, node) -> dict:
        """Extract the last JSON dict published by the node."""
        call_args = node._pub.publish.call_args
        self.assertIsNotNone(call_args, "publish was never called")
        msg = call_args[0][0]
        return json.loads(msg.data)

    def test_valid_request_success(self):
        """Valid JSON with x/y/z returns success=True and 6 angles."""
        node = _make_node()
        msg = _String(data='{"x": 150, "y": 0, "z": 100}')
        node._on_request(msg)
        result = self._last_published(node)
        self.assertTrue(result["success"])
        self.assertIn("angles_deg", result)
        self.assertEqual(len(result["angles_deg"]), 6)
        self.assertIn("error_mm", result)

    def test_missing_key_returns_error(self):
        """Missing 'z' key must return success=False with an error message."""
        node = _make_node()
        msg = _String(data='{"x": 100, "y": 50}')
        node._on_request(msg)
        result = self._last_published(node)
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_invalid_json_returns_error(self):
        """Malformed JSON must return success=False."""
        node = _make_node()
        msg = _String(data="not_valid_json{{")
        node._on_request(msg)
        result = self._last_published(node)
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_non_numeric_value_returns_error(self):
        """Non-numeric coordinate value must return success=False."""
        node = _make_node()
        msg = _String(data='{"x": "abc", "y": 0, "z": 100}')
        node._on_request(msg)
        result = self._last_published(node)
        self.assertFalse(result["success"])

    def test_empty_json_returns_error(self):
        """Empty JSON object must return success=False."""
        node = _make_node()
        msg = _String(data="{}")
        node._on_request(msg)
        result = self._last_published(node)
        self.assertFalse(result["success"])

    def test_unreachable_position(self):
        """When IK solver returns None, response has success=False and error='unreachable'."""
        node = _make_node()
        node._ik.solve = lambda x, y, z: None
        msg = _String(data='{"x": 9999, "y": 9999, "z": 9999}')
        node._on_request(msg)
        result = self._last_published(node)
        self.assertFalse(result["success"])
        self.assertEqual(result.get("error"), "unreachable")

    def test_angles_rounded_to_4_places(self):
        """Returned angles must be rounded to 4 decimal places."""
        node = _make_node()
        node._ik.solve = lambda x, y, z: ([1.123456789, 2.987654321, 0.0, 0.0, 0.0, 0.0], 0.123456)
        msg = _String(data='{"x": 10, "y": 0, "z": 50}')
        node._on_request(msg)
        result = self._last_published(node)
        self.assertTrue(result["success"])
        for angle in result["angles_deg"]:
            # Should have at most 4 decimal places
            self.assertEqual(round(angle, 4), angle)

    def test_extra_keys_ignored(self):
        """Extra JSON keys must not cause errors."""
        node = _make_node()
        msg = _String(data='{"x": 150, "y": 0, "z": 100, "extra": "ignored"}')
        node._on_request(msg)
        result = self._last_published(node)
        self.assertTrue(result["success"])

    def test_publish_called_exactly_once_per_request(self):
        """Each request must trigger exactly one publish."""
        node = _make_node()
        msg = _String(data='{"x": 100, "y": 0, "z": 80}')
        node._on_request(msg)
        self.assertEqual(node._pub.publish.call_count, 1)

    def test_float_coordinates_accepted(self):
        """Float-valued coordinates must be parsed without error."""
        node = _make_node()
        msg = _String(data='{"x": 123.456, "y": -45.6, "z": 78.9}')
        node._on_request(msg)
        result = self._last_published(node)
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
