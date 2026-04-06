#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration Package

Содержит константы приложения и настройки по умолчанию.
"""

from app.config.constants import (
    MIN_POSITION,
    MAX_POSITION,
    DEFAULT_SPEED,
    DEFAULT_ACC,
    MONITOR_INTERVAL,
    TEMP_WARNING,
    TEMP_CRITICAL,
    LOAD_WARNING,
    CONFIG_FILE,
    PROGRAM_FILE,
    FANUC_BG,
    FANUC_PANEL,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_RED,
    FANUC_BLUE,
    FANUC_TEXT,
    FANUC_GRAY,
    BLOCK_COLORS,
    KINEMA_COLORS,
    JOINT_NAMES,
    DEFAULT_MOTOR_MAPPING,
    DEFAULT_MOTOR_CONFIG,
    JOG_MODE_JOINT,
    JOG_MODE_CARTESIAN,
    MAX_POSITION_REGISTERS,
    MAX_PROGRAM_LINES,
    SPEED_OVERRIDE_MIN,
    SPEED_OVERRIDE_MAX,
    SPEED_OVERRIDE_DEFAULT,
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
