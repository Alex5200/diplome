"""
REST API routes for robot control.
All heavy logic lives in shared/ (app/); this layer is thin HTTP glue.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.controllers.motor_controller import MotorController
from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF
from app.utils.config_manager import ConfigManager

router = APIRouter(tags=["robot"])

# ---------------------------------------------------------------------------
# Shared state (single controller instance per server process)
# ---------------------------------------------------------------------------
_controller: Optional[MotorController] = None
_ik = InverseKinematics6DOF(RobotKinematics6DOF())
_cfg = ConfigManager()


def _require_connected() -> MotorController:
    if _controller is None or not _controller.is_connected:
        raise HTTPException(status_code=503, detail="Robot not connected")
    return _controller


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ConnectRequest(BaseModel):
    port: str = Field("COM3", examples=["COM3", "/dev/ttyUSB0"])
    baudrate: int = 1000000


class MoveRequest(BaseModel):
    joint: int = Field(..., ge=1, le=6, description="Joint index 1–6")
    position: int = Field(..., ge=0, le=4095)
    speed: int = Field(2400, ge=100, le=3400)


class IKRequest(BaseModel):
    x: float
    y: float
    z: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/status")
async def get_status():
    """Return current robot state (connected, motor data)."""
    if _controller is None:
        return {"connected": False, "motors": {}}
    motors = {}
    if _controller.is_connected:
        for mid in _controller.get_connected_motors():
            data = _controller.get_motor_data(mid)
            if data:
                motors[mid] = {
                    "position": data.position,
                    "temperature": data.temperature,
                    "voltage": data.voltage,
                    "current": data.current,
                    "load": data.load,
                    "status": data.status.value if hasattr(data.status, "value") else str(data.status),
                }
    return {"connected": _controller.is_connected, "motors": motors}


@router.post("/connect")
async def connect(req: ConnectRequest):
    """Connect to robot via serial port."""
    global _controller
    _controller = MotorController()
    ok = _controller.connect(req.port, req.baudrate)
    if not ok:
        raise HTTPException(status_code=500, detail=f"Failed to connect to {req.port}")
    motors = _controller.scan_motors()
    return {"connected": True, "motors_found": motors}


@router.post("/disconnect")
async def disconnect():
    """Disconnect from robot."""
    global _controller
    if _controller:
        _controller.disconnect()
    return {"connected": False}


@router.post("/move")
async def move(req: MoveRequest):
    """Move a single joint to the target position."""
    ctrl = _require_connected()
    ok = ctrl.move_joint(req.joint, req.position, req.speed)
    if not ok:
        raise HTTPException(status_code=500, detail="Move command failed")
    return {"joint": req.joint, "position": req.position}


@router.post("/stop")
async def emergency_stop():
    """Emergency stop — disable torque on all motors."""
    ctrl = _require_connected()
    ctrl.emergency_stop()
    return {"stopped": True}


@router.post("/ik")
async def inverse_kinematics(req: IKRequest):
    """Solve IK for target Cartesian position (x, y, z) in mm."""
    result = _ik.solve(req.x, req.y, req.z)
    if result is None:
        raise HTTPException(status_code=422, detail="Target position is unreachable")
    angles, error = result
    return {"angles_deg": angles, "error_mm": round(error, 4)}
