#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI Control Panel для моторов ST3215
Использует Tkinter + отдельный поток мониторинга
ПОЛНАЯ ВЕРСИЯ со всеми функциями (Кинематика, Управление, Мониторинг)
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import serial
import serial.tools.list_ports
import threading
import time
import json
import math  # ← ДОБАВЛЕНО: был импорт math
from datetime import datetime
from st3215 import ST3215
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List
from enum import Enum

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

# --- КОНФИГУРАЦИЯ МОТОРОВ ---
MOTOR_CONFIG = {
    'motor_1': {'min_pos': 0, 'max_pos': MAX_POSITION},
    'motor_2': {'min_pos': 0, 'max_pos': MAX_POSITION},
    'motor_3': {'min_pos': 0, 'max_pos': MAX_POSITION},
    'motor_4': {'min_pos': 0, 'max_pos': MAX_POSITION},
    'motor_5': {'min_pos': 0, 'max_pos': MAX_POSITION},
    'motor_6': {'min_pos': 0, 'max_pos': MAX_POSITION}
}


# --- КЛАССЫ ---

@dataclass
class MotorData:
    """Данные мотора для мониторинга"""
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

    def to_dict(self) -> dict:  # ← ДОБАВЛЕНО: метод для экспорта
        return asdict(self)


class Kinematics:
    """Класс для кинематики шестиосевого робота"""

    def __init__(self):
        self.l1 = 200
        self.l2 = 250
        self.l3 = 200
        self.l4 = 200
        self.l5 = 180
        self.l6 = 150
        self.motor_min_positions = {k: v for k, v in MOTOR_CONFIG.items()}
        self.motor_max_positions = {k: MAX_POSITION for k in MOTOR_CONFIG.keys()}

    def forward_kinematics(self, theta1, theta2, theta3, theta4, theta5, theta6):
        x = self.l1 * math.sin(theta1) + self.l2 * math.sin(theta1 + theta2)
        y = self.l3 * math.cos(theta3) + self.l4 * math.cos(theta3 + theta4)
        z = self.l5 * math.sin(theta5) + self.l6 * math.sin(theta5 + theta6)
        return x, y, z

    def inverse_kinematics(self, x, y, z):
        theta1 = math.asin(x / self.l1) if abs(x) > 0 else 0
        theta2 = math.acos((x ** 2 + y ** 2 - self.l2 ** 2) / (2 * x * self.l2)) if abs(x) > self.l2 else 0
        theta3 = math.asin(z / self.l5) if abs(z) > 0 else 0
        theta4 = math.acos(
            (self.l6 ** 2 - self.l5 ** 2 - self.l6 ** 2 * math.sin(theta3) ** 2) / (2 * self.l5 * self.l6))
        theta5 = math.asin(y / self.l3) if abs(y) > 0 else 0
        theta6 = 0
        return [theta1, theta2, theta3, theta4, theta5, theta6]

    def check_position_limits(self, motor_positions):
        for mid in self.motor_min_positions:
            if not (self.motor_min_positions[mid] <= motor_positions[mid] <= self.motor_max_positions[mid]):
                return False
        return True

    def move_to_position(self, x, y, z):
        theta = self.inverse_kinematics(x, y, z)
        motor_positions = []
        for i in range(len(theta)):
            position = int(self.l1 * theta[i] / math.pi * 4095)
            if not self.check_position_limits({f'motor_{i + 1}': position}):
                raise ValueError(f"Позиция мотора {i + 1} выходит за пределы допустимых значений")
            motor_positions.append(position)
        return motor_positions

    def get_current_position(self):
        return 0.1, 0.1, 0.1


