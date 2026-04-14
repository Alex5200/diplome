---
date: 2025-04-09
topic: "Robot Hardware Interface for ROS 2"
status: draft
phase: 1
---

## Problem Statement

### Current Architecture Issues

The existing ROS 2 implementation has a critical flaw: **multiple nodes create separate connections to the ST3215 motors**:

- `robot_node.py` creates its own `MotorController` instance
- `monitor_node.py` creates another `MotorController` instance
- Each node calls `connect(port, baudrate)` independently

**Consequences:**
1. **Port conflicts** - Serial port can only have one connection
2. **State inconsistency** - Each node sees different motor states
3. **Resource waste** - Duplicate motor scanning and polling
4. **Race conditions** - Simultaneous writes from different nodes

### Existing Code Analysis

From `robot_node.py` (lines 45-55):
```python
# Hardware - creates NEW controller instance
self._ctrl = MotorController()
self._monitor: MotorMonitor | None = None

# Connect - separate connection
if self._ctrl.connect(port, baudrate):
    self._ctrl.scan_motors()
```

From `monitor_node.py` (lines 42-50):
```python
# ANOTHER separate instance!
self._ctrl = MotorController()
self._monitor: MotorMonitor | None = None

if self._ctrl.connect(port, baudrate):
    motors = self._ctrl.scan_motors()
```

### Desired State

Single shared `MotorController` instance accessed by all ROS 2 nodes through a unified Hardware Interface.

---

## Constraints

1. **Maintain backward compatibility** - Existing GUI and tests must continue working
2. **Thread safety** - MotorController uses threading.Lock() which must be preserved
3. **No breaking changes to MotorController** - Don't modify app/controllers/motor_controller.py
4. **ROS 2 Humble compatibility** - Must work with standard rclpy patterns
5. **Offline mode support** - System should work without physical motors (simulation)

---

## Approach

### Solution Pattern: Singleton Hardware Interface

Create a **singleton wrapper** around `MotorController` that provides:
1. **Single connection point** - Only one serial connection
2. **Shared state** - All nodes see same motor data
3. **Thread-safe access** - Proper locking for concurrent reads/writes
4. **Lifecycle management** - Proper initialization and cleanup

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    ROS 2 Nodes                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ robot_node  │  │monitor_node │  │ trajectory_node     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼────────────┘
          │                │                    │
          └────────────────┴────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  RobotHWInterface   │  ← Singleton
                    │  (singleton)        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  MotorController    │  ← Existing class
                    │  (one instance)      │
                    └──────────┬──────────┘
                               │
                        ┌──────▼──────┐
                        │   ST3215    │
                        │  (serial)   │
                        └─────────────┘
```

### Key Design Decisions

**Decision 1: Singleton vs Dependency Injection**
- **Chosen**: Singleton pattern via module-level instance
- **Why**: ROS 2 nodes are separate processes, can't easily share objects
- **Alternative considered**: ROS 2 composable nodes (more complex)

**Decision 2: Direct MotorController access vs wrapper**
- **Chosen**: Thin wrapper with added ROS 2 semantics
- **Why**: Keeps existing code working, adds ROS 2 lifecycle

**Decision 3: Sync vs Async API**
- **Chosen**: Synchronous API with internal thread pool
- **Why**: Matches existing MotorController patterns

---

## Architecture

### Component: RobotHWInterface

**Purpose**: Singleton wrapper providing unified access to hardware

**Location**: `ros2/robot_control/hardware_interface.py`

**Responsibilities**:
1. Maintain single MotorController instance
2. Provide thread-safe read/write methods
3. Manage connection lifecycle
4. Cache motor data for fast reads
5. Handle connection failures gracefully

**Interface**:
```python
class RobotHWInterface:
    """Singleton hardware interface for ST3215 motors."""
    
    # Class-level singleton instance
    _instance: ClassVar[RobotHWInterface | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()
    
    def __new__(cls) -> RobotHWInterface:
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, port: str, baudrate: int) -> bool:
        """Initialize connection (called once)."""
        
    def is_connected(self) -> bool:
        """Check if motors are connected."""
        
    def read_joint_states(self) -> list[JointState]:
        """Read current positions of all joints."""
        
    def write_joint_positions(self, positions: list[float]) -> bool:
        """Write target positions to joints."""
        
    def get_motor_data(self, motor_id: int) -> MotorData | None:
        """Get cached motor data."""
        
    def emergency_stop(self) -> None:
        """Emergency stop all motors."""
        
    def shutdown(self) -> None:
        """Cleanup and disconnect."""
