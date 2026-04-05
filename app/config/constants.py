#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Application Configuration Constants
"""

# --- КОНСТАНТЫ ---
MIN_POSITION = 0
MAX_POSITION = 4095
DEFAULT_SPEED = 2400
DEFAULT_ACC = 50
MONITOR_INTERVAL = 0.5

CONFIG_FILE = "robot_config.json"
PROGRAM_FILE = "robot_program.json"

# --- ТЕМПЕРАТУРНЫЕ ПОРОГИ ---
TEMP_WARNING = 70
TEMP_CRITICAL = 80
LOAD_WARNING = 80

# --- ЦВЕТА ---
FANUC_BG = "#1a1a2e"
FANUC_PANEL = "#16213e"
FANUC_GREEN = "#00ff88"
FANUC_ORANGE = "#ff9500"
FANUC_RED = "#ff4444"
FANUC_BLUE = "#00d4ff"
FANUC_TEXT = "#ffffff"
FANUC_GRAY = "#666666"

BLOCK_COLORS = {
    'motion': '#4CAF50',
    'control': '#2196F3',
    'logic': '#FF9800',
    'wait': '#9C27B0',
    'io': '#F44336',
}

KINEMA_COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']

# --- FANUC РЕЖИМЫ ---
JOG_MODE_JOINT = 'joint'
JOG_MODE_CARTESIAN = 'cartesian'

# --- ПОЗИЦИОННЫЕ РЕГИСТРЫ ---
MAX_POSITION_REGISTERS = 100
MAX_PROGRAM_LINES = 500

# --- СКОРОСТЬ ---
SPEED_OVERRIDE_MIN = 1
SPEED_OVERRIDE_MAX = 100
SPEED_OVERRIDE_DEFAULT = 50

# --- ЛОГИЧЕСКИЕ НАЗВАНИЯ СУСТАВОВ ---
JOINT_NAMES = [
    '🏗️ База',
    '💪 Плечо 1',
    '💪 Плечо 2',
    '🦾 Локоть',
    '🖐️ Кисть 1',
    '🖐️ Кисть 2'
]

# Конфигурация по умолчанию
DEFAULT_MOTOR_MAPPING = {
    'joint_0': {'motor_id': 1, 'name': 'База', 'min_pos': 0, 'max_pos': MAX_POSITION, 'inverted': True},
    'joint_1': {'motor_id': 2, 'name': 'Плечо 1', 'min_pos': 0, 'max_pos': MAX_POSITION, 'inverted': False},
    'joint_2': {'motor_id': 4, 'name': 'Плечо 2', 'min_pos': 0, 'max_pos': MAX_POSITION, 'inverted': True},
    'joint_3': {'motor_id': 5, 'name': 'Локоть', 'min_pos': 0, 'max_pos': MAX_POSITION, 'inverted': False},
    'joint_4': {'motor_id': 3, 'name': 'Кисть 1', 'min_pos': 0, 'max_pos': MAX_POSITION, 'inverted': False},
    'joint_5': {'motor_id': 6, 'name': 'Кисть 2', 'min_pos': 0, 'max_pos': MAX_POSITION, 'inverted': False},
}

DEFAULT_MOTOR_CONFIG = {
    f'motor_{i}': {'min_pos': 0, 'max_pos': MAX_POSITION, 'name': f'Мотор {i}'}
    for i in range(1, 7)
}