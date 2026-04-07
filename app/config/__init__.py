#!/usr/bin/env python3

"""
Configuration Package

Содержит константы приложения и настройки по умолчанию.
"""

from app.config.constants import (
    BLOCK_COLORS,
    CONFIG_FILE,
    DEFAULT_ACC,
    DEFAULT_MOTOR_CONFIG,
    DEFAULT_MOTOR_MAPPING,
    DEFAULT_SPEED,
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    JOG_MODE_CARTESIAN,
    JOG_MODE_JOINT,
    JOINT_NAMES,
    KINEMA_COLORS,
    LOAD_WARNING,
    MAX_POSITION,
    MAX_POSITION_REGISTERS,
    MAX_PROGRAM_LINES,
    MIN_POSITION,
    MONITOR_INTERVAL,
    PROGRAM_FILE,
    SPEED_OVERRIDE_DEFAULT,
    SPEED_OVERRIDE_MAX,
    SPEED_OVERRIDE_MIN,
    TEMP_CRITICAL,
    TEMP_WARNING,
)

__all__ = [
    # Position constants
    "MIN_POSITION",
    "MAX_POSITION",
    # Motion defaults
    "DEFAULT_SPEED",
    "DEFAULT_ACC",
    # Monitoring
    "MONITOR_INTERVAL",
    # Temperature thresholds
    "TEMP_WARNING",
    "TEMP_CRITICAL",
    # Load threshold
    "LOAD_WARNING",
    # Files
    "CONFIG_FILE",
    "PROGRAM_FILE",
    # Colors (FANUC theme)
    "FANUC_BG",
    "FANUC_PANEL",
    "FANUC_GREEN",
    "FANUC_ORANGE",
    "FANUC_RED",
    "FANUC_BLUE",
    "FANUC_TEXT",
    "FANUC_GRAY",
    # Block colors
    "BLOCK_COLORS",
    "KINEMA_COLORS",
    # Joint names
    "JOINT_NAMES",
    # Default mappings
    "DEFAULT_MOTOR_MAPPING",
    "DEFAULT_MOTOR_CONFIG",
]
