"""
Shared layer — platform-independent core.
Re-exports all public symbols from app/ for compatibility.
"""

from app.controllers.motor_controller import MotorController
from app.controllers.motor_monitor import MotorMonitor
from app.core.events import EventBus
from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF
from app.models.motor_data import (
    JointState,
    MotorData,
    ProgramBlock,
    RobotProgram,
    RobotState,
)
from app.services.kinematics_service import KinematicsService
from app.services.program_service import ProgramService
from app.services.robot_service import RobotService
from app.utils.config_manager import ConfigManager
from app.utils.logger import Logger

__all__ = [
    "ConfigManager",
    "EventBus",
    "InverseKinematics6DOF",
    "JointState",
    "KinematicsService",
    "Logger",
    "MotorController",
    "MotorData",
    "MotorMonitor",
    "ProgramBlock",
    "ProgramService",
    "RobotKinematics6DOF",
    "RobotProgram",
    "RobotService",
    "RobotState",
]
