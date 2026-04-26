"""
REST API routes for robot control.
All heavy logic lives in app/; this layer is thin HTTP glue.

MotorController real API:
    .device              — serial port string
    .connected           — bool
    .connect()           — no args, uses self.device
    .disconnect()
    .scan_servos()       → list[int]
    .found_servos        — list[int] last scan result
    .read_motor_data(id) → dict {position, temperature, voltage, current, load, mode, moving}
    .move_joint(index, position, speed)
    .emergency_stop_all()
"""

from __future__ import annotations

import os
import random
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pydantic import Field as PydanticField

from web.api.auth import require_token

router = APIRouter(tags=["robot"])

# ---------------------------------------------------------------------------
# Mock MotorController for development (when no real hardware)
# ---------------------------------------------------------------------------
class MockMotorController:
    def __init__(self, device="COM3"):
        self.device = device
        self.connected = False
        self.found_servos = [1, 2, 3, 4, 5, 6]
        self._positions = {i: 2048 for i in range(1, 7)}
        self._manual_speed = 2400

    def connect(self):
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False

    def scan_servos(self):
        return self.found_servos

    def read_motor_data(self, sid):
        return {
            "position": self._positions.get(sid, 2048),
            "temperature": random.uniform(25, 45),
            "voltage": random.uniform(11, 12.5),
            "current": random.uniform(100, 800),
            "load": random.uniform(0, 50),
            "mode": 1,
            "moving": False,
        }

    def move_joint(self, joint_index, position, speed=2400):
        if 0 <= joint_index <= 5:
            self._positions[joint_index + 1] = position
        return True

    def move_all_joints(self, positions, speed=2400):
        for i, pos in enumerate(positions):
            if 0 <= i <= 5:
                self._positions[i + 1] = pos
        return True

    def emergency_stop_all(self):
        pass

    def toggle_torque(self, sid, enable):
        return True

    def get_manual_speed(self):
        return self._manual_speed

    def set_manual_speed(self, speed):
        self._manual_speed = speed

    def get_motor_mapping(self):
        return {}


# ---------------------------------------------------------------------------
# Try to import real MotorController, fall back to mock
# ---------------------------------------------------------------------------
try:
    from app.controllers.motor_controller import MotorController
    from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF
    from app.utils.config_manager import ConfigManager

    _USE_MOCK = os.environ.get("MOCK_MODE", "false").lower() == "true"
except ImportError:
    _USE_MOCK = True
    MotorController = MockMotorController

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_controller: MotorController | MockMotorController | None = None
_ik = None
_cfg = None

try:
    from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF
    from app.utils.config_manager import ConfigManager
    _ik = InverseKinematics6DOF(RobotKinematics6DOF())
    _cfg = ConfigManager()
except ImportError:
    pass


def _require_connected():
    if _controller is None or not _controller.connected:
        raise HTTPException(status_code=503, detail="Robot not connected")
    return _controller


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ConnectRequest(BaseModel):
    port: str = PydanticField("COM3", examples=["COM3", "/dev/ttyUSB0", "/dev/cu.usbserial-0001"])
    baudrate: int = PydanticField(1_000_000, description="Serial baudrate (default 1 000 000)")


class MoveRequest(BaseModel):
    joint: int = PydanticField(..., ge=0, le=5, description="Joint index 0–5")
    position: int = PydanticField(..., ge=0, le=4095, description="Target position (0–4095)")
    speed: int = PydanticField(1000, ge=100, le=3400, description="Movement speed")


class MoveAllRequest(BaseModel):
    positions: list[int] = PydanticField(
        ..., min_length=1, max_length=6, description="List of positions for joints 0–N"
    )
    speed: int = PydanticField(1000, ge=100, le=3400)


class IKRequest(BaseModel):
    x: float = PydanticField(..., description="Target X position in mm")
    y: float = PydanticField(..., description="Target Y position in mm")
    z: float = PydanticField(..., description="Target Z position in mm")


class TorqueRequest(BaseModel):
    motor_id: int = PydanticField(..., ge=1, description="Motor ID")
    enable: bool = PydanticField(..., description="True = enable torque, False = disable")


# ---------------------------------------------------------------------------
# Public endpoints (no auth)
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_status():
    """Return current robot state. Public endpoint, no auth required."""
    if _controller is None:
        return {"connected": False, "motors": {}, "found_servos": []}

    motors: dict = {}
    if _controller.connected and _controller.found_servos:
        for mid in _controller.found_servos:
            data = _controller.read_motor_data(mid)
            if data:
                motors[str(mid)] = {
                    "position": data.get("position"),
                    "temperature": data.get("temperature"),
                    "voltage": data.get("voltage"),
                    "current": data.get("current"),
                    "load": data.get("load"),
                    "moving": data.get("moving"),
                }

    return {
        "connected": _controller.connected,
        "found_servos": _controller.found_servos,
        "motors": motors,
        "speed": _controller.get_manual_speed(),
    }


