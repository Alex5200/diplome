"""
Shared layer — platform-independent core.
Re-exports all public symbols from app/ for compatibility.
"""

from app.models.motor_data import (
    MotorData,
    JointState,
    RobotState,
    ProgramBlock,
    RobotProgram,
)
from app.models.kinematics import RobotKinematics6DOF, InverseKinematics6DOF
from app.controllers.motor_controller import MotorController
from app.controllers.motor_monitor import MotorMonitor
from app.services.robot_service import RobotService
from app.services.kinematics_service import KinematicsService
from app.services.program_service import ProgramService
from app.core.events import EventBus
from app.utils.config_manager import ConfigManager
from app.utils.logger import Logger

__all__ = [
    "MotorData",
    "JointState",
    "RobotState",
    "ProgramBlock",
    "RobotProgram",
    "RobotKinematics6DOF",
    "InverseKinematics6DOF",
    "MotorController",
    "MotorMonitor",
    "RobotService",
    "KinematicsService",
    "ProgramService",
    "EventBus",
    "ConfigManager",
    "Logger",
]
