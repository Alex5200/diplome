#!/usr/bin/env python3
"""
Robot Hardware Interface - ROS2 Hardware Interface for ST3215 robot.

Provides unified, thread-safe access to ST3215 motors for all ROS 2 nodes.
Uses core module for data models.

Usage:
    from robot_control.hardware_interface import RobotHWInterface

    hw = RobotHWInterface.get_instance()
    hw.initialize("COM3", 1000000)
    states = hw.read_joint_states()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import ClassVar

try:
    from st3215 import ST3215
except ImportError:
    import sys
    sys.stderr.write("Warning: st3215 package not installed. Install with: pip install st3215\n")
    ST3215 = None

from core.motor_data import MotorData, JointState as CoreJointState, RobotState


@dataclass
class JointState:
    """Joint state data for ROS 2."""

    position_rad: float = 0.0
    velocity_rad_s: float = 0.0
    effort: float = 0.0
    position_raw: int = 2048  # 0-4095


@dataclass
class MotorCache:
    """Thread-safe cache for motor data."""

    data: MotorData | None = None
    timestamp: float = field(default_factory=time.time)

    def is_fresh(self, max_age_ms: float = 500.0) -> bool:
        """Check if data is fresh."""
        return (time.time() - self.timestamp) * 1000 < max_age_ms


class RobotHWInterface:
    """
    Singleton hardware interface for ST3215 robot control.

    Ensures only one MotorController connection exists across all ROS 2 nodes.
    Provides thread-safe access to motor data and commands.

    Usage:
        hw = RobotHWInterface.get_instance()
        hw.initialize("COM3", 1000000)
        states = hw.read_joint_states()
    """

    _instance: ClassVar[RobotHWInterface | None] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> RobotHWInterface:
        """Singleton pattern - only one instance allowed."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> RobotHWInterface:
        """Get singleton instance."""
        return cls()

    def _initialize_internal(self) -> None:
        """Internal initialization (called once)."""
        if self._initialized:
            return

        self._motor: ST3215 | None = None
        self._connected = False
        self._cache: dict[int, MotorCache] = {}
        self._cache_lock = threading.Lock()
        self._running = False
        self._motor_ids: list[int] = []
        self._monitor_thread: threading.Thread | None = None

        self._initialized = True

    def initialize(self, port: str, baudrate: int, monitor_rate_hz: float = 50.0) -> bool:
        """
        Initialize hardware connection.

        Args:
            port: Serial port (e.g., "COM3" or "/dev/ttyUSB0")
            baudrate: Baud rate (typically 1000000)
            monitor_rate_hz: Background polling rate

        Returns:
            True if connected successfully
        """
        if ST3215 is None:
            return False

        self._initialize_internal()

        if self._connected:
            return True

        try:
            self._motor = ST3215(device=port)
            self._connected = True
            self._motor_ids = [1, 2, 3, 4, 5, 6]
            self._start_monitor(monitor_rate_hz)

            with self._cache_lock:
                for mid in self._motor_ids:
                    self._cache[mid] = MotorCache()
            return True
        except Exception:
            return False

        return success

    def is_connected(self) -> bool:
        """Check if motors are connected."""
        if not self._initialized:
            return False
        return self._connected

    def is_initialized(self) -> bool:
        """Check if interface has been initialized."""
        return self._initialized

    def read_joint_states(self) -> list[JointState]:
        """
        Read current joint states from cache.

        Returns:
            List of 6 JointState objects (one per joint)
        """
        if not self._initialized or not self._connected:
            return [JointState() for _ in range(6)]

        states = []
        for i in range(6):
            motor_id = i + 1

            with self._cache_lock:
                cache = self._cache.get(motor_id)
                if cache and cache.data:
                    pos_raw = cache.data.position or 2048
                    pos_rad = self._position_to_rad(pos_raw)
                    states.append(JointState(position_rad=pos_rad, position_raw=pos_raw))
                else:
                    states.append(JointState())

        return states

    def write_joint_positions(self, positions_rad: list[float]) -> bool:
        """
        Write target positions to joints.

        Args:
            positions_rad: List of 6 positions in radians

        Returns:
            True if all commands sent successfully
        """
        if not self._initialized or not self._connected:
            return False

        if len(positions_rad) != 6:
            return False

        success = True
        for i, pos_rad in enumerate(positions_rad):
            pos_raw = self._rad_to_position(pos_rad)
            motor_id = i + 1
            try:
                if self._motor:
                    self._motor.write(motor_id, pos_raw)
            except Exception:
                success = False

        return success

    def get_motor_data(self, motor_id: int) -> MotorData | None:
        """Get cached motor data."""
        if not self._initialized:
            return None

        with self._cache_lock:
            cache = self._cache.get(motor_id)
            if cache:
                return cache.data
            return None

    def get_all_motor_data(self) -> dict[int, MotorData]:
        """Get all cached motor data."""
        if not self._initialized:
            return {}

        with self._cache_lock:
            return {mid: cache.data for mid, cache in self._cache.items() if cache.data}

    def emergency_stop(self) -> None:
        """Emergency stop all motors."""
        if self._initialized and self._connected:
            try:
                for motor_id in self._motor_ids:
                    if self._motor:
                        self._motor.torque_disable(motor_id)
            except Exception:
                pass

    def shutdown(self) -> None:
        """Cleanup and disconnect."""
        if not self._initialized:
            return

        self._stop_monitor()

        if self._connected:
            try:
                if hasattr(self._motor, 'portHandler'):
                    self._motor.portHandler.closePort()
            except Exception:
                pass
            self._connected = False

        # Clear singleton
        with self._instance_lock:
            RobotHWInterface._instance = None
            self._initialized = False

    def _start_monitor(self, rate_hz: float) -> None:
        """Start background monitoring thread."""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(rate_hz,), daemon=True
        )
        self._monitor_thread.start()

    def _stop_monitor(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)

    def _monitor_loop(self, rate_hz: float) -> None:
        """Background thread updating motor data cache."""

        interval = 1.0 / rate_hz

        while self._running:
            start = time.time()

            if self._connected and self._motor:
                for motor_id in self._motor_ids:
                    try:
                        position = self._motor.read_position(motor_id)
                        data = {
                            "position": position if position is not None else 2048,
                            "temperature": 0.0,
                            "voltage": 0.0,
                            "current": 0.0,
                            "load": 0.0,
                            "mode": None,
                            "moving": False,
                        }
                        with self._cache_lock:
                            if motor_id not in self._cache:
                                self._cache[motor_id] = MotorCache()
                            self._cache[motor_id].data = MotorData(
                                motor_id=motor_id,
                                position=data.get("position", 2048),
                                temperature=data.get("temperature", 0.0),
                                voltage=data.get("voltage", 0.0),
                                current=data.get("current", 0.0),
                                load=data.get("load", 0.0),
                                mode=data.get("mode"),
                                moving=data.get("moving", False),
                            )
                            self._cache[motor_id].timestamp = time.time()
                    except Exception:
                        pass

            elapsed = time.time() - start
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)

    @staticmethod
    def _position_to_rad(position: int) -> float:
        """Convert motor position (0-4095) to radians (-π to π)."""
        import math

        angle_deg = (position / 4095.0) * 360.0 - 180.0
        return math.radians(angle_deg)

    @staticmethod
    def _rad_to_position(rad: float) -> int:
        """Convert radians to motor position (0-4095)."""
        import math

        angle_deg = math.degrees(rad)
        position = round((angle_deg + 180.0) / 360.0 * 4095)
        return max(0, min(4095, position))
