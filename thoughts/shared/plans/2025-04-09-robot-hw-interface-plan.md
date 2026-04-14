# Implementation Plan: Robot Hardware Interface (Phase 1)

Based on design: 2025-04-09-robot-hw-interface-design.md

## Task 1: Create RobotHWInterface Class

### 1.1 Create file: ros2/robot_control/hardware_interface.py

**Content:**
```python
#!/usr/bin/env python3
"""
Robot Hardware Interface - Singleton wrapper for MotorController.

Provides unified, thread-safe access to ST3215 motors for all ROS 2 nodes.
"""

from __future__ import annotations

import sys
import os
import threading
import time
from dataclasses import dataclass, field
from typing import ClassVar, Any

# Allow importing from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.controllers.motor_controller import MotorController
from app.controllers.motor_monitor import MotorMonitor
from app.models.motor_data import MotorData


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
    
    @property
    def is_fresh(self, max_age_ms: float = 500.0) -> bool:
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
            
        self._ctrl = MotorController()
        self._monitor: MotorMonitor | None = None
        self._monitor_thread: threading.Thread | None = None
        self._cache: dict[int, MotorCache] = {}
        self._cache_lock = threading.Lock()
        self._running = False
        self._motor_ids: list[int] = []
        
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
        self._initialize_internal()
        
        if self._ctrl.is_connected:
            return True
        
        success = self._ctrl.connect(port, baudrate)
        if success:
            self._motor_ids = self._ctrl.scan_motors()
            self._start_monitor(monitor_rate_hz)
            
            # Initialize cache
            with self._cache_lock:
                for mid in self._motor_ids:
                    self._cache[mid] = MotorCache()
                    
        return success
    
    def is_connected(self) -> bool:
        """Check if motors are connected."""
        if not self._initialized:
            return False
        return self._ctrl.is_connected
    
    def is_initialized(self) -> bool:
        """Check if interface has been initialized."""
        return self._initialized
    
    def read_joint_states(self) -> list[JointState]:
        """
        Read current joint states from cache.
        
        Returns:
            List of 6 JointState objects (one per joint)
        """
        if not self._initialized or not self._ctrl.is_connected:
            return [JointState() for _ in range(6)]
        
        states = []
        for i in range(6):
            motor_id = self._ctrl.get_motor_id_for_joint(i)
            
            with self._cache_lock:
                cache = self._cache.get(motor_id)
                if cache and cache.data:
                    # Convert position to radians
                    pos_raw = cache.data.position or 2048
                    pos_rad = self._position_to_rad(pos_raw)
                    states.append(JointState(
                        position_rad=pos_rad,
                        position_raw=pos_raw
                    ))
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
        if not self._initialized or not self._ctrl.is_connected:
            return False
        
        if len(positions_rad) != 6:
            return False
        
        success = True
        for i, pos_rad in enumerate(positions_rad):
            pos_raw = self._rad_to_position(pos_rad)
            if not self._ctrl.move_joint(i, pos_raw):
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
            return {
                mid: cache.data for mid, cache in self._cache.items()
                if cache.data
            }
    
    def emergency_stop(self) -> None:
        """Emergency stop all motors."""
        if self._initialized and self._ctrl.is_connected:
            self._ctrl.emergency_stop_all()
    
    def shutdown(self) -> None:
        """Cleanup and disconnect."""
        if not self._initialized:
            return
            
        self._stop_monitor()
        
        if self._ctrl.is_connected:
            self._ctrl.disconnect()
            
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
            target=self._monitor_loop,
            args=(rate_hz,),
            daemon=True
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
            
            if self._ctrl.is_connected:
                for motor_id in self._motor_ids:
                    try:
                        data = self._ctrl.read_motor_data(motor_id)
                        with self._cache_lock:
                            if motor_id not in self._cache:
                                self._cache[motor_id] = MotorCache()
                            self._cache[motor_id].data = MotorData(
                                motor_id=motor_id,
                                **data
                            ) if data else None
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
        position = int((angle_deg + 180.0) / 360.0 * 4095)
        return max(0, min(4095, position))
```

## Task 2: Refactor robot_node.py

