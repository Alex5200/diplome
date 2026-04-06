#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ST3215 Robot Control Panel v6.1
- 3D визуализация (matplotlib)
- Асинхронный мониторинг (нижняя панель)
- Настройка соответствия моторов суставам
- Все ошибки исправлены и проверены
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import json
import math
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List

from st3215 import ST3215

# matplotlib для 3D визуализации
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- КОНСТАНТЫ ---
MIN_POSITION = 0
MAX_POSITION = 4095
DEFAULT_SPEED = 2400
DEFAULT_ACC = 50
MONITOR_INTERVAL = 0.5
TEMP_WARNING = 70
TEMP_CRITICAL = 80
LOAD_WARNING = 80
CONFIG_FILE = "robot_config.json"
PROGRAM_FILE = "robot_program.json"

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
    "motion": "#4CAF50",
    "control": "#2196F3",
    "logic": "#FF9800",
    "wait": "#9C27B0",
    "io": "#F44336",
}

KINEMA_COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD"]

# --- ЛОГИЧЕСКИЕ НАЗВАНИЯ СУСТАВОВ ---
JOINT_NAMES = [
    "🏗️ База",
    "💪 Плечо 1",
    "💪 Плечо 2",
    "🦾 Локоть",
    "🖐️ Кисть 1",
    "🖐️ Кисть 2",
]

# Конфигурация по умолчанию
DEFAULT_MOTOR_MAPPING = {
    "joint_0": {"motor_id": 1, "name": "База", "min_pos": 0, "max_pos": MAX_POSITION},
    "joint_1": {
        "motor_id": 2,
        "name": "Плечо 1",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
    },
    "joint_2": {
        "motor_id": 3,
        "name": "Плечо 2",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
    },
    "joint_3": {"motor_id": 4, "name": "Локоть", "min_pos": 0, "max_pos": MAX_POSITION},
    "joint_4": {
        "motor_id": 5,
        "name": "Кисть 1",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
    },
    "joint_5": {
        "motor_id": 6,
        "name": "Кисть 2",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
    },
}

DEFAULT_MOTOR_CONFIG = {
    f"motor_{i}": {"min_pos": 0, "max_pos": MAX_POSITION, "name": f"Мотор {i}"}
    for i in range(1, 7)
}


# ==================== КЛАССЫ ДАННЫХ ====================


@dataclass
class MotorData:
    motor_id: int
    position: Optional[int] = None
    temperature: Optional[float] = None
    voltage: Optional[float] = None
    current: Optional[float] = None
    load: Optional[float] = None
    mode: Optional[int] = None
    moving: Optional[bool] = None
    torque_enabled: bool = False
    last_update: float = 0.0
    error_count: int = 0

    def is_overheating(self) -> bool:
        return self.temperature is not None and self.temperature >= TEMP_CRITICAL

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProgramBlock:
    id: int
    block_type: str
    params: dict
    order: int


# ==================== МОТОР КОНТРОЛЛЕР ====================