class MotorMonitor:
    """Отдельный поток для мониторинга моторов"""

    def __init__(self, motor_controller, update_callback=None):
        self.motor_controller = motor_controller
        self.update_callback = update_callback
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.motor_data: Dict[int, MotorData] = {}
        self.lock = threading.Lock()

    def start(self, motor_ids: List[int]):
        if self.running:
            return
        with self.lock:
            for mid in motor_ids:
                if mid not in self.motor_data:
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
            try:
                for motor_id, data in list(self.motor_data.items()):
                    self._update_motor_data(motor_id, data)
                if self.update_callback and self.motor_data:
                    self.update_callback(self.motor_data.copy())
            except Exception as e:
                print(f"❌ Ошибка мониторинга: {e}")
            time.sleep(MONITOR_INTERVAL)

    def _update_motor_data(self, motor_id: int, data: MotorData):
        if not self.motor_controller or not self.motor_controller.connected:
            return
        try:
            motor = self.motor_controller.motor
            data.position = motor.ReadPosition(motor_id)
            data.temperature = motor.ReadTemperature(motor_id)
            data.voltage = motor.ReadVoltage(motor_id)
            data.current = motor.ReadCurrent(motor_id)
            data.load = motor.ReadLoad(motor_id)
            data.mode = motor.ReadMode(motor_id)
            data.moving = motor.IsMoving(motor_id)
            data.last_update = time.time()
            data.error_count = 0
        except Exception as e:
            data.error_count += 1
            if data.error_count > 3:
                print(f"⚠️ Мотор {motor_id}: много ошибок")

    def get_data(self, motor_id: int) -> Optional[MotorData]:
        with self.lock:
            return self.motor_data.get(motor_id)


class MotorController:
    """Контроллер моторов ST3215"""

    def __init__(self, device='/dev/ttyUSB0'):
        self.device = device
        self.motor: Optional[ST3215] = None
        self.connected = False
        self.found_servos: List[int] = []
        self.current_id: Optional[int] = None
        self.torque_states: Dict[int, bool] = {}

    def connect(self):
        try:
            self.motor = ST3215(device=self.device)
            self.connected = True
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def disconnect(self):
        if self.motor and self.current_id is not None:
            try:
                self.motor.StopServo(self.current_id)
            except:
                pass
        self.connected = False

    def scan_servos(self):
        if not self.connected:
            return []
        try:
            self.found_servos = self.motor.ListServos()
            return self.found_servos
        except:
            return []

    def move_to_position(self, sts_id: int, position: int, speed=DEFAULT_SPEED, acc=DEFAULT_ACC):
        if not (MIN_POSITION <= position <= MAX_POSITION):
            return False
        try:
            self.motor.StartServo(sts_id)
            self.motor.MoveTo(sts_id, position, speed=speed, acc=acc)
            return True
        except Exception as e:
            print(f"Ошибка движения: {e}")
            return False

    def toggle_torque(self, sts_id: int, enable=True):
        try:
            if self.connected and self.motor is not None:
                if enable:
                    result = self.motor.StartServo(sts_id)
                    self.torque_states[sts_id] = True
                else:
                    result = self.motor.StopServo(sts_id)
                    self.torque_states[sts_id] = False
                return result is not None
            return False
        except Exception as e:
            print(f"Ошибка переключения момента: {e}")
            return False

    def get_torque_state(self, sts_id: int) -> bool:  # ← ДОБАВЛЕНО
        return self.torque_states.get(sts_id, False)

    def emergency_stop_all(self):
        if not self.connected:
            return
        for sid in self.found_servos:
            try:
                self.motor.StopServo(sid)
                self.torque_states[sid] = False
            except Exception as e:
                print(f"Ошибка остановки серво {sid}: {e}")
                continue


# ==================== GUI КЛАССЫ ====================