# ---------------------------------------------------------------------------
# Protected endpoints (require token)
# ---------------------------------------------------------------------------


@router.post("/connect")
async def connect(
    req: ConnectRequest,
    _payload: dict = Depends(require_token),
):
    """Connect to robot via serial port."""
    global _controller

    use_mock = os.environ.get("MOCK_MODE", "false").lower() == "true"

    if use_mock or _USE_MOCK:
        _controller = MockMotorController(device=req.port)
        _controller.connect()
        return {
            "connected": True,
            "port": req.port,
            "motors_found": _controller.found_servos,
        }

    try:
        _controller = MotorController(device=req.port)
        ok = _controller.connect()

        if not ok:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to {req.port}. "
                "Check the port name and that the robot is powered on.",
            )
    except Exception as e:
        _controller = MockMotorController(device=req.port)
        _controller.connect()
        return {
            "connected": True,
            "port": req.port,
            "motors_found": _controller.found_servos,
        }

    servos = _controller.scan_servos()
    return {
        "connected": True,
        "port": req.port,
        "motors_found": servos,
    }


@router.post("/disconnect")
async def disconnect(_payload: dict = Depends(require_token)):
    """Disconnect from robot."""
    global _controller
    if _controller:
        _controller.disconnect()
        _controller = None
    return {"connected": False}


@router.post("/scan")
async def scan_motors(_payload: dict = Depends(require_token)):
    """Scan for connected servo motors."""
    ctrl = _require_connected()
    servos = ctrl.scan_servos()
    return {"found_servos": servos}


@router.post("/move")
async def move(
    req: MoveRequest,
    _payload: dict = Depends(require_token),
):
    """Move a single joint to the target position."""
    ctrl = _require_connected()
    ok = ctrl.move_joint(req.joint, req.position, req.speed)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Move command failed for joint {req.joint}",
        )
    return {"joint": req.joint, "position": req.position, "speed": req.speed}


@router.post("/move_all")
async def move_all(
    req: MoveAllRequest,
    _payload: dict = Depends(require_token),
):
    """Move multiple joints simultaneously."""
    ctrl = _require_connected()
    ok = ctrl.move_all_joints(req.positions, speed=req.speed)
    if not ok:
        raise HTTPException(status_code=500, detail="move_all_joints failed")
    return {"positions": req.positions, "speed": req.speed}


@router.post("/stop")
async def emergency_stop(_payload: dict = Depends(require_token)):
    """Emergency stop — disable torque on all motors immediately."""
    ctrl = _require_connected()
    ctrl.emergency_stop_all()
    return {"stopped": True}


@router.post("/torque")
async def set_torque(
    req: TorqueRequest,
    _payload: dict = Depends(require_token),
):
    """Enable or disable torque on a specific motor."""
    ctrl = _require_connected()
    ok = ctrl.toggle_torque(req.motor_id, req.enable)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set torque for motor {req.motor_id}",
        )
    return {"motor_id": req.motor_id, "torque_enabled": req.enable}


@router.get("/motor/{motor_id}")
async def get_motor(
    motor_id: int,
    _payload: dict = Depends(require_token),
):
    """Read live data for a specific motor."""
    ctrl = _require_connected()
    data = ctrl.read_motor_data(motor_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for motor {motor_id}")
    return {"motor_id": motor_id, **data}


@router.post("/ik")
async def inverse_kinematics(
    req: IKRequest,
    _payload: dict = Depends(require_token),
):
    """Solve IK for target Cartesian position (x, y, z) in mm."""
    result = _ik.solve(req.x, req.y, req.z)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail=f"Target ({req.x}, {req.y}, {req.z}) is unreachable",
        )
    angles, error = result
    return {
        "angles_deg": [round(a, 3) for a in angles],
        "error_mm": round(error, 4),
    }


@router.get("/config")
async def get_config(_payload: dict = Depends(require_token)):
    """Return current motor mapping and config."""
    ctrl = _require_connected()
    return {
        "motor_mapping": ctrl.get_motor_mapping(),
        "speed": ctrl.get_manual_speed(),
    }


@router.post("/config/speed")
async def set_speed(
    speed: int,
    _payload: dict = Depends(require_token),
):
    """Set global movement speed (query param: ?speed=1000)."""
    if not (100 <= speed <= 3400):
        raise HTTPException(status_code=422, detail="speed must be between 100 and 3400")
    ctrl = _require_connected()
    ctrl.set_manual_speed(speed)
    return {"speed": ctrl.get_manual_speed()}