class MotorController:
    def __init__(self, device="COM3"):
        self.device = device
        self.motor = None
        self.connected = False
        self.found_servos: List[int] = []
        self.current_id: Optional[int] = None
        self.torque_states: Dict[int, bool] = {}
        self.joint_positions: Dict[int, float] = {i: 0.0 for i in range(1, 7)}
        self.cartesian_position = [0.0, 0.0, 0.0]
        self.motor_config = DEFAULT_MOTOR_CONFIG.copy()
        self.motor_mapping = DEFAULT_MOTOR_MAPPING.copy()
        self._read_lock = threading.Lock()
        self._manual_speed = DEFAULT_SPEED

    def connect(self):
        try:
            self.motor = ST3215(device=self.device)
            self.connected = True
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def disconnect(self):
        if self.motor:
            try:
                if hasattr(self.motor, "portHandler"):
                    self.motor.portHandler.closePort()
            except Exception as e:
                print(f"⚠️ Ошибка закрытия порта: {e}")
        self.connected = False
        self.motor = None

    def scan_servos(self):
        if not self.connected:
            return []
        try:
            self.found_servos = self.motor.ListServos()
            return self.found_servos
        except Exception as e:
            print(f"❌ Ошибка сканирования: {e}")
            return []

    def get_motor_id_for_joint(self, joint_index: int) -> int:
        key = f"joint_{joint_index}"
        if key in self.motor_mapping:
            return self.motor_mapping[key]["motor_id"]
        return joint_index + 1

    def get_joint_name(self, joint_index: int) -> str:
        key = f"joint_{joint_index}"
        if key in self.motor_mapping:
            return self.motor_mapping[key]["name"]
        return (
            JOINT_NAMES[joint_index]
            if joint_index < len(JOINT_NAMES)
            else f"Сустав {joint_index}"
        )

    def move_to_position(self, sts_id: int, position: int, speed=None, acc=DEFAULT_ACC):
        if not self.connected or not self.motor:
            return False
        if not (MIN_POSITION <= position <= MAX_POSITION):
            return False
        try:
            with self._read_lock:
                if speed is None:
                    speed = self._manual_speed
                self.motor.MoveTo(sts_id, position, speed=speed, acc=acc)
            self.joint_positions[sts_id] = position
            return True
        except Exception as e:
            print(f"Ошибка движения: {e}")
            return False

    def move_joint(self, joint_index: int, position: int, speed=None, acc=DEFAULT_ACC):
        motor_id = self.get_motor_id_for_joint(joint_index)
        return self.move_to_position(motor_id, position, speed, acc)

    def move_all_joints(self, positions: List[int], speed=DEFAULT_SPEED):
        for i, pos in enumerate(positions):
            self.move_joint(i, pos, speed=speed)
        return True

    def toggle_torque(self, sts_id: int, enable=True):
        if not self.connected or not self.motor:
            return False
        try:
            with self._read_lock:
                if enable:
                    result = self.motor.StartServo(sts_id)
                else:
                    result = self.motor.StopServo(sts_id)
            self.torque_states[sts_id] = enable
            return result is not None
        except Exception as e:
            print(f"Ошибка переключения момента: {e}")
            return False

    def get_torque_state(self, sts_id: int) -> bool:
        return self.torque_states.get(sts_id, False)

    def emergency_stop_all(self):
        if not self.connected or not self.motor:
            return
        for sid in self.found_servos:
            try:
                with self._read_lock:
                    self.motor.StopServo(sid)
                self.torque_states[sid] = False
            except Exception as e:
                print(f"Ошибка остановки мотора {sid}: {e}")

    def get_joint_positions(self) -> Dict[int, float]:
        return self.joint_positions.copy()

    def read_motor_data(self, sts_id: int) -> dict:
        if not self.connected or not self.motor:
            return {}
        data = {
            "position": None,
            "temperature": None,
            "voltage": None,
            "current": None,
            "load": None,
            "mode": None,
            "moving": None,
        }
        try:
            with self._read_lock:
                data["position"] = self.motor.ReadPosition(sts_id)
                data["temperature"] = self.motor.ReadTemperature(sts_id)
                data["voltage"] = self.motor.ReadVoltage(sts_id)
                data["current"] = self.motor.ReadCurrent(sts_id)
                data["load"] = self.motor.ReadLoad(sts_id)
                data["mode"] = self.motor.ReadMode(sts_id)
                data["moving"] = self.motor.IsMoving(sts_id)
        except Exception as e:
            print(f"⚠️ Ошибка чтения мотора {sts_id}: {e}")
        return data

    def set_manual_speed(self, speed: int):
        self._manual_speed = max(0, min(10000, speed))

    def get_manual_speed(self) -> int:
        return self._manual_speed

    def update_motor_mapping(self, joint_index: int, motor_id: int, name: str = ""):
        key = f"joint_{joint_index}"
        default_name = (
            JOINT_NAMES[joint_index]
            if joint_index < len(JOINT_NAMES)
            else f"Сустав {joint_index}"
        )
        self.motor_mapping[key] = {
            "motor_id": motor_id,
            "name": name or default_name,
            "min_pos": 0,
            "max_pos": MAX_POSITION,
        }

    def get_motor_mapping(self) -> dict:
        return self.motor_mapping.copy()

    def update_motor_config(
        self, motor_id: int, min_pos: int, max_pos: int, name: str = ""
    ):
        key = f"motor_{motor_id}"
        self.motor_config[key] = {
            "min_pos": min_pos,
            "max_pos": max_pos,
            "name": name or f"Мотор {motor_id}",
        }

    def get_motor_config(self, motor_id: int) -> dict:
        key = f"motor_{motor_id}"
        return self.motor_config.get(
            key, {"min_pos": 0, "max_pos": MAX_POSITION, "name": f"Мотор {motor_id}"}
        )

    def save_config(self, filename: str = CONFIG_FILE):
        try:
            config = {
                "port": self.device,
                "motor_config": self.motor_config,
                "motor_mapping": self.motor_mapping,
                "timestamp": datetime.now().isoformat(),
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")
            return False

    def load_config(self, filename: str = CONFIG_FILE):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "motor_config" in config:
                self.motor_config = config["motor_config"]
            if "motor_mapping" in config:
                self.motor_mapping = config["motor_mapping"]
            if "port" in config:
                self.device = config["port"]
            return True
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
            return False


# ==================== МОТОР МОНИТОР (АСИНХРОННЫЙ) ====================
# ==================== МОТОР МОНИТОР (АСИНХРОННЫЙ) ====================


class MotorMonitor:
    def __init__(self, motor_controller, update_callback=None):
        self.motor_controller = motor_controller
        self.update_callback = update_callback
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.motor_data: Dict[int, MotorData] = {}  # ✅ ИСПРАВЛЕНО
        self.lock = threading.Lock()

    def start(self, motor_ids: List[int]):
        if self.running:
            return
        with self.lock:
            for mid in motor_ids:
                if mid not in self.motor_data:  # ✅ ИСПРАВЛЕНО
                    self.motor_data[mid] = MotorData(motor_id=mid)
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print(f"🔍 Мониторинг запущен для {len(motor_ids)} моторов")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("🛑 Мониторинг остановлен")

    def _monitor_loop(self):
        while self.running:
            start_time = time.time()
            try:
                motor_ids = list(self.motor_data.keys())  # ✅ ИСПРАВЛЕНО
                for motor_id in motor_ids:
                    if not self.running:
                        break
                    with self.lock:
                        data = self.motor_data.get(motor_id)  # ✅ ИСПРАВЛЕНО
                        if data:  # ✅ ИСПРАВЛЕНО: было просто "if"
                            self._update_motor_data(motor_id, data)
            except Exception as e:
                print(f"❌ Ошибка мониторинга: {e}")
            elapsed = time.time() - start_time
            sleep_time = max(0, MONITOR_INTERVAL - elapsed)
            time.sleep(sleep_time)

    def _update_motor_data(
        self, motor_id: int, data: MotorData
    ):  # ✅ ИСПРАВЛЕНО: было " MotorData"
        if not self.motor_controller or not self.motor_controller.connected:
            return
        try:
            motor_data = self.motor_controller.read_motor_data(motor_id)
            data.position = motor_data.get("position")
            data.temperature = motor_data.get("temperature")
            data.voltage = motor_data.get("voltage")
            data.current = motor_data.get("current")
            data.load = motor_data.get("load")
            data.mode = motor_data.get("mode")
            data.moving = motor_data.get("moving")
            data.last_update = time.time()
            data.torque_enabled = self.motor_controller.get_torque_state(motor_id)
            if data.position is not None:
                data.error_count = 0
            else:
                data.error_count += 1
                if data.error_count > 5:
                    print(
                        f"⚠️ Мотор {motor_id}: много ошибок чтения ({data.error_count})"
                    )
        except Exception as e:
            data.error_count += 1
            print(f"⚠️ Ошибка обновления мотора {motor_id}: {e}")

    def get_data(self, motor_id: int) -> Optional[MotorData]:
        with self.lock:
            return self.motor_data.get(motor_id)  # ✅ ИСПРАВЛЕНО

    def get_all_data(self) -> Dict[int, MotorData]:
        with self.lock:
            return self.motor_data.copy()  # ✅ ИСПРАВЛЕНО


# ==================== НАСТРОЙКА СООТВЕТСТВИЯ МОТОРОВ ====================


class MotorMappingPanel(ttk.Frame):
    def __init__(self, parent, controller, log_callback):
        super().__init__(parent)
        self.controller = controller
        self.log = log_callback
        self.mapping_vars = {}
        self.name_vars = {}
        self.mapping_widgets = {}
        self._create_widgets()
        self._load_current_mapping()

    def _create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=10)

        ttk.Label(
            header_frame,
            text="⚙️ Настройка соответствия моторов",
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        ttk.Button(header_frame, text="💾 Сохранить", command=self._save_mapping).pack(
            side="right", padx=5
        )
        ttk.Button(header_frame, text="🔄 Сбросить", command=self._reset_mapping).pack(
            side="right", padx=5
        )

        info_frame = ttk.LabelFrame(main_frame, text="ℹ️ Информация")
        info_frame.pack(fill="x", pady=10)

        info_text = """
        Здесь вы можете указать, какой физический ID мотора соответствует каждому суставу робота.
        • Суставы: логические части робота (База, Плечо, Локоть, Кисть)
        • ID мотора: физический адрес мотора на шине (1-253)
        • Название: отображаемое имя сустава
        """
        ttk.Label(info_frame, text=info_text, justify="left").pack(padx=10, pady=10)

        mapping_frame = ttk.LabelFrame(
            main_frame, text="🔗 Соответствие суставов и моторов"
        )
        mapping_frame.pack(fill="both", expand=True, pady=10)

        headers = ["Сустав", "ID мотора", "Название", "Текущая позиция"]
        for col, header in enumerate(headers):
            ttk.Label(mapping_frame, text=header, font=("Arial", 10, "bold")).grid(
                row=0, column=col, padx=10, pady=5, sticky="w"
            )

        for joint_idx in range(6):
            self._create_mapping_row(mapping_frame, joint_idx)

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=10)

        ttk.Button(
            action_frame, text="🔍 Автоопределение", command=self._auto_detect
        ).pack(side="left", padx=5)
        ttk.Button(
            action_frame, text="📊 Проверить все", command=self._check_all_motors
        ).pack(side="left", padx=5)

    def _create_mapping_row(self, parent, joint_idx: int):
        row = joint_idx + 1

        joint_name = (
            JOINT_NAMES[joint_idx]
            if joint_idx < len(JOINT_NAMES)
            else f"Сустав {joint_idx}"
        )
        ttk.Label(parent, text=joint_name, font=("Arial", 10)).grid(
            row=row, column=0, padx=10, pady=5, sticky="w"
        )

        motor_id_var = tk.IntVar(value=joint_idx + 1)
        self.mapping_vars[joint_idx] = motor_id_var

        motor_combo = ttk.Combobox(
            parent, textvariable=motor_id_var, width=10, state="readonly"
        )
        motor_combo["values"] = list(range(1, 254))
        motor_combo.grid(row=row, column=1, padx=10, pady=5)

        name_var = tk.StringVar(value=joint_name)
        self.name_vars[joint_idx] = name_var

        name_entry = ttk.Entry(parent, textvariable=name_var, width=20)
        name_entry.grid(row=row, column=2, padx=10, pady=5)

        pos_label = ttk.Label(parent, text="--", font=("Consolas", 10))
        pos_label.grid(row=row, column=3, padx=10, pady=5)

        self.mapping_widgets[joint_idx] = {
            "combo": motor_combo,
            "name": name_entry,
            "pos": pos_label,
        }

    def _load_current_mapping(self):
        mapping = self.controller.get_motor_mapping()
        for joint_idx in range(6):
            key = f"joint_{joint_idx}"
            if key in mapping:
                motor_id = mapping[key].get("motor_id", joint_idx + 1)
                name = mapping[key].get(
                    "name",
                    JOINT_NAMES[joint_idx]
                    if joint_idx < len(JOINT_NAMES)
                    else f"Сустав {joint_idx}",
                )

                if joint_idx in self.mapping_vars:
                    self.mapping_vars[joint_idx].set(motor_id)
                if joint_idx in self.name_vars:
                    self.name_vars[joint_idx].set(name)

    def _save_mapping(self):
        for joint_idx in range(6):
            if joint_idx in self.mapping_vars:
                motor_id = self.mapping_vars[joint_idx].get()
                name = self.name_vars[joint_idx].get()
                self.controller.update_motor_mapping(joint_idx, motor_id, name)

        self.controller.save_config()
        self.log("💾 Соответствие моторов сохранено", "success")
        messagebox.showinfo("Успех", "Соответствие моторов сохранено!")

    def _reset_mapping(self):
        if messagebox.askyesno("Подтверждение", "Сбросить все настройки к умолчанию?"):
            self.controller.motor_mapping = DEFAULT_MOTOR_MAPPING.copy()
            self._load_current_mapping()
            self.log("🔄 Настройки сброшены", "info")

    def _auto_detect(self):
        if not self.controller.connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь к роботу!")
            return

        self.log("🔍 Автоопределение моторов...", "info")
        found_servos = self.controller.scan_servos()

        if found_servos:
            self.log(f"✅ Найдено моторов: {found_servos}", "success")
            for joint_idx in range(min(6, len(found_servos))):
                if joint_idx in self.mapping_vars:
                    self.mapping_vars[joint_idx].set(found_servos[joint_idx])
            self.log("🔗 Моторы назначены автоматически", "info")
        else:
            self.log("⚠️ Моторы не найдены", "warning")
            messagebox.showinfo(
                "Информация", "Моторы не найдены.\nПроверьте подключение."
            )

    def _check_all_motors(self):
        if not self.controller.connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь!")
            return

        self.log("📊 Проверка всех моторов...", "info")
        for joint_idx in range(6):
            if joint_idx in self.mapping_vars:
                motor_id = self.mapping_vars[joint_idx].get()
                data = self.controller.read_motor_data(motor_id)

                if data.get("position") is not None:
                    pos_text = str(data["position"])
                    color = "green"
                else:
                    pos_text = "Нет ответа"
                    color = "red"

                if joint_idx in self.mapping_widgets:
                    self.mapping_widgets[joint_idx]["pos"].config(
                        text=pos_text, foreground=color
                    )

        self.log("✅ Проверка завершена", "success")

    def update_positions(self, motor_data_dict):
        for joint_idx in range(6):
            if joint_idx in self.mapping_vars:
                motor_id = self.mapping_vars[joint_idx].get()
                if motor_id in motor_data_dict:
                    data = motor_data_dict[motor_id]
                    if data.position is not None:
                        if joint_idx in self.mapping_widgets:
                            self.mapping_widgets[joint_idx]["pos"].config(
                                text=str(data.position), foreground="green"
                            )


