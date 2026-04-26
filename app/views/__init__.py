#!/usr/bin/env python3

"""
Views Package

GUI компоненты приложения на основе Tkinter:
    - main_window: Главное окно приложения
    - manual_control_panel: Панель ручного управления
    - motor_mapping_panel: Панель настройки соответствия моторов
    - kinematics_3d_panel: 3D визуализация кинематики
    - bottom_monitor_panel: Нижняя панель мониторинга
    - block_programming: Блочное программирование
"""

from app.views.block_programming import BlockPalette, ProgramCanvas
from app.views.bottom_monitor_panel import BottomMonitorPanel
from app.views.kinematics_3d_panel import Kinematics3DPanel
from app.views.main_window import RobotControlGUI
from app.views.manual_control_panel import ManualControlPanel
from app.views.motor_mapping_panel import MotorMappingPanel

__all__ = [
    "BlockPalette",
    "BottomMonitorPanel",
    "Kinematics3DPanel",
    "ManualControlPanel",
    "MotorMappingPanel",
    "ProgramCanvas",
    "RobotControlGUI",
]