### 2.1 Create file: ros2/robot_control/robot_node_v2.py

**Changes from v1:**
- Uses `RobotHWInterface.get_instance()` instead of direct MotorController
- No separate MotorMonitor (uses HWInterface cache)
- Simpler lifecycle management

**Key implementation:**
```python
class RobotNodeV2(Node):
    def __init__(self):
        super().__init__('robot_node_v2')
        
        # Use singleton HW interface
        self._hw = RobotHWInterface.get_instance()
        
        # Parameters
        self.declare_parameter('port', 'COM3')
        self.declare_parameter('baudrate', 1_000_000)
        
        # Initialize hardware
        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value
        
        if not self._hw.is_initialized():
            if self._hw.initialize(port, baudrate):
                self.get_logger().info(f'Connected to {port}')
            else:
                self.get_logger().warn(f'Could not connect to {port}')
        
        # Publishers (same as v1)
        self._pub_joints = self.create_publisher(
            JointState, '/robot/joint_states', 10
        )
        
        # Timer for publishing
        self.create_timer(0.1, self._publish_state)
    
    def _publish_state(self):
        """Publish joint states from HW cache."""
        states = self._hw.read_joint_states()
        # ... publish logic
```

## Task 3: Refactor monitor_node.py

### 3.1 Create file: ros2/robot_control/monitor_node_v2.py

**Changes from v1:**
- Uses `RobotHWInterface.get_instance()` 
- Reads from shared cache (no direct motor access)
- No separate connection

**Key implementation:**
```python
class MonitorNodeV2(Node):
    def __init__(self):
        super().__init__('monitor_node_v2')
        
        self._hw = RobotHWInterface.get_instance()
        
        # Wait for initialization
        if not self._hw.is_initialized():
            self.get_logger().warn('HW not initialized yet')
        
        # Publishers (same topics as v1)
        self._pub_diag = self.create_publisher(String, '/robot/diagnostics', 10)
        
        # Timer - reads from cache only
        self.create_timer(1.0, self._publish_diagnostics)
    
    def _publish_diagnostics(self):
        """Publish from shared cache."""
        motor_data = self._hw.get_all_motor_data()
        # ... publish logic using cached data
```

## Task 4: Create Tests

### 4.1 Create file: ros2/tests/test_hw_interface.py

**Test cases:**
```python
def test_singleton_pattern():
    """Multiple instantiations return same object."""
    hw1 = RobotHWInterface.get_instance()
    hw2 = RobotHWInterface.get_instance()
    assert hw1 is hw2

def test_thread_safety():
    """Concurrent reads don't corrupt data."""
    # Implementation...

def test_offline_mode():
    """System works without motors."""
    hw = RobotHWInterface.get_instance()
    states = hw.read_joint_states()
    assert len(states) == 6
    assert all(s.position_rad == 0.0 for s in states)
```

## Task 5: Create Launch File

### 5.1 Create file: ros2/launch/robot_v2.launch.py

```python
def generate_launch_description():
    return LaunchDescription([
        Node(
            package='robot_control',
            executable='robot_node_v2',
            name='robot_node_v2',
            parameters=[{'port': 'COM3', 'baudrate': 1000000}],
        ),
        Node(
            package='robot_control',
            executable='monitor_node_v2',
            name='monitor_node_v2',
        ),
    ])
```

## Task 6: Update setup.py

### 6.1 Modify: ros2/setup.py

Add entry points:
```python
entry_points={
    'console_scripts': [
        'robot_node_v2 = robot_control.robot_node_v2:main',
        'monitor_node_v2 = robot_control.monitor_node_v2:main',
    ],
}
```

## Dependencies

- app/controllers/motor_controller.py (unchanged)
- app/controllers/motor_monitor.py (unchanged)
- app/models/motor_data.py (unchanged)

## Verification Steps

1. Run unit tests: `python -m pytest ros2/tests/test_hw_interface.py`
2. Launch nodes: `ros2 launch robot_control robot_v2.launch.py`
3. Verify single connection in logs
4. Check joint_states consistency: `ros2 topic echo /robot/joint_states`
5. Test emergency stop: `ros2 topic pub /robot/stop std_msgs/Empty`