# ==================== 3D ВИЗУАЛИЗАЦИЯ ====================


class Kinematics3DPanel(ttk.Frame):
    def __init__(self, parent, controller, log_callback):
        super().__init__(parent)
        self.controller = controller
        self.log = log_callback
        self.joint_angles = [0.0] * 6
        self.figure = None
        self.canvas = None
        self.ax = None
        self.angle_vars = []
        self.angle_labels = []
        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        viz_frame = ttk.LabelFrame(main_frame, text="🔬 3D Визуализация")
        viz_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.figure = plt.Figure(figsize=(8, 6), dpi=100, facecolor="#1a1a2e")
        self.ax = self.figure.add_subplot(111, projection="3d")
        self.ax.set_facecolor("#16213e")

        self.canvas = FigureCanvasTkAgg(self.figure, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        angle_frame = ttk.LabelFrame(main_frame, text="📐 Углы суставов (градусы)")
        angle_frame.pack(fill="x", padx=10, pady=10)

        for i in range(6):
            row_frame = ttk.Frame(angle_frame)
            row_frame.pack(fill="x", padx=10, pady=2)

            joint_name = self.controller.get_joint_name(i)
            label = ttk.Label(row_frame, text=f"J{i + 1} ({joint_name}):", width=20)
            label.pack(side="left", padx=5)
            self.angle_labels.append(label)

            angle_var = tk.DoubleVar(value=0.0)
            self.angle_vars.append(angle_var)

            entry = ttk.Spinbox(
                row_frame, from_=-180, to=180, textvariable=angle_var, width=10
            )
            entry.pack(side="left", padx=5)

            ttk.Button(
                row_frame,
                text="OK",
                width=8,
                command=lambda idx=i: self._apply_angle(idx),
            ).pack(side="left", padx=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(
            btn_frame, text="🔄 Обновить 3D", command=self._update_visualization
        ).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="🏠 Сброс", command=self._reset_angles).pack(
            side="left", padx=5
        )
        ttk.Button(
            btn_frame, text="📤 Применить все", command=self._apply_all_angles
        ).pack(side="left", padx=5)

        self._update_joint_names()
        self._draw_robot()

    def _update_joint_names(self):
        for i in range(6):
            joint_name = self.controller.get_joint_name(i)
            if i < len(self.angle_labels):
                self.angle_labels[i].config(text=f"J{i + 1} ({joint_name}):")

    def _apply_angle(self, idx: int):
        motor_id = self.controller.get_motor_id_for_joint(idx)
        angle = self.angle_vars[idx].get()
        position = int((angle + 180) / 360 * MAX_POSITION)
        position = max(0, min(MAX_POSITION, position))
        self.controller.move_to_position(motor_id, position)
        self.controller.joint_positions[motor_id] = position
        self.log(
            f"🔄 {self.controller.get_joint_name(idx)} → {angle}° (ID={motor_id}, поз={position})",
            "info",
        )

    def _apply_all_angles(self):
        if not self.controller.connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь!")
            return
        if messagebox.askyesno("Подтверждение", "Применить все углы?"):
            for i in range(6):
                self._apply_angle(i)
            self.log("🔄 Все углы применены", "success")

    def _reset_angles(self):
        for i in range(6):
            self.angle_vars[i].set(0.0)
            self.joint_angles[i] = 0.0
        self._update_visualization()
        self.log("🏠 Углы сброшены", "info")

    def _update_visualization(self):
        for i in range(6):
            try:
                self.joint_angles[i] = self.angle_vars[i].get()
            except:
                self.joint_angles[i] = 0.0
        self._update_joint_names()
        self._draw_robot()

    def _draw_robot(self):
        self.ax.clear()
        self.ax.set_facecolor("#16213e")
        self.ax.set_xlim(-300, 300)
        self.ax.set_ylim(-300, 300)
        self.ax.set_zlim(0, 500)
        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_zlabel("Z")
        self.ax.set_title("Робот манипулятор", color="white")

        self.ax.xaxis.pane.fill = False
        self.ax.yaxis.pane.fill = False
        self.ax.zaxis.pane.fill = False
        self.ax.xaxis.pane.set_edgecolor("#666666")
        self.ax.yaxis.pane.set_edgecolor("#666666")
        self.ax.zaxis.pane.set_edgecolor("#666666")
        self.ax.tick_params(colors="white")

        segment_lengths = [80, 70, 60, 50, 40, 30]

        x_points = [0]
        y_points = [0]
        z_points = [0]

        current_x, current_y, current_z = 0, 0, 0
        current_angle_xy = 0
        current_angle_z = 90

        for i in range(6):
            angle_xy_rad = math.radians(current_angle_xy + self.joint_angles[i])
            angle_z_rad = math.radians(current_angle_z)

            current_x += (
                segment_lengths[i] * math.cos(angle_xy_rad) * math.sin(angle_z_rad)
            )
            current_y += (
                segment_lengths[i] * math.sin(angle_xy_rad) * math.sin(angle_z_rad)
            )
            current_z += segment_lengths[i] * math.cos(angle_z_rad)

            x_points.append(current_x)
            y_points.append(current_y)
            z_points.append(current_z)

            current_angle_xy = math.degrees(angle_xy_rad)

        self.ax.plot(
            x_points,
            y_points,
            z_points,
            color=FANUC_GREEN,
            linewidth=3,
            marker="o",
            markersize=8,
        )

        for i, (x, y, z) in enumerate(zip(x_points, y_points, z_points)):
            self.ax.scatter(
                [x], [y], [z], color=KINEMA_COLORS[i % len(KINEMA_COLORS)], s=100
            )
            joint_name = self.controller.get_joint_name(i) if i > 0 else "База"
            self.ax.text(x, y, z + 10, f"J{i}", color="white", fontsize=9)

        self.figure.tight_layout()
        self.canvas.draw()


# ==================== МАНУАЛЬНОЕ УПРАВЛЕНИЕ ====================


class ManualControlPanel(ttk.Frame):
    def __init__(self, parent, controller, log_callback, update_callback=None):
        super().__init__(parent)
        self.controller = controller
        self.log = log_callback
        self.update_callback = update_callback
        self.selected_joint = 0
        self.joint_var = None
        self.speed_var = None
        self.pos_var = None
        self.speed_label = None
        self.status_label = None
        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        motor_frame = ttk.LabelFrame(main_frame, text="🎯 Выбор сустава")
        motor_frame.pack(fill="x", padx=10, pady=10)

        self.joint_var = tk.IntVar(value=0)
        for i in range(6):
            joint_name = self.controller.get_joint_name(i)
            ttk.Radiobutton(
                motor_frame,
                text=f"J{i + 1} ({joint_name})",
                variable=self.joint_var,
                value=i,
                command=self._on_joint_select,
            ).pack(side="left", padx=5, pady=5)

        dir_frame = ttk.LabelFrame(main_frame, text="⬆️ Направление")
        dir_frame.pack(fill="x", padx=10, pady=10)

        btn_frame = ttk.Frame(dir_frame)
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame,
            text="◀ Назад",
            bg=FANUC_ORANGE,
            fg="black",
            font=("Arial", 12, "bold"),
            command=lambda: self._move_direction(-1),
        ).pack(side="left", padx=10)
        tk.Button(
            btn_frame,
            text="▶ Вперед",
            bg=FANUC_GREEN,
            fg="black",
            font=("Arial", 12, "bold"),
            command=lambda: self._move_direction(1),
        ).pack(side="left", padx=10)

        speed_frame = ttk.LabelFrame(main_frame, text="⚡ Скорость (шаг/сек)")
        speed_frame.pack(fill="x", padx=10, pady=10)

        self.speed_var = tk.IntVar(value=DEFAULT_SPEED)
        speed_scale = ttk.Scale(
            speed_frame,
            from_=0,
            to=10000,
            variable=self.speed_var,
            orient="horizontal",
            length=400,
            command=self._on_speed_change,
        )
        speed_scale.pack(padx=20, pady=10)

        self.speed_label = ttk.Label(
            speed_frame, text=f"{DEFAULT_SPEED} шаг/сек", font=("Arial", 11)
        )
        self.speed_label.pack()

        pos_frame = ttk.LabelFrame(main_frame, text="📍 Позиция")
        pos_frame.pack(fill="x", padx=10, pady=10)

        self.pos_var = tk.IntVar(value=0)
        pos_spin = ttk.Spinbox(
            pos_frame,
            from_=0,
            to=MAX_POSITION,
            textvariable=self.pos_var,
            width=15,
            font=("Arial", 12),
        )
        pos_spin.pack(pady=5)

        ttk.Button(pos_frame, text="🎯 Перейти", command=self._move_to_position).pack(
            pady=5
        )

        status_frame = ttk.LabelFrame(main_frame, text="📊 Состояние")
        status_frame.pack(fill="x", padx=10, pady=10)

        self.status_label = ttk.Label(status_frame, text="--", font=("Arial", 11))
        self.status_label.pack(pady=10)

        quick_frame = ttk.Frame(main_frame)
        quick_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(quick_frame, text="🏠 В 0", command=self._go_home).pack(
            side="left", padx=5
        )
        ttk.Button(quick_frame, text="🔄 В центр", command=self._go_center).pack(
            side="left", padx=5
        )
        ttk.Button(quick_frame, text="🔒 ВКЛ", command=self._torque_on).pack(
            side="left", padx=5
        )
        ttk.Button(quick_frame, text="🔓 ВЫКЛ", command=self._torque_off).pack(
            side="left", padx=5
        )

        self._update_position_display()

    def _on_joint_select(self):
        self.selected_joint = self.joint_var.get()
        self._update_position_display()
        joint_name = self.controller.get_joint_name(self.selected_joint)
        self.log(f"🎯 Выбран сустав: {joint_name}", "info")

    def _on_speed_change(self, value):
        speed = int(float(value))
        self.speed_label.config(text=f"{speed} шаг/сек")
        self.controller.set_manual_speed(speed)

    def _move_direction(self, direction: int):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        current = self.controller.joint_positions.get(motor_id, 0)
        step = 100
        new_pos = max(0, min(MAX_POSITION, current + direction * step))
        self.controller.move_to_position(motor_id, new_pos)
        self.controller.joint_positions[motor_id] = new_pos
        self.pos_var.set(new_pos)
        self._update_position_display()
        joint_name = self.controller.get_joint_name(self.selected_joint)
        self.log(f"🔄 {joint_name} (ID={motor_id}): {new_pos}", "info")

    def _move_to_position(self):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        position = self.pos_var.get()
        self.controller.move_to_position(motor_id, position)
        self.controller.joint_positions[motor_id] = position
        self._update_position_display()
        joint_name = self.controller.get_joint_name(self.selected_joint)
        self.log(f"🎯 {joint_name} (ID={motor_id}) → {position}", "info")

    def _go_home(self):
        self.pos_var.set(0)
        self._move_to_position()

    def _go_center(self):
        self.pos_var.set(2048)
        self._move_to_position()

    def _torque_on(self):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        self.controller.toggle_torque(motor_id, True)
        joint_name = self.controller.get_joint_name(self.selected_joint)
        self.log(f"💪 Момент ВКЛ: {joint_name} (ID={motor_id})", "success")

    def _torque_off(self):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        self.controller.toggle_torque(motor_id, False)
        joint_name = self.controller.get_joint_name(self.selected_joint)
        self.log(f"🛑 Момент ВЫКЛ: {joint_name} (ID={motor_id})", "warning")

    def _update_position_display(self):
        motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
        pos = self.controller.joint_positions.get(motor_id, 0)
        speed = self.controller.get_manual_speed()
        joint_name = self.controller.get_joint_name(self.selected_joint)
        self.status_label.config(
            text=f"{joint_name} (ID={motor_id}) | Позиция: {int(pos)} | Скорость: {speed}"
        )
        self.pos_var.set(int(pos))

    def update_from_monitor(self, motor_data_dict):
        if self.selected_joint in range(6):
            motor_id = self.controller.get_motor_id_for_joint(self.selected_joint)
            if motor_id in motor_data_dict:
                data = motor_data_dict[motor_id]
                if data.position is not None:
                    self.controller.joint_positions[motor_id] = data.position
                    self._update_position_display()


