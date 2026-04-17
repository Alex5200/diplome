#!/usr/bin/env python3

"""
Application Configuration Constants
"""

# --- КОНСТАНТЫ ---
MIN_POSITION = 0
MAX_POSITION = 4095
DEFAULT_SPEED = 2400
DEFAULT_ACC = 50
MONITOR_INTERVAL = 0.5


# --- ТЕМПЕРАТУРНЫЕ ПОРОГИ ---
TEMP_WARNING = 70
TEMP_CRITICAL = 80
LOAD_WARNING = 80

# --- ПАСТЕЛЬНАЯ ТЕМА ---
# Фон приложения (теплый кремовый)
FANUC_BG = "#faf8f5"
# Панели / карточки (белый с теплым оттенком)
FANUC_PANEL = "#ffffff"
# Пастельный мятный — основной акцент (успех, активные элементы)
FANUC_GREEN = "#000000"
# Пастельный персиковый — предупреждения, внимание
FANUC_ORANGE = "#f5b971"
# Пастельный коралловый — ошибки, стоп
FANUC_RED = "#e8927c"
# Пастельный голубой — информация, ссылки
FANUC_BLUE = "#8ab4f8"
# Основной текст — ЧЁРНЫЙ для максимального контраста
FANUC_TEXT = "#000000"
# Текст вторичный (тёмно-серый для less important)
FANUC_TEXT2 = "#4a4a5a"
# Разделители (тёмно-серый для видимости)
FANUC_GRAY = "#8a8580"

# --- СВЕТЛАЯ ПАСТЕЛЬНАЯ ТЕМА ---
LIGHT_BG = "#faf8f5"
LIGHT_PANEL = "#ffffff"
LIGHT_BORDER = "#e8e4e0"
LIGHT_TEXT = "#000000"  # Чёрный для контраста
LIGHT_TEXT2 = "#4a4a5a"  # Тёмно-серый для secondary
LIGHT_GREEN = "#7dd3c0"
LIGHT_ORANGE = "#f5b971"
LIGHT_RED = "#e8927c"
LIGHT_BLUE = "#8ab4f8"
LIGHT_ACCENT = "#7dd3c0"
LIGHT_HOVER = "#f0ece8"
LIGHT_SELECT = "#7dd3c0"

TEXT_COLOR = "#000000"

# Блоки — пастельные оттенки для различимости
BLOCK_COLORS = {
    "motion": "#a8e6cf",  # пастельный мятный
    "control": "#b8d4e3",  # пастельный голубой
    "logic": "#f4d03f",  # пастельный желтый
    "wait": "#f8c471",  # пастельный персиковый
    "io": "#d7bde2",  # пастельный лавандовый
}

KINEMA_COLORS = ["#7dd3c0", "#a8e6cf", "#b8d4e3", "#8ab4f8", "#d7bde2", "#f5b971"]

# --- FANUC РЕЖИМЫ ---
JOG_MODE_JOINT = "joint"
JOG_MODE_CARTESIAN = "cartesian"

# --- ПОЗИЦИОННЫЕ РЕГИСТРЫ ---
MAX_POSITION_REGISTERS = 100
MAX_PROGRAM_LINES = 500

# --- СКОРОСТЬ ---
SPEED_OVERRIDE_MIN = 1
SPEED_OVERRIDE_MAX = 100
SPEED_OVERRIDE_DEFAULT = 50

# --- ЛОГИЧЕСКИЕ НАЗВАНИЯ СУСТАВОВ ---
NUM_JOINTS = 6  # Количество суставов робота
JOINT_NAMES = [
    "База",
    "Плечо 1",
    "Плечо 2",
    "Локоть",
    "Кисть 1",
    "Кисть 2",
]

# --- ОРИЕНТАЦИЯ РОБОТА ---
ROBOT_ORIENTATIONS = {
    "front": 0,  # 0° - стандартная установка
    "left": -90,  # -90° - робот повернут влево
    "right": 90,  # +90° - робот повернут вправо
    "back": 180,  # 180° - робот повернут назад
}
DEFAULT_ORIENTATION = "front"

# Конфигурация по умолчанию

_ACCENT = "#7dd3c0"
_ACCENT_H = "#5bb8a4"
_BORDER = "#e8e4e0"
_CARD_BG = FANUC_PANEL
CONFIG_FILE = "robot_config.json"
PROGRAM_FILE = "robot_program.json"
DEFAULT_MOTOR_CONFIG = {
    f"motor_{i}": {"min_pos": 0, "max_pos": MAX_POSITION, "name": f"Мотор {i}"} for i in range(1, 7)
}
DEFAULT_ACC = 50
MAX_POSITION = 4095

DEFAULT_MOTOR_MAPPING = {
    "joint_0": {
        "motor_id": 1,
        "name": "База",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": True,
    },
    "joint_1": {
        "motor_id": 2,
        "name": "Плечо 1",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": False,
    },
    "joint_2": {
        "motor_id": 4,
        "name": "Плечо 2",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": True,
    },
    "joint_3": {
        "motor_id": 5,
        "name": "Локоть",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": False,
    },
    "joint_4": {
        "motor_id": 3,
        "name": "Кисть 1",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": False,
    },
    "joint_5": {
        "motor_id": 6,
        "name": "Кисть 2",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": False,
    },
}

# --- МАСШТАБИРОВАНИЕ ПОД МОНИТОР ---
# Процент от ширины экрана для определения размера окна
WINDOW_SCALE_PERCENT = 80  # 80% от ширины экрана
# Минимальный и максимальный масштаб (процент от базового размера)
MIN_SCALE_PERCENT = 10
MAX_SCALE_PERCENT = 100
# Базовый размер окна (при 100% масштабе)
BASE_WINDOW_WIDTH = 1400
BASE_WINDOW_HEIGHT = 600