```

### Component: SharedMotorMonitor

**Purpose**: Background thread updating motor data cache

**Location**: `ros2/robot_control/hardware_interface.py` (inner class)

**Responsibilities**:
1. Poll motors at configured rate
2. Update shared data cache
3. Detect connection failures
4. Provide data freshness indicators

### Component: Refactored Nodes

**robot_node_v2.py**:
- Uses `RobotHWInterface.get_instance()` 
- No direct MotorController instantiation
- Publishes `/robot/joint_states` from cached data

**monitor_node_v2.py**:
- Uses same `RobotHWInterface.get_instance()`
- Reads from shared cache (no direct motor access)
- Publishes diagnostics

---

## Data Flow

### Read Flow (Joint States)

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────┐
│ ROS 2 Node   │────▶│ RobotHWInterface │────▶│  Data Cache   │
│ (requests)   │     │  (get_joint_states)│     │ (thread-safe)│
└──────────────┘     └──────────────────┘     └───────┬───────┘
                                                      │
                                               ┌──────▼──────┐
                                               │ Background  │
                                               │ Monitor     │
                                               │ Thread      │
                                               └──────┬──────┘
                                                      │
                                               ┌──────▼──────┐
                                               │MotorController│
                                               │(actual read) │
                                               └─────────────┘
```

### Write Flow (Command)

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────┐
│ ROS 2 Node   │────▶│ RobotHWInterface │────▶│MotorController│
│ (command)    │     │ (write_joints)   │     │ (actual write)│
└──────────────┘     └──────────────────┘     └───────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ Command Queue│ (optional, for ordering)
                     └──────────────┘
```

---

## Error Handling Strategy

### Connection Failures

**Scenario**: Motor disconnected during operation

**Strategy**:
1. Background monitor detects read failure
2. Sets `is_connected = False`
3. Publishes diagnostic message
4. All read operations return last known values (with timestamp)
5. Write operations return False (no action taken)

### Partial Motor Failure

**Scenario**: One motor stops responding

**Strategy**:
1. Individual motor marked as `DISCONNECTED` in cache
2. Other motors continue operating
3. Alert published to `/robot/diagnostics`

### Race Condition Prevention

**Mechanism**:
```python
# MotorController already has _read_lock
# RobotHWInterface adds second layer:

with self._cache_lock:
    data = self._cache[motor_id].copy()
    
# Background thread:
with self._ctrl._read_lock:  # MotorController lock
    raw_data = self._ctrl.read_motor_data(mid)
    
with self._cache_lock:  # HWInterface lock
    self._cache[mid].update(raw_data)
```

---

## Testing Strategy

### Unit Tests

1. **Singleton behavior**: Multiple instantiations return same object
2. **Thread safety**: Concurrent read/write without corruption
3. **Connection lifecycle**: Proper init/shutdown sequence

### Integration Tests

1. **Two nodes sharing**: robot_node + monitor_node with same HWInterface
2. **Offline mode**: System starts without motors
3. **Reconnection**: Motor disconnect/reconnect handling

---

## Files to Create

| File | Purpose |
|------|---------|
| `ros2/robot_control/hardware_interface.py` | RobotHWInterface class |
| `ros2/robot_control/robot_node_v2.py` | Refactored robot_node |
| `ros2/robot_control/monitor_node_v2.py` | Refactored monitor_node |
| `ros2/launch/robot_v2.launch.py` | Launch file for new architecture |
| `ros2/tests/test_hw_interface.py` | Unit tests |

---

## Open Questions

1. **Cache TTL**: How long to keep cached data before marking stale? (Default: 500ms)
2. **Monitor Rate**: Background polling frequency? (Default: 50Hz for control)
3. **Retry Logic**: How many connection attempts before giving up? (Default: 3)

---

## Success Criteria

1. ✅ Only one MotorController instance created across all nodes
2. ✅ robot_node_v2 + monitor_node_v2 can run simultaneously
3. ✅ No serial port conflicts in logs
4. ✅ Joint states consistent between nodes
5. ✅ Existing tests continue to pass
6. ✅ Can run in offline mode (no motors connected)