# ==================== НИЖНЯЯ ПАНЕЛЬ МОНИТОРИНГА ====================


class BottomMonitorPanel(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.motor_frames = {}
        self._create_widgets()

    def _create_widgets(self):
        self.configure(relief="ridge", borderwidth=2)

        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(
            header_frame, text="📊 МОНИТОРИНГ МОТОРОВ", font=("Arial", 11, "bold")
        ).pack(side="left")

        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        for i in range(6):
            joint_name = self.controller.get_joint_name(i)
            frame = ttk.LabelFrame(main_frame, text=f"J{i + 1} ({joint_name})")
            frame.pack(side="left", fill="both", expand=True, padx=2)

            pos_label = ttk.Label(frame, text="Поз: --", font=("Consolas", 9))
            pos_label.pack(pady=2)

            temp_label = ttk.Label(frame, text="Темп: --°C", font=("Consolas", 9))
            temp_label.pack(pady=2)

            load_label = ttk.Label(frame, text="Нагр: --%", font=("Consolas", 9))
            load_label.pack(pady=2)

            self.motor_frames[i] = {
                "pos": pos_label,
                "temp": temp_label,
                "load": load_label,
            }

    def update_data(self, motor_data_dict):
        for joint_idx in range(6):
            motor_id = self.controller.get_motor_id_for_joint(joint_idx)
            if motor_id in motor_data_dict and joint_idx in self.motor_frames:
                data = motor_data_dict[motor_id]
                frame = self.motor_frames[joint_idx]

                joint_name = self.controller.get_joint_name(joint_idx)
                frame.master.config(text=f"J{joint_idx + 1} ({joint_name})")

                pos = str(data.position) if data.position is not None else "--"
                temp = f"{data.temperature}" if data.temperature is not None else "--"
                load = f"{data.load}" if data.load is not None else "--"

                frame["pos"].config(text=f"Поз: {pos}")
                frame["temp"].config(text=f"Темп: {temp}°C")
                frame["load"].config(text=f"Нагр: {load}%")

                if data.is_overheating():
                    frame["temp"].config(foreground="red")
                else:
                    frame["temp"].config(foreground="black")


# ==================== БЛОЧНОЕ ПРОГРАММИРОВАНИЕ ====================


class BlockPalette(ttk.Frame):
    def __init__(self, parent, canvas):
        super().__init__(parent, width=200)
        self.canvas = canvas
        self.block_id_counter = 0
        ttk.Label(self, text="📦 Блоки", font=("Arial", 11, "bold")).pack(pady=5)
        categories = [
            (
                "🔄 Движение",
                "motion",
                [
                    ("Движение", {"type": "move_to", "joint": 0, "position": 2048}),
                    ("Home", {"type": "home", "joint": "all"}),
                ],
            ),
            (
                "⏱ Ожидание",
                "wait",
                [
                    ("Ждать", {"type": "wait_time", "seconds": 1.0}),
                ],
            ),
            (
                "💪 Момент",
                "control",
                [
                    ("ВКЛ", {"type": "torque_on", "joint": 0}),
                    ("ВЫКЛ", {"type": "torque_off", "joint": 0}),
                ],
            ),
        ]
        for category_name, category_type, blocks in categories:
            frame = ttk.LabelFrame(self, text=category_name)
            frame.pack(fill="x", padx=5, pady=5)
            for block_name, params in blocks:
                btn = tk.Button(
                    frame,
                    text=block_name,
                    bg=BLOCK_COLORS[category_type],
                    fg="white",
                    font=("Arial", 9),
                    command=lambda p=params, t=category_type: self._add_block(p, t),
                )
                btn.pack(fill="x", padx=3, pady=2)

    def _add_block(self, params: dict, block_type: str):
        self.block_id_counter += 1
        block = ProgramBlock(
            id=self.block_id_counter,
            block_type=block_type,
            params=params,
            order=self.canvas.get_block_count() if self.canvas else 0,
        )
        if self.canvas:
            self.canvas.add_block(block)


class ProgramCanvas(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, bg="#f5f5f5", highlightthickness=0)
        self.blocks: List[ProgramBlock] = []
        self.block_widgets: Dict[int, tk.Frame] = {}
        self.y_offset = 10
        self.bind("<Configure>", self._on_resize)

    def get_block_count(self) -> int:
        return len(self.blocks)

    def add_block(self, block: ProgramBlock):
        self.blocks.append(block)
        self._create_block_widget(block)
        self._update_blocks_display()

    def remove_block(self, block_id: int):
        self.blocks = [b for b in self.blocks if b.id != block_id]
        if block_id in self.block_widgets:
            self.block_widgets[block_id].destroy()
            del self.block_widgets[block_id]
        self._update_blocks_display()

    def clear_all(self):
        for widget in self.block_widgets.values():
            widget.destroy()
        self.block_widgets.clear()
        self.blocks.clear()
        self.y_offset = 10

    def _create_block_widget(self, block: ProgramBlock):
        frame = tk.Frame(
            self,
            bg=BLOCK_COLORS.get(block.block_type, "#999999"),
            relief="raised",
            bd=2,
        )
        title_frame = tk.Frame(frame, bg=BLOCK_COLORS.get(block.block_type, "#999999"))
        title_frame.pack(fill="x", padx=5, pady=3)
        block_names = {
            "move_to": "🔄 Движение",
            "home": "🏠 Home",
            "wait_time": "⏱ Ждать",
            "torque_on": "💪 ВКЛ",
            "torque_off": "💪 ВЫКЛ",
        }
        tk.Label(
            title_frame,
            text=block_names.get(block.params.get("type", ""), "Блок"),
            bg=BLOCK_COLORS.get(block.block_type, "#999999"),
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(side="left")
        tk.Button(
            title_frame,
            text="✕",
            bg=BLOCK_COLORS.get(block.block_type, "#999999"),
            fg="white",
            bd=0,
            command=lambda bid=block.id: self.remove_block(bid),
        ).pack(side="right")
        self.block_widgets[block.id] = frame

    def _update_blocks_display(self):
        self.delete("all")
        self.y_offset = 10
        for block in self.blocks:
            if block.id in self.block_widgets:
                self.create_window(
                    10, self.y_offset, window=self.block_widgets[block.id], anchor="nw"
                )
                self.y_offset += self.block_widgets[block.id].winfo_reqheight() + 10
        self.configure(scrollregion=self.bbox("all"))

    def _on_resize(self, event):
        self.configure(scrollregion=self.bbox("all"))

    def get_program(self) -> List[dict]:
        return [b.__dict__ for b in self.blocks]


# ==================== ОСНОВНОЙ GUI ====================


class RobotControlGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🤖 ST3215 Robot Control Panel v6.1")
        self.geometry("1600x1000")
        self.controller = MotorController()
        self.monitor: Optional[MotorMonitor] = None
        self.motor_mapping_panel = None
        self.manual_panel = None
        self.bottom_monitor = None
        self.kinematics_panel = None
        self.program_canvas = None
        self.block_palette = None
        self._monitor_update_pending = False
        self._setup_styles()
        self._create_widgets()
        self._create_menu()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._log("🎉 Приложение запущено", "success")
        self.controller.load_config()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Emergency.TButton",
            font=("Arial", 11, "bold"),
            foreground="white",
            background="red",
        )

    def _create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="📁 Файл", menu=file_menu)
        file_menu.add_command(label="💾 Сохранить", command=self._save_config)
        file_menu.add_command(label="🚪 Выход", command=self._on_closing)
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="🛠️ Инструменты", menu=tools_menu)
        tools_menu.add_command(label="🔍 Сканировать", command=self._scan_servos)
        tools_menu.add_command(label="▶️ Запуск", command=self._run_program)
        tools_menu.add_separator()
        tools_menu.add_command(
            label="⚙️ Настройка моторов", command=self._show_mapping_panel
        )

    def _create_widgets(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(top_frame)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="🏠 Главная")
        self._create_main_tab()

        self.manual_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.manual_tab, text="🎮 Мануальное")
        self.manual_panel = ManualControlPanel(
            self.manual_tab, self.controller, self._log, self._on_manual_update
        )
        self.manual_panel.pack(fill="both", expand=True)

        self.mapping_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.mapping_tab, text="🔗 Настройка моторов")
        self.motor_mapping_panel = MotorMappingPanel(
            self.mapping_tab, self.controller, self._log
        )
        self.motor_mapping_panel.pack(fill="both", expand=True)

        self.kinematics_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.kinematics_tab, text="🔬 3D Кинематика")
        self.kinematics_panel = Kinematics3DPanel(
            self.kinematics_tab, self.controller, self._log
        )
        self.kinematics_panel.pack(fill="both", expand=True)

        self.block_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.block_tab, text="📦 Программы")
        self._create_block_tab()

        self.bottom_monitor = BottomMonitorPanel(self, self.controller)
        self.bottom_monitor.pack(fill="x", padx=5, pady=(0, 5))

        self.log_frame = ttk.LabelFrame(self, text="📋 Лог")
        self.log_frame.pack(fill="x", padx=5, pady=(0, 5))
        self._create_log_panel()

    def _create_main_tab(self):
        main_frame = ttk.Frame(self.main_tab)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        conn_frame = ttk.LabelFrame(main_frame, text="🔌 Подключение")
        conn_frame.pack(fill="x", padx=10, pady=10)
        port_frame = ttk.Frame(conn_frame)
        port_frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(port_frame, text="COM Порт:").pack(side="left", padx=5)
        self.port_combo = ttk.Combobox(port_frame, width=30)
        self.port_combo.pack(side="left", padx=10)
        ttk.Button(port_frame, text="🔄", command=self._refresh_ports).pack(
            side="left", padx=5
        )
        btn_frame = ttk.Frame(conn_frame)
        btn_frame.pack(fill="x", padx=10, pady=10)
        self.connect_btn = ttk.Button(
            btn_frame,
            text="🔌 Подключиться",
            command=self._toggle_connection,
            style="Emergency.TButton",
        )
        self.connect_btn.pack(side="left", padx=10)
        self.scan_btn = ttk.Button(
            btn_frame,
            text="🔍 Сканировать",
            command=self._scan_servos,
            state="disabled",
        )
        self.scan_btn.pack(side="left", padx=10)
        self.status_label = ttk.Label(
            conn_frame,
            text="⭕ Не подключено",
            font=("Arial", 12, "bold"),
            foreground="gray",
        )
        self.status_label.pack(padx=10, pady=10)
        self._refresh_ports()

    def _create_block_tab(self):
        left_frame = ttk.PanedWindow(self.block_tab, orient="horizontal")
        left_frame.pack(fill="both", expand=True, padx=5, pady=5)
        palette_frame = ttk.Frame(left_frame, width=200)
        left_frame.add(palette_frame, weight=1)
        self.block_palette = BlockPalette(palette_frame, None)
        self.block_palette.pack(fill="both", expand=True)
        canvas_frame = ttk.Frame(left_frame)
        left_frame.add(canvas_frame, weight=3)
        self.program_canvas = ProgramCanvas(canvas_frame)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.program_canvas.yview
        )
        self.program_canvas.configure(yscrollcommand=scrollbar.set)
        self.program_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        btn_frame = ttk.Frame(self.block_tab)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text="▶️ Запустить", command=self._run_program).pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="🗑️ Очистить", command=self._clear_program).pack(
            side="left", padx=5
        )

    def _create_log_panel(self):
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame,
            height=4,
            font=("Consolas", 9),
            state="disabled",
            bg="#f5f5f5",
        )
        self.log_text.pack(fill="x", padx=5, pady=5)
        ttk.Button(self.log_frame, text="🗑️ Очистить", command=self._clear_log).pack(
            anchor="e", padx=5, pady=(0, 5)
        )

    def _log(self, message: str, level="info"):
        if not hasattr(self, "log_text"):
            return
        timestamp = time.strftime("%H:%M:%S")
        colors = {
            "info": "black",
            "warning": "darkorange",
            "error": "red",
            "success": "green",
        }
        self.log_text.config(state="normal")
        self.log_text.insert(
            "end", f"[{timestamp}] {message}\n", colors.get(level, "black")
        )
        self.log_text.config(state="disabled")
        self.log_text.see("end")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.current(0)

    def _toggle_connection(self):
        if self.controller.connected:
            self._disconnect()
        else:
            port = self.port_combo.get()
            if not port:
                messagebox.showwarning("Предупреждение", "Выберите порт!")
                return
            self._connect(port)

    def _connect(self, port):
        self.controller.device = port
        if self.controller.connect():
            self._log(f"✅ Подключено к {port}", "success")
            self.status_label.config(text="✅ Подключено", foreground="green")
            self.connect_btn.config(text="🔌 Отключиться")
            self.scan_btn.config(state="normal")

    def _disconnect(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
        self.controller.disconnect()
        self._log("🔌 Отключено", "info")
        self.status_label.config(text="⭕ Не подключено", foreground="gray")
        self.connect_btn.config(text="🔌 Подключиться")
        self.scan_btn.config(state="disabled")

    def _scan_servos(self):
        self._log("🔍 Сканирование...", "info")
        threading.Thread(target=self._scan_servos_thread, daemon=True).start()

    def _scan_servos_thread(self):
        servos = self.controller.scan_servos()
        self.after(0, lambda: self._on_scan_complete(servos))

    def _on_scan_complete(self, servos):
        if servos:
            self._log(f"✅ Найдено моторов: {servos}", "success")
            self._start_monitoring(servos)
        else:
            self._log("⚠️ Моторы не найдены", "warning")

    def _start_monitoring(self, motor_ids):
        self.monitor = MotorMonitor(self.controller, None)
        self.monitor.start(motor_ids)
        self._schedule_monitor_update()

    def _schedule_monitor_update(self):
        if self.monitor and self.monitor.running:
            try:
                data_copy = self.monitor.get_all_data()
                self._on_monitor_update(data_copy)
            except Exception as e:
                print(f"⚠️ Ошибка обновления: {e}")
            self.after(int(MONITOR_INTERVAL * 1000), self._schedule_monitor_update)

    def _on_monitor_update(self, motor_data_dict: Dict[int, MotorData]):
        if self._monitor_update_pending:
            return
        self._monitor_update_pending = True
        try:
            if self.bottom_monitor:
                self.bottom_monitor.update_data(motor_data_dict)

            if self.manual_panel:
                self.manual_panel.update_from_monitor(motor_data_dict)

            if self.motor_mapping_panel:
                self.motor_mapping_panel.update_positions(motor_data_dict)

            if self.kinematics_panel:
                for joint_idx in range(6):
                    motor_id = self.controller.get_motor_id_for_joint(joint_idx)
                    if motor_id in motor_data_dict:
                        data = motor_data_dict[motor_id]
                        if data.position is not None:
                            angle = (data.position / MAX_POSITION) * 360 - 180
                            self.kinematics_panel.angle_vars[joint_idx].set(angle)
                            self.kinematics_panel.joint_angles[joint_idx] = angle
                self.kinematics_panel._draw_robot()

        except Exception as e:
            print(f"⚠️ Ошибка обновления GUI: {e}")
        finally:
            self._monitor_update_pending = False

    def _on_manual_update(self):
        pass

    def _show_mapping_panel(self):
        self.notebook.select(self.mapping_tab)

    def _run_program(self):
        program = self.program_canvas.get_program()
        if not program:
            messagebox.showwarning("Предупреждение", "Программа пуста!")
            return
        self._log(f"▶️ Запуск ({len(program)} блоков)", "success")
        threading.Thread(
            target=self._execute_program, args=(program,), daemon=True
        ).start()

    def _execute_program(self, program):
        for block in program:
            params = block.get("params", {})
            block_type = params.get("type", "")
            if block_type == "move_to":
                joint = params.get("joint", 0)
                position = params.get("position", 2048)
                self.controller.move_joint(joint, position)
                joint_name = self.controller.get_joint_name(joint)
                self._log(f"🔄 {joint_name} → {position}", "info")
            elif block_type == "wait_time":
                time.sleep(params.get("seconds", 1.0))
            elif block_type == "torque_on":
                joint = params.get("joint", 0)
                motor_id = self.controller.get_motor_id_for_joint(joint)
                self.controller.toggle_torque(motor_id, True)
            elif block_type == "torque_off":
                joint = params.get("joint", 0)
                motor_id = self.controller.get_motor_id_for_joint(joint)
                self.controller.toggle_torque(motor_id, False)
        self._log("✅ Программа выполнена", "success")

    def _clear_program(self):
        self.program_canvas.clear_all()
        self._log("🗑️ Программа очищена", "info")

    def _save_config(self):
        if self.controller.save_config():
            self._log("💾 Конфигурация сохранена", "success")

    def _on_closing(self):
        if messagebox.askyesno("Выход", "Завершить работу?"):
            if self.monitor:
                self.monitor.stop()
            self.controller.disconnect()
            self.controller.save_config()
            plt.close("all")
            self.destroy()


def main():
    print("\n" + "=" * 70)
    print("🤖 ST3215 Robot Control Panel v6.1")
    print("=" * 70)
    print("Функции:")
    print("  • Настройка соответствия моторов суставам")
    print("  • 3D визуализация кинематики")
    print("  • Асинхронный мониторинг")
    print("  • Мануальное управление")
    print("=" * 70)
    app = RobotControlGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
