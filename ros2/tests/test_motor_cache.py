#!/usr/bin/env python3
"""
Tests for MotorCache freshness logic.
"""

import os
import sys
import time
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robot_control"))
sys.path.insert(0, _ROOT)

from hardware_interface import MotorCache


class TestMotorCache(unittest.TestCase):
    """MotorCache freshness and state tracking."""

    def test_fresh_on_creation(self):
        """Newly created cache is fresh with default 500ms threshold."""
        cache = MotorCache()
        self.assertTrue(cache.is_fresh())

    def test_stale_after_timeout(self):
        """Cache is stale when timestamp is older than threshold."""
        cache = MotorCache()
        cache.timestamp = time.time() - 0.6  # 600ms ago
        self.assertFalse(cache.is_fresh())

    def test_custom_threshold_fresh(self):
        """Cache is fresh under a lenient threshold."""
        cache = MotorCache()
        cache.timestamp = time.time() - 0.4  # 400ms ago
        self.assertTrue(cache.is_fresh(max_age_ms=500.0))

    def test_custom_threshold_stale(self):
        """Cache is stale under a strict threshold."""
        cache = MotorCache()
        cache.timestamp = time.time() - 0.2  # 200ms ago
        self.assertFalse(cache.is_fresh(max_age_ms=100.0))

    def test_boundary_exactly_at_limit(self):
        """Cache right at the threshold should be stale (not strictly less than)."""
        cache = MotorCache()
        cache.timestamp = time.time() - 0.5  # exactly 500ms ago
        # is_fresh uses strict <, so 500ms old with 500ms limit is stale
        self.assertFalse(cache.is_fresh(max_age_ms=500.0))

    def test_data_defaults_to_none(self):
        """Freshly created cache has no data."""
        cache = MotorCache()
        self.assertIsNone(cache.data)

    def test_timestamp_updated(self):
        """Manually updating timestamp makes stale cache fresh again."""
        cache = MotorCache()
        cache.timestamp = time.time() - 1.0  # stale
        self.assertFalse(cache.is_fresh())
        cache.timestamp = time.time()  # refresh
        self.assertTrue(cache.is_fresh())


if __name__ == "__main__":
    unittest.main()
