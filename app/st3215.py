# Mock ST3215 motor driver for Docker testing
# In production, this would be the actual Lewansoul ST3215 driver

import time
import threading
from typing import Optional, Dict, Any


class ST3215:
    """Mock ST3215 servo motor driver for testing without hardware."""

    def __init__(self, device: str = "/dev/ttyUSB0", baudrate: int = 115200, timeout: float = 0.1):
        self.device = device
        self.baudrate = baudrate
        self.timeout = timeout
        self.connected = False
        self._positions: Dict[int, int] = {i: 2048 for i in range(1, 7)}
        self._torques: Dict[int, bool] = {i: True for i in range(1, 7)}
        self._speeds: Dict[int, int] = {i: 2400 for i in range(1, 7)}

    def connect(self) -> bool:
        """Simulate connection to motor."""
        self.connected = True
        return True

    def disconnect(self):
        """Disconnect from motor."""
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def ping(self, motor_id: int) -> bool:
        """Check if motor responds."""
        return self.connected and 1 <= motor_id <= 6

    def set_position(self, motor_id: int, position: int, speed: int = 2400) -> bool:
        """Set motor position (0-4095)."""
        if not self.connected:
            return False
        if not (0 <= position <= 4095):
            return False
        self._positions[motor_id] = position
        self._speeds[motor_id] = speed
        return True

    def read_position(self, motor_id: int) -> int:
        """Read current motor position."""
        if not self.connected:
            return 2048
        return self._positions.get(motor_id, 2048)

    def enable_torque(self, motor_id: int, enable: bool = True) -> bool:
        """Enable or disable motor torque."""
        if not self.connected:
            return False
        self._torques[motor_id] = enable
        return True

    def read_load(self, motor_id: int) -> int:
        """Read motor load (simulated)."""
        if not self.connected:
            return 0
        return 50  # Simulated 50% load

    def read_temperature(self, motor_id: int) -> float:
        """Read motor temperature in Celsius."""
        if not self.connected:
            return 25.0
        return 35.0  # Simulated temperature

    def read_voltage(self, motor_id: int) -> float:
        """Read motor voltage."""
        if not self.connected:
            return 0.0
        return 12.0  # Simulated 12V

    def read_speed(self, motor_id: int) -> int:
        """Read motor speed."""
        if not self.connected:
            return 0
        return self._speeds.get(motor_id, 2400)

    def get_motor_data(self, motor_id: int) -> Dict[str, Any]:
        """Get all motor data at once."""
        return {
            "position": self.read_position(motor_id),
            "load": self.read_load(motor_id),
            "temperature": self.read_temperature(motor_id),
            "voltage": self.read_voltage(motor_id),
            "speed": self.read_speed(motor_id),
            "torque_enabled": self._torques.get(motor_id, False),
        }