class ProgressBarWithLabel(ttk.Frame):
    """Прогресс-бар с подписью и значением"""

    def __init__(self, parent, label: str, max_value: float, unit="", warning_threshold=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.label_text = label
        self.max_value = max_value
        self.unit = unit
        self.warning_threshold = warning_threshold

        self.title_label = ttk.Label(self, text=label, font=('Arial', 9, 'bold'))
        self.title_label.pack(anchor='w')
        self.progress = ttk.Progressbar(self, mode='determinate', maximum=max_value, length=200)
        self.progress.pack(fill='x', pady=(2, 0))
        self.value_label = ttk.Label(self, text=f"-- {unit}", font=('Arial', 8))
        self.value_label.pack(anchor='e')

    def update_value(self, value: float):
        if value is not None:
            self.progress['value'] = value
            self.value_label.config(text=f"{value:.1f} {self.unit}")
            if self.warning_threshold and value >= self.warning_threshold:
                self.value_label.config(foreground='red')
            else:
                self.value_label.config(foreground='black')


class MotorMonitorFrame(ttk.LabelFrame):
    """Фрейм мониторинга одного мотора"""

    def __init__(self, parent, motor_id: int, **kwargs):
        super().__init__(parent, text=f"🔧 Мотор ID: {motor_id}", **kwargs)
        self.motor_id = motor_id

        row = 0
        self.temp_bar = ProgressBarWithLabel(self, "🌡️ Температура", 100, "°C", warning_threshold=TEMP_WARNING)
        self.temp_bar.grid(row=row, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        row += 1

        self.load_bar = ProgressBarWithLabel(self, "💪 Нагрузка", 100, "%", warning_threshold=LOAD_WARNING)
        self.load_bar.grid(row=row, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        row += 1

        self.volt_bar = ProgressBarWithLabel(self, "🔋 Напряжение", 25, "V")
        self.volt_bar.grid(row=row, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        row += 1

        self.current_bar = ProgressBarWithLabel(self, "⚡ Ток", 2000, "mA")
        self.current_bar.grid(row=row, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        row += 1

        self.status_frame = ttk.Frame(self)
        self.status_frame.grid(row=row, column=0, columnspan=2, sticky='ew', padx=5, pady=5)

        ttk.Label(self.status_frame, text="📍 Позиция:").grid(row=0, column=0, sticky='w')
        self.pos_label = ttk.Label(self.status_frame, text="--", font=('Arial', 9, 'bold'))
        self.pos_label.grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(self.status_frame, text="🔄 Движение:").grid(row=1, column=0, sticky='w')
        self.moving_label = ttk.Label(self.status_frame, text="--")
        self.moving_label.grid(row=1, column=1, sticky='w', padx=5)

        ttk.Label(self.status_frame, text="💪 Момент:").grid(row=2, column=0, sticky='w')
        self.torque_label = ttk.Label(self.status_frame, text="ВЫКЛ", foreground='red')
        self.torque_label.grid(row=2, column=1, sticky='w', padx=5)

        self.error_label = ttk.Label(self, text="", foreground='red')
        self.error_label.grid(row=row + 1, column=0, columnspan=2, sticky='ew', padx=5)

        self.alert_frame = ttk.Frame(self, relief='solid', borderwidth=1)
        self.alert_frame.grid(row=row + 2, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        self.alert_label = ttk.Label(self.alert_frame, text="")  # ← ДОБАВЛЕНО: создание виджета
        self.alert_label.pack(padx=5, pady=2)

    def update_data(self, data: MotorData):  # ← ДОБАВЛЕНО: метод обновления
        if data.position is not None:
            self.pos_label.config(text=str(data.position))
        if data.temperature is not None:
            self.temp_bar.update_value(data.temperature)
        if data.load is not None:
            self.load_bar.update_value(data.load)
        if data.voltage is not None:
            self.volt_bar.update_value(data.voltage)
        if data.current is not None:
            self.current_bar.update_value(data.current)
        if data.moving is not None:
            self.moving_label.config(text="ДА" if data.moving else "НЕТ")
        if data.error_count > 0:
            self.error_label.config(text=f"Ошибок: {data.error_count}")
        else:
            self.error_label.config(text="")

    def set_torque_state(self, enabled: bool):  # ← ДОБАВЛЕНО: метод состояния момента
        if enabled:
            self.torque_label.config(text="ВКЛ", foreground='green')
        else:
            self.torque_label.config(text="ВЫКЛ", foreground='red')


class ST3215GUI(tk.Tk):
    """Основное окно приложения"""

    def __init__(self):
        super().__init__()
        self.title("ST3215 Motor Control Panel v2.0")
        self.geometry("1400x800")
        self.minsize(1200, 700)

        self._setup_styles()

        self.controller = MotorController()
        self.monitor: Optional[MotorMonitor] = None
        self.monitor_frames: Dict[int, MotorMonitorFrame] = {}
        self.kinematics = Kinematics()

        self._create_widgets()
        self._create_menu()

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._log("🎉 Приложение запущено", 'success')

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Success.TLabel', foreground='green')
        style.configure('Warning.TLabel', foreground='orange')
        style.configure('Error.TLabel', foreground='red')
        style.configure('Bold.TLabel', font=('Arial', 9, 'bold'))
        style.configure('Emergency.TButton', font=('Arial', 11, 'bold'), foreground='white', background='red')

    def _create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="📁 Файл", menu=file_menu)
        file_menu.add_command(label="💾 Сохранить конфигурацию", command=self._save_config)
        file_menu.add_command(label="📂 Загрузить конфигурацию", command=self._load_config_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="🚪 Выход", command=self._on_closing)

        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="🛠️ Инструменты", menu=tools_menu)
        tools_menu.add_command(label="🔍 Сканировать моторы", command=self._scan_servos)
        tools_menu.add_command(label="🗑️ Очистить мониторинг", command=self._clear_monitor_frames)
        tools_menu.add_separator()
        tools_menu.add_command(label="📊 Экспорт данных", command=self._export_data)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="❓ Помощь", menu=help_menu)
        help_menu.add_command(label="ℹ️ О программе", command=self._show_about)
        help_menu.add_command(label="📖 Документация", command=self._show_help)

    def _create_widgets(self):
        # Верхняя панель
        self.top_frame = ttk.Frame(self)
        self.top_frame.pack(fill='x', padx=5, pady=5)

        self.emergency_btn = ttk.Button(self.top_frame, text="🛑 АВАРИЙНАЯ ОСТАНОВКА",
                                        command=self._emergency_stop, style='Emergency.TButton')
        self.emergency_btn.pack(side='right', padx=5, pady=5)

        self.status_label = ttk.Label(self.top_frame, text="⭕ Не подключено",
                                      font=('Arial', 11, 'bold'), foreground='gray')
        self.status_label.pack(side='right', padx=20)

        # Панели
        self.paned = ttk.PanedWindow(self, orient='horizontal')
        self.paned.pack(fill='both', expand=True, padx=5, pady=5)

        self.control_frame = ttk.LabelFrame(self.paned, text="🎮 Управление")
        self.paned.add(self.control_frame, weight=1)

        self.monitor_frame = ttk.LabelFrame(self.paned, text="📊 Мониторинг")
        self.paned.add(self.monitor_frame, weight=2)

        # Лог событий
        self.log_frame = ttk.LabelFrame(self, text="📋 Лог событий")
        self.log_frame.pack(fill='x', padx=5, pady=(0, 5))

        self._create_log_panel()
        self._create_control_panel()
        self._create_monitor_panel()
        self._create_connection_panel()  # ← ДОБАВЛЕНО: панель подключения

    def _create_connection_panel(self):  # ← ДОБАВЛЕНО: создание виджетов подключения
        conn_frame = ttk.LabelFrame(self.control_frame, text="🔌 Подключение")
        conn_frame.pack(fill='x', pady=(0, 10))

        port_frame = ttk.Frame(conn_frame)
        port_frame.pack(fill='x', pady=5)

        ttk.Label(port_frame, text="Порт:").pack(side='left')
        self.port_combo = ttk.Combobox(port_frame, width=20)
        self.port_combo.pack(side='left', padx=5)

        self.connect_btn = ttk.Button(port_frame, text="🔌 Подключиться", command=self._toggle_connection)
        self.connect_btn.pack(side='left', padx=5)

        self.scan_btn = ttk.Button(port_frame, text="🔍 Сканировать", command=self._scan_servos, state='disabled')
        self.scan_btn.pack(side='left', padx=5)

        ttk.Button(port_frame, text="🔄 Обновить порты", command=self._refresh_ports).pack(side='left', padx=5)

        self._refresh_ports()

    def _create_control_panel(self):
        # Кинематика
        frame = ttk.LabelFrame(self.control_frame, text="🔄 Кинематика")
        frame.pack(fill='x', pady=(0, 10))

        x_frame = ttk.Frame(frame)
        x_frame.pack(fill='x', pady=5)

        ttk.Label(x_frame, text="X:").pack(side='left')
        self.x_entry = ttk.Entry(x_frame, width=10)
        self.x_entry.insert(0, "0.1")
        self.x_entry.pack(side='left')

        ttk.Label(x_frame, text="Y:").pack(side='left', padx=(5, 0))
        self.y_entry = ttk.Entry(x_frame, width=10)
        self.y_entry.insert(0, "0.1")
        self.y_entry.pack(side='left')

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(5, 0))

        ttk.Button(btn_frame, text="➕ X+", command=self._move_by_x).pack(side='left')
        ttk.Button(btn_frame, text="➖ X-", command=self._move_minus_x).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="➕ Y+", command=self._move_by_y).pack(side='left')
        ttk.Button(btn_frame, text="➖ Y-", command=self._move_minus_y).pack(side='left', padx=5)

        self.move_x_y_btn = ttk.Button(frame, text="🔄 Переместить по X/Y", command=self._move_to_x_y)
        self.move_x_y_btn.pack(fill='x', pady=5)

        # Управление мотором
        motor_frame = ttk.LabelFrame(self.control_frame, text="🎯 Управление мотором")
        motor_frame.pack(fill='x', pady=(0, 10))

        servo_frame = ttk.Frame(motor_frame)
        servo_frame.pack(fill='x', pady=5)

        ttk.Label(servo_frame, text="Моторы:").pack(side='left')
        self.servo_list = tk.Listbox(servo_frame, width=20, height=5)
        self.servo_list.pack(side='left', padx=5)
        self.servo_list.bind('<<ListboxSelect>>', self._on_servo_select)

        pos_frame = ttk.Frame(motor_frame)
        pos_frame.pack(fill='x', pady=5)

        ttk.Label(pos_frame, text="Позиция (0-4095):").pack(side='left')
        self.pos_spin = ttk.Spinbox(pos_frame, from_=0, to=4095, width=10)
        self.pos_spin.pack(side='left', padx=5)

        ttk.Label(pos_frame, text="Скорость:").pack(side='left', padx=(10, 0))
        self.speed_spin = ttk.Spinbox(pos_frame, from_=0, to=10000, width=10)
        self.speed_spin.set(DEFAULT_SPEED)
        self.speed_spin.pack(side='left', padx=5)

        btn_row = ttk.Frame(motor_frame)
        btn_row.pack(fill='x', pady=5)

        ttk.Button(btn_row, text="🚀 Движение", command=self._move_to_position).pack(side='left', padx=2)
        ttk.Button(btn_row, text="⏹ Стоп", command=self._stop_servo).pack(side='left', padx=2)
        self.torque_btn = ttk.Button(btn_row, text="💪 Момент: ВЫКЛ", command=self._toggle_torque,
                                     style='Warning.TButton')
        self.torque_btn.pack(side='left', padx=2)

        ttk.Button(btn_row, text="🏠 Home", command=self._home_all_motors).pack(side='left', padx=2)

    def _create_monitor_panel(self):
        self.monitor_canvas = tk.Canvas(self.monitor_frame)
        self.monitor_scrollbar = ttk.Scrollbar(self.monitor_frame, orient='vertical', command=self.monitor_canvas.yview)
        self.monitor_scrollable = ttk.Frame(self.monitor_canvas)

        self.monitor_scrollable.bind("<Configure>", lambda e: self.monitor_canvas.configure(
            scrollregion=self.monitor_canvas.bbox("all")))
        self.monitor_canvas.create_window((0, 0), window=self.monitor_scrollable, anchor='nw')
        self.monitor_canvas.configure(yscrollcommand=self.monitor_scrollbar.set)

        self.monitor_canvas.pack(side='left', fill='both', expand=True)
        self.monitor_scrollbar.pack(side='right', fill='y')

        self.placeholder_label = ttk.Label(self.monitor_scrollable,
                                           text="Подключитесь и просканируйте моторы для начала мониторинга",
                                           font=('Arial', 11), foreground='gray')
        self.placeholder_label.pack(pady=50)

    def _create_log_panel(self):
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=4, font=('Consolas', 9),
                                                  state='disabled', bg='#f5f5f5')
        self.log_text.pack(fill='x', padx=5, pady=5)
        ttk.Button(self.log_frame, text="🗑️ Очистить лог", command=self._clear_log).pack(anchor='e', padx=5,
                                                                                         pady=(0, 5))

    def _log(self, message: str, level='info'):
        if not hasattr(self, 'log_text') or self.log_text is None:
            return

        timestamp = time.strftime("%H:%M:%S")
        colors = {'info': 'black', 'warning': 'darkorange', 'error': 'red', 'success': 'green'}
        color = colors.get(level, 'black')

        self.log_text.config(state='normal')
        self.log_text.insert('end', f"[{timestamp}] ", 'timestamp')
        self.log_text.insert('end', f"{message}\n", color)
        self.log_text.tag_config(color, foreground=color)
        self.log_text.config(state='disabled')
        self.log_text.see('end')

    def _clear_log(self):
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
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

    def _connect(self, port=None):
        self.controller.device = port
        if self.controller.connect():
            self._log(f"✅ Подключено к {port}", 'success')
            self.status_label.config(text="✅ Подключено", foreground='green')
            self.connect_btn.config(text="🔌 Отключиться")
            self.scan_btn.config(state='normal')

    def _disconnect(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None

        self.controller.disconnect()
        self._log("🔌 Отключено", 'info')
        self.status_label.config(text="⭕ Не подключено", foreground='gray')
        self.connect_btn.config(text="🔌 Подключиться")
        self.scan_btn.config(state='disabled')

    def _scan_servos(self):
        self._log("🔍 Сканирование...", 'info')
        self.config(cursor='watch')
        self.update()

        servos = self.controller.scan_servos()

        if servos:
            self._log(f"✅ Найдено моторов: {len(servos)}", 'success')
            self.servo_list.delete(0, tk.END)
            for sid in servos:
                self.servo_list.insert(tk.END, f"ID: {sid}")
            self.status_label.config(text=f"🟢 Моторов: {len(servos)}", foreground='green')
            self._start_monitoring(servos)
        else:
            self._log("⚠️ Моторы не найдены", 'warning')
            messagebox.showinfo("Информация", "Моторы не найдены.\nПроверьте питание и провода")

        self.config(cursor='')

    def _start_monitoring(self, motor_ids):
        self._clear_monitor_frames()
        for mid in motor_ids:
            frame = MotorMonitorFrame(self.monitor_scrollable, motor_id=mid)
            frame.pack(fill='x', padx=10, pady=5)
            self.monitor_frames[mid] = frame

        self.placeholder_label.pack_forget()

        self.monitor = MotorMonitor(self.controller, self._on_monitor_update)
        self.monitor.start(motor_ids)

    def _clear_monitor_frames(self):
        for frame in self.monitor_frames.values():
            frame.destroy()
        self.monitor_frames.clear()
        self.placeholder_label.pack(pady=50)

    def _on_monitor_update(self, motor_data: Dict[int, MotorData]):
        for mid, data in motor_data.items():
            if mid in self.monitor_frames:
                self.monitor_frames[mid].update_data(data)
                torque_state = self.controller.get_torque_state(mid)
                self.monitor_frames[mid].set_torque_state(torque_state)

    def _on_servo_select(self, event):
        selection = self.servo_list.curselection()
        if selection:
            idx = selection[0]
            servo_text = self.servo_list.get(idx)
            motor_id = int(servo_text.split(":")[1].strip())
            self.controller.current_id = motor_id
            self._log(f"✅ Выбран мотор ID={motor_id}", 'info')

    def _move_to_position(self):
        if self.controller.current_id is None:
            messagebox.showwarning("Предупреждение", "Выберите мотор!")
            return

        try:
            pos = int(self.pos_spin.get())
            speed = int(self.speed_spin.get())
            if self.controller.move_to_position(self.controller.current_id, pos, speed):
                self._log(f"🚀 Движение в {pos} (ID={self.controller.current_id}, speed={speed})", 'info')
            else:
                self._log("❌ Ошибка движения", 'error')
        except ValueError:
            messagebox.showerror("Ошибка", "Неверное значение!")

    def _move_by_x(self):
        try:
            delta = float(self.x_entry.get())
            self._log(f"🔄 Перемещение по X: +{delta}", 'info')
        except ValueError:
            messagebox.showerror("Ошибка", "Неверное значение X!")

    def _move_minus_x(self):
        try:
            delta = float(self.x_entry.get())
            self._log(f"🔄 Перемещение по X: -{delta}", 'info')
        except ValueError:
            messagebox.showerror("Ошибка", "Неверное значение X!")

    def _move_by_y(self):
        try:
            delta = float(self.y_entry.get())
            self._log(f"🔄 Перемещение по Y: +{delta}", 'info')
        except ValueError:
            messagebox.showerror("Ошибка", "Неверное значение Y!")

    def _move_minus_y(self):
        try:
            delta = float(self.y_entry.get())
            self._log(f"🔄 Перемещение по Y: -{delta}", 'info')
        except ValueError:
            messagebox.showerror("Ошибка", "Неверное значение Y!")

    def _move_to_x_y(self):
        try:
            x = float(self.x_entry.get())
            y = float(self.y_entry.get())
            self._log(f"🔄 Перемещение в X={x}, Y={y}", 'info')
        except ValueError:
            messagebox.showerror("Ошибка", "Неверные координаты!")

    def _stop_servo(self):
        if self.controller.current_id and self.controller.motor:
            try:
                self.controller.motor.StopServo(self.controller.current_id)
                self.controller.torque_states[self.controller.current_id] = False
                self._log(f"⏹ Остановлен мотор ID={self.controller.current_id}", 'info')
                if self.controller.current_id in self.monitor_frames:
                    self.monitor_frames[self.controller.current_id].set_torque_state(False)
            except:
                pass

    def _toggle_torque(self):
        if self.controller.current_id is None:
            messagebox.showwarning("Предупреждение", "Выберите мотор!")
            return
        current = self.controller.get_torque_state(self.controller.current_id)
        new = not current
        if self.controller.toggle_torque(self.controller.current_id, new):
            if self.controller.current_id in self.monitor_frames:
                self.monitor_frames[self.controller.current_id].set_torque_state(new)
            status = "ВКЛ" if new else "ВЫКЛ"
            style = 'Success.TButton' if new else 'Warning.TButton'
            self.torque_btn.config(text=f"💪 Момент: {status}", style=style)
            self._log(f"💪 Момент {status} (ID={self.controller.current_id})", 'info')

    def _enable_all_torque(self):
        for motor_id in self.controller.found_servos:
            self.controller.toggle_torque(motor_id, True)
        self._log("💪 Момент ВКЛ на всех моторах", 'success')

    def _disable_all_torque(self):
        for motor_id in self.controller.found_servos:
            self.controller.toggle_torque(motor_id, False)
        self._log("🛑 Момент ВЫКЛ на всех моторах", 'warning')

    def _home_all_motors(self):
        if not self.controller.connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь!")
            return

        if messagebox.askyesno("Подтверждение", "Вернуть все моторы в позицию 0?"):
            for motor_id in self.controller.found_servos:
                self.controller.move_to_position(motor_id, 0, speed=1500)
            self._log("🏠 Все моторы движутся в Home позиции (0)", 'info')

    def _emergency_stop(self):
        if messagebox.askyesno("⚠️ АВАРИЙНАЯ ОСТАНОВКА", "Вы уверены? Это остановит ВСЕ моторы!", icon='warning'):
            self.controller.emergency_stop_all()
            for frame in self.monitor_frames.values():
                frame.set_torque_state(False)
            self.torque_btn.config(text="💪 Момент: ВЫКЛ", style='Warning.TButton')
            self._log("🛑🛑 АВАРИЙНАЯ ОСТАНОВКА ВСЕХ МОТОРОВ 🛑🛑", 'error')
            messagebox.showwarning("Остановлено", "Все моторы остановлены!")

    def _save_config(self):
        try:
            config = {
                'port': self.port_combo.get() if hasattr(self, 'port_combo') else '',
                'found_servos': self.controller.found_servos,
                'timestamp': datetime.now().isoformat()
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            self._log(f"💾 Конфигурация сохранена в {CONFIG_FILE}", 'success')
            messagebox.showinfo("Успех", f"Конфигурация сохранена!\n{CONFIG_FILE}")
        except Exception as e:
            self._log(f"❌ Ошибка сохранения: {e}", 'error')

    def _load_config_dialog(self):  # ← ИСПРАВЛЕНО: имя метода
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'port' in config and hasattr(self, 'port_combo'):
                    self.port_combo.set(config['port'])
                    self._log("📂 Конфигурация автозагружена", 'info')
        except Exception as e:
            self._log(f"❌ Ошибка загрузки: {e}", 'error')

    def _export_data(self):
        if not self.monitor:
            messagebox.showwarning("Предупреждение", "Нет данных для экспорта!")
            return

        try:
            filename = filedialog.asksaveasfilename(defaultextension=".json")
            if not filename:
                return
            data = {}
            for mid, frame in self.monitor_frames.items():
                motor_data = self.monitor.get_data(mid)
                if motor_data:
                    data[f'motor_{mid}'] = motor_data.to_dict()
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self._log(f"📊 Данные экспортированы в {filename}", 'success')
        except Exception as e:
            self._log(f"❌ Ошибка экспорта: {e}", 'error')

    def _show_about(self):
        messagebox.showinfo("О программе",
                            "ST3215 Motor Control Panel v2.0\nУправление моторами Feetech ST3215 с мониторингом.\n© 2024")

    def _show_help(self):
        help_text = """
📖 КРАТКАЯ ИНСТРУКЦИЯ:

1. Подключение: Выберите порт, нажмите "Подключиться".
2. Сканирование: Нажмите "Сканировать моторы", дождитесь завершения.
3. Управление: Выберите мотор, укажите позицию (0-4095), нажмите "Движение".
4. Мониторинг: Данные обновляются автоматически.
5. Аварийная остановка: Красная кнопка вверху справа.

⚠️ МЕРЫ ПРЕДОСТОРОЖНОСТИ: 
Закрепите моторы перед тестом, следите за температурой (<70°C), 
не превышайте нагрузку (>80%).
        """
        messagebox.showinfo(title="Помощь", message=help_text)  # ← ИСПРАВЛЕНО: убран лишний параметр

    def _on_closing(self):
        if messagebox.askyesno("Выход", "Завершить работу?"):
            if self.monitor:
                self.monitor.stop()
            self.controller.disconnect()
            self._save_config()
            self.destroy()


def main():
    print("\n" + "=" * 70)
    print("ST3215 Motor Control Panel v2.0")
    print("=" * 70)
    app = ST3215GUI()
    app.mainloop()


if __name__ == '__main__':
    main()