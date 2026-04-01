#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI Control Panel для моторов ST3215
Использует Tkinter + отдельный поток мониторинга
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
from st3215 import ST3215
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import numpy as np
from st3215 import ST3215
from config_manager import ConfigManager
from settings_dialog import open_settings
from kinematics_3d import RobotVisualizer3D, ForwardKinematics3D
from motor_monitor import MotorController, MotorMonitor, MotorData

# --- КОНСТАНТЫ ---
MIN_POSITION = 0
MAX_POSITION = 4095
DEFAULT_SPEED = 2400
DEFAULT_ACC = 50
MONITOR_INTERVAL = 0.5  # Интервал обновления мониторинга (сек)
TEMP_WARNING = 70  # Предупреждение температуры (°C)
TEMP_CRITICAL = 80  # Критическая температура (°C)
LOAD_WARNING = 80  # Предупреждение нагрузки (%)
# -----------------


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

    def is_warning(self) -> bool:
        return (self.temperature is not None and self.temperature >= TEMP_WARNING) or (
            self.load is not None and self.load >= LOAD_WARNING
        )


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
        """Запуск мониторинга"""
        if self.running:
            return

        # Инициализация данных
        with self.lock:
            for mid in motor_ids:
                if mid not in self.motor_data:
                    self.motor_data[mid] = MotorData(motor_id=mid)

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print(f"🔍 Мониторинг запущен для {len(motor_ids)} моторов")

    def stop(self):
        """Остановка мониторинга"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("🛑 Мониторинг остановлен")

    def _monitor_loop(self):
        """Основной цикл мониторинга"""
        while self.running:
            try:
                for motor_id, data in list(self.motor_data.items()):
                    self._update_motor_data(motor_id, data)

                # Вызов callback для обновления GUI (в main thread)
                if self.update_callback and self.motor_data:
                    self.update_callback(self.motor_data.copy())

            except Exception as e:
                print(f"❌ Ошибка мониторинга: {e}")

            time.sleep(MONITOR_INTERVAL)

    def _update_motor_data(self, motor_id: int, data: MotorData):
        """Обновление данных конкретного мотора"""
        if not self.motor_controller or not self.motor_controller.connected:
            return

        try:
            motor = self.motor_controller.motor

            # Чтение параметров
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
                print(f"⚠️ Мотор {motor_id}: много ошибок - {e}")

    def get_data(self, motor_id: int) -> Optional[MotorData]:
        """Получение данных мотора"""
        with self.lock:
            return self.motor_data.get(motor_id)

    def get_all_data(self) -> Dict[int, MotorData]:
        """Получение всех данных"""
        with self.lock:
            return self.motor_data.copy()


class MotorController:
    """Контроллер моторов (адаптирован из оригинального кода)"""

    def __init__(self, device="/dev/ttyUSB0"):
        self.device = device
        self.motor: Optional[ST3215] = None
        self.connected = False
        self.found_servos: List[int] = []
        self.current_id: Optional[int] = None

    def connect(self) -> bool:
        """Подключение к шине"""
        try:
            self.motor = ST3215(device=self.device)
            self.connected = True
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def disconnect(self):
        """Отключение"""
        if self.motor and self.current_id is not None:
            try:
                self.motor.StopServo(self.current_id)
            except:
                pass
        self.connected = False

    def scan_servos(self) -> List[int]:
        """Сканирование моторов"""
        if not self.connected:
            return []
        try:
            self.found_servos = self.motor.ListServos()
            return self.found_servos
        except:
            return []

    def move_to_position(
        self,
        sts_id: int,
        position: int,
        speed: int = DEFAULT_SPEED,
        acc: int = DEFAULT_ACC,
    ) -> bool:
        """Движение в позицию"""
        if not (MIN_POSITION <= position <= MAX_POSITION):
            return False
        try:
            self.motor.StartServo(sts_id)
            self.motor.MoveTo(sts_id, position, speed=speed, acc=acc)
            return True
        except:
            return False

    def toggle_torque(self, sts_id: int, enable: bool) -> bool:
        """Вкл/Выкл момента"""
        try:
            if enable:
                return self.motor.StartServo(sts_id) is not None
            else:
                return self.motor.StopServo(sts_id) is not None
        except:
            return False


# ==================== GUI КЛАССЫ ====================


class ProgressBarWithLabel(ttk.Frame):
    """Прогресс-бар с подписью и значением"""

    def __init__(
        self,
        parent,
        label: str,
        max_value: float,
        unit: str = "",
        warning_threshold: float = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)

        self.label_text = label
        self.max_value = max_value
        self.unit = unit
        self.warning_threshold = warning_threshold

        # Label
        self.title_label = ttk.Label(self, text=label, font=("Arial", 9, "bold"))
        self.title_label.pack(anchor="w")

        # Progress bar
        self.progress = ttk.Progressbar(
            self, mode="determinate", maximum=max_value, length=200
        )
        self.progress.pack(fill="x", pady=(2, 0))

        # Value label
        self.value_label = ttk.Label(self, text=f"-- {unit}", font=("Arial", 8))
        self.value_label.pack(anchor="e")

    def update_value(self, value: Optional[float]):
        """Обновление значения"""
        if value is None:
            self.progress["value"] = 0
            self.value_label.config(text=f"-- {self.unit}", foreground="gray")
        else:
            self.progress["value"] = min(value, self.max_value)
            text = f"{value:.1f} {self.unit}".rstrip()
            self.value_label.config(text=text)

            # Цветовая индикация
            if self.warning_threshold and value >= self.warning_threshold:
                self.value_label.config(foreground="red")
            elif value >= self.max_value * 0.8:
                self.value_label.config(foreground="orange")
            else:
                self.value_label.config(foreground="green")


class MotorMonitorFrame(ttk.LabelFrame):
    """Фрейм мониторинга одного мотора"""

    def __init__(self, parent, motor_id: int, **kwargs):
        super().__init__(parent, text=f"Мотор ID: {motor_id}", **kwargs)

        self.motor_id = motor_id

        # Grid layout
        self.columnconfigure(1, weight=1)

        # Параметры
        row = 0
        self.temp_bar = ProgressBarWithLabel(
            self, "🌡️ Температура", 100, "°C", warning_threshold=TEMP_WARNING
        )
        self.temp_bar.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        row += 1

        self.load_bar = ProgressBarWithLabel(
            self, "💪 Нагрузка", 100, "%", warning_threshold=LOAD_WARNING
        )
        self.load_bar.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        row += 1

        self.volt_bar = ProgressBarWithLabel(self, "🔋 Напряжение", 25, "V")
        self.volt_bar.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        row += 1

        self.current_bar = ProgressBarWithLabel(self, "⚡ Ток", 2000, "mA")
        self.current_bar.grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2
        )
        row += 1

        # Статусы
        self.status_frame = ttk.Frame(self)
        self.status_frame.grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=5
        )

        ttk.Label(self.status_frame, text="📍 Позиция:").grid(
            row=0, column=0, sticky="w"
        )
        self.pos_label = ttk.Label(
            self.status_frame, text="--", font=("Arial", 9, "bold")
        )
        self.pos_label.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(self.status_frame, text="🔄 Движение:").grid(
            row=1, column=0, sticky="w"
        )
        self.moving_label = ttk.Label(self.status_frame, text="--")
        self.moving_label.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(self.status_frame, text="💪 Момент:").grid(
            row=2, column=0, sticky="w"
        )
        self.torque_label = ttk.Label(self.status_frame, text="ВЫКЛ", foreground="red")
        self.torque_label.grid(row=2, column=1, sticky="w", padx=5)

        # Индикатор ошибок
        self.error_label = ttk.Label(self, text="", foreground="red")
        self.error_label.grid(row=row + 1, column=0, columnspan=2, sticky="ew", padx=5)

        # Alert frame (скрыт по умолчанию)
        self.alert_frame = ttk.Frame(self, relief="solid", borderwidth=1)
        self.alert_frame.grid(
            row=row + 2, column=0, columnspan=2, sticky="ew", padx=5, pady=2
        )
        self.alert_frame.grid_remove()

        self.alert_label = ttk.Label(
            self.alert_frame, text="", foreground="red", wraplength=200
        )
        self.alert_label.pack(padx=5, pady=2)

    def update_data(self, data: MotorData):
        """Обновление данных"""
        # Прогресс-бары
        self.temp_bar.update_value(data.temperature)
        self.load_bar.update_value(data.load)
        self.volt_bar.update_value(data.voltage)
        self.current_bar.update_value(data.current)

        # Статусы
        self.pos_label.config(
            text=str(data.position) if data.position is not None else "--"
        )
        self.moving_label.config(
            text="✓ Да" if data.moving else "✗ Нет" if data.moving is not None else "--"
        )
        self.torque_label.config(
            text="✓ ВКЛ" if data.torque_enabled else "✗ ВЫКЛ",
            foreground="green" if data.torque_enabled else "red",
        )

        # Ошибки
        if data.error_count > 2:
            self.error_label.config(text=f"⚠️ Ошибок: {data.error_count}")
        else:
            self.error_label.config(text="")

        # Предупреждения
        if data.is_overheating():
            self._show_alert(f"🔥 ПЕРЕГРЕВ! {data.temperature}°C", "red")
        elif data.is_warning():
            alerts = []
            if data.temperature and data.temperature >= TEMP_WARNING:
                alerts.append(f"Темп: {data.temperature}°C")
            if data.load and data.load >= LOAD_WARNING:
                alerts.append(f"Нагрузка: {data.load}%")
            self._show_alert("⚠️ " + ", ".join(alerts), "orange")
        else:
            self._hide_alert()

    def _show_alert(self, message: str, color: str):
        """Показать предупреждение"""
        self.alert_label.config(text=message, foreground=color)
        self.alert_frame.grid()

    def _hide_alert(self):
        """Скрыть предупреждение"""
        self.alert_frame.grid_remove()

    def set_torque_state(self, enabled: bool):
        """Установка состояния момента"""
        self.torque_label.config(
            text="✓ ВКЛ" if enabled else "✗ ВЫКЛ",
            foreground="green" if enabled else "red",
        )


class ST3215GUI(tk.Tk):
    """Основное окно приложения"""

    def __init__(self):
        super().__init__()

        self.title("ST3215 Motor Control Panel")
        self.geometry("1200x700")
        self.minsize(900, 600)

        # Настройки стиля
        self._setup_styles()

        # Данные
        self.controller = MotorController()
        self.monitor: Optional[MotorMonitor] = None
        self.monitor_frames: Dict[int, MotorMonitorFrame] = {}

        # Создание интерфейса
        self._create_widgets()

        # Обработчик закрытия
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_styles(self):
        """Настройка стилей ttk"""
        style = ttk.Style()
        style.theme_use("clam")

        # Цвета для статусов
        style.configure("Success.TLabel", foreground="green")
        style.configure("Warning.TLabel", foreground="orange")
        style.configure("Error.TLabel", foreground="red")
        style.configure("Bold.TLabel", font=("Arial", 9, "bold"))

    def _create_widgets(self):
        """Создание виджетов"""
        # Главное разделение
        self.paned = ttk.PanedWindow(self, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=5, pady=5)

        # Левая панель - управление
        self.control_frame = ttk.LabelFrame(self.paned, text="🎮 Управление")
        self.paned.add(self.control_frame, weight=1)
        self._create_control_panel()

        # Правая панель - мониторинг
        self.monitor_frame = ttk.LabelFrame(self.paned, text="📊 Мониторинг")
        self.paned.add(self.monitor_frame, weight=2)
        self._create_monitor_panel()

        # Нижняя панель - лог
        self.log_frame = ttk.LabelFrame(self, text="📋 Лог событий")
        self.log_frame.pack(fill="x", padx=5, pady=(0, 5))
        self._create_log_panel()

    def _create_control_panel(self):
        """Панель управления"""
        frame = ttk.Frame(self.control_frame)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Порт
        port_frame = ttk.LabelFrame(frame, text="Подключение")
        port_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(port_frame, text="Порт:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self.port_combo = ttk.Combobox(port_frame, width=20, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)
        self._refresh_ports()

        ttk.Button(port_frame, text="🔄 Обновить", command=self._refresh_ports).grid(
            row=0, column=2, padx=5
        )

        self.connect_btn = ttk.Button(
            port_frame, text="🔌 Подключиться", command=self._toggle_connection
        )
        self.connect_btn.grid(row=1, column=0, columnspan=3, pady=5, sticky="ew")

        # Сканирование
        scan_frame = ttk.LabelFrame(frame, text="Сканирование")
        scan_frame.pack(fill="x", pady=(0, 10))

        self.scan_btn = ttk.Button(
            scan_frame,
            text="🔍 Сканировать моторы",
            command=self._scan_servos,
            state="disabled",
        )
        self.scan_btn.pack(fill="x", padx=5, pady=5)

        self.servo_list = tk.Listbox(scan_frame, height=6, selectmode="single")
        self.servo_list.pack(fill="x", padx=5, pady=5)
        self.servo_list.bind("<<ListboxSelect>>", self._on_servo_select)

        # Управление выбранным мотором
        control_frame = ttk.LabelFrame(frame, text="Управление мотором")
        control_frame.pack(fill="x", pady=(0, 10))

        # Позиция
        pos_frame = ttk.Frame(control_frame)
        pos_frame.pack(fill="x", pady=5)

        ttk.Label(pos_frame, text="Позиция (0-4095):").pack(anchor="w")
        self.pos_spin = ttk.Spinbox(
            pos_frame, from_=MIN_POSITION, to=MAX_POSITION, width=10
        )
        self.pos_spin.set("0")
        self.pos_spin.pack(anchor="w", pady=2)

        # Скорость
        speed_frame = ttk.Frame(control_frame)
        speed_frame.pack(fill="x", pady=5)

        ttk.Label(speed_frame, text="Скорость (0-3400):").pack(anchor="w")
        self.speed_spin = ttk.Spinbox(speed_frame, from_=0, to=3400, width=10)
        self.speed_spin.set(str(DEFAULT_SPEED))
        self.speed_spin.pack(anchor="w", pady=2)

        # Кнопки управления
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill="x", pady=10)

        ttk.Button(btn_frame, text="🚀 Движение", command=self._move_to_position).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="⏹ Стоп", command=self._stop_servo).pack(
            side="left", padx=2
        )

        self.torque_btn = ttk.Button(
            btn_frame,
            text="💪 Момент: ВЫКЛ",
            command=self._toggle_torque,
            style="Warning.TButton",
        )
        self.torque_btn.pack(side="left", padx=2)

        # Быстрые позиции
        quick_frame = ttk.LabelFrame(control_frame, text="Быстрые позиции")
        quick_frame.pack(fill="x", pady=5)

        for i, (label, pos) in enumerate(
            [("0", 0), ("¼", 1024), ("½", 2048), ("¾", 3072), ("MAX", 4095)]
        ):
            ttk.Button(
                quick_frame, text=label, command=lambda p=pos: self._quick_move(p)
            ).grid(row=0, column=i, padx=2, pady=2)

    def _create_monitor_panel(self):
        """Панель мониторинга"""
        # Canvas с прокруткой для динамического количества моторов
        self.monitor_canvas = tk.Canvas(self.monitor_frame)
        self.monitor_scrollbar = ttk.Scrollbar(
            self.monitor_frame, orient="vertical", command=self.monitor_canvas.yview
        )
        self.monitor_scrollable = ttk.Frame(self.monitor_canvas)

        self.monitor_scrollable.bind(
            "<Configure>",
            lambda e: self.monitor_canvas.configure(
                scrollregion=self.monitor_canvas.bbox("all")
            ),
        )

        self.monitor_canvas.create_window(
            (0, 0), window=self.monitor_scrollable, anchor="nw"
        )
        self.monitor_canvas.configure(yscrollcommand=self.monitor_scrollbar.set)

        self.monitor_canvas.pack(side="left", fill="both", expand=True)
        self.monitor_scrollbar.pack(side="right", fill="y")

        # Placeholder
        self.placeholder_label = ttk.Label(
            self.monitor_scrollable,
            text="Подключитесь и просканируйте моторы для мониторинга",
            font=("Arial", 10),
        )
        self.placeholder_label.pack(pady=20)

    def _create_log_panel(self):
        """Панель логов"""
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, height=4, font=("Consolas", 9), state="disabled"
        )
        self.log_text.pack(fill="x", padx=5, pady=5)

    def _log(self, message: str, level: str = "info"):
        """Добавление сообщения в лог"""
        self.log_text.config(state="normal")

        timestamp = time.strftime("%H:%M:%S")
        colors = {
            "info": "black",
            "warning": "orange",
            "error": "red",
            "success": "green",
        }
        color = colors.get(level, "black")

        self.log_text.insert("end", f"[{timestamp}] ", "timestamp")
        self.log_text.insert("end", f"{message}\n", color)
        self.log_text.tag_config(color, foreground=color)
        self.log_text.tag_config("timestamp", foreground="gray")

        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _refresh_ports(self):
        """Обновление списка портов"""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.current(0)

    def _toggle_connection(self):
        """Подключение/отключение"""
        if self.controller.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        """Подключение к порту"""
        port = self.port_combo.get()
        if not port:
            messagebox.showwarning("Предупреждение", "Выберите порт!")
            return

        self.controller.device = port
        if self.controller.connect():
            self._log(f"✅ Подключено к {port}", "success")
            self.connect_btn.config(text="🔌 Отключиться")
            self.scan_btn.config(state="normal")
            self.port_combo.config(state="disabled")
        else:
            self._log(f"❌ Ошибка подключения к {port}", "error")

    def _disconnect(self):
        """Отключение"""
        if self.monitor:
            self.monitor.stop()
            self.monitor = None

        self.controller.disconnect()
        self._log("🔌 Отключено", "info")

        self.connect_btn.config(text="🔌 Подключиться")
        self.scan_btn.config(state="disabled")
        self.port_combo.config(state="readonly")

        # Очистка мониторинга
        self._clear_monitor_frames()

    def _scan_servos(self):
        """Сканирование моторов"""
        self._log("🔍 Сканирование...", "info")
        self.config(cursor="watch")
        self.update()

        servos = self.controller.scan_servos()

        if servos:
            self._log(f"✅ Найдено моторов: {len(servos)}", "success")
            self.servo_list.delete(0, "end")
            for sid in servos:
                self.servo_list.insert("end", f"ID: {sid}")

            # Запуск мониторинга
            self._start_monitoring(servos)
        else:
            self._log("⚠️ Моторы не найдены", "warning")
            messagebox.showinfo(
                "Информация", "Моторы не найдены. Проверьте питание и подключение."
            )

        self.config(cursor="")

    def _start_monitoring(self, motor_ids: List[int]):
        """Запуск мониторинга"""
        self._clear_monitor_frames()
        self.placeholder_label.pack_forget()

        # Создание фреймов мониторинга
        for mid in motor_ids:
            frame = MotorMonitorFrame(self.monitor_scrollable, motor_id=mid)
            frame.pack(fill="x", padx=10, pady=5)
            self.monitor_frames[mid] = frame

        # Запуск потока мониторинга
        self.monitor = MotorMonitor(self.controller, self._on_monitor_update)
        self.monitor.start(motor_ids)

    def _clear_monitor_frames(self):
        """Очистка фреймов мониторинга"""
        for frame in self.monitor_frames.values():
            frame.destroy()
        self.monitor_frames.clear()
        self.placeholder_label.pack(pady=20)

    def _on_monitor_update(self, motor_data: Dict[int, MotorData]):
        """Callback для обновления GUI из потока мониторинга"""
        # Обновление в main thread
        self.after(0, self._update_monitor_gui, motor_data)

    def _update_monitor_gui(self, motor_data: Dict[int, MotorData]):
        """Обновление GUI с данными мониторинга"""
        for mid, data in motor_data.items():
            if mid in self.monitor_frames:
                self.monitor_frames[mid].update_data(data)

    def _on_servo_select(self, event):
        """Выбор мотора в списке"""
        selection = self.servo_list.curselection()
        if selection:
            idx = selection[0]
            servo_text = self.servo_list.get(idx)
            motor_id = int(servo_text.split(":")[1].strip())
            self.controller.current_id = motor_id
            self._log(f"✅ Выбран мотор ID={motor_id}", "info")

    def _move_to_position(self):
        """Движение в позицию"""
        if self.controller.current_id is None:
            messagebox.showwarning("Предупреждение", "Выберите мотор!")
            return

        try:
            position = int(self.pos_spin.get())
            speed = int(self.speed_spin.get())

            if self.controller.move_to_position(
                self.controller.current_id, position, speed
            ):
                self._log(
                    f"🚀 Движение в {position} (ID={self.controller.current_id})",
                    "info",
                )
            else:
                self._log("❌ Ошибка движения", "error")
        except ValueError:
            messagebox.showerror("Ошибка", "Неверное значение!")

    def _quick_move(self, position: int):
        """Быстрое перемещение"""
        self.pos_spin.set(str(position))
        self._move_to_position()

    def _stop_servo(self):
        """Остановка мотора"""
        if self.controller.current_id and self.controller.motor:
            try:
                self.controller.motor.StopServo(self.controller.current_id)
                self._log(f"⏹ Остановлен мотор ID={self.controller.current_id}", "info")
            except:
                self._log("❌ Ошибка остановки", "error")

    def _toggle_torque(self):
        """Переключение момента"""
        if self.controller.current_id is None:
            return

        # Переключаем состояние
        current_state = self.controller.current_id in [
            mid
            for mid, frame in self.monitor_frames.items()
            if frame.torque_label.cget("text") == "✓ ВКЛ"
        ]

        new_state = not current_state

        if self.controller.toggle_torque(self.controller.current_id, new_state):
            # Обновляем UI
            if self.controller.current_id in self.monitor_frames:
                self.monitor_frames[self.controller.current_id].set_torque_state(
                    new_state
                )

            status = "ВКЛ" if new_state else "ВЫКЛ"
            style = "Success.TButton" if new_state else "Warning.TButton"
            self.torque_btn.config(text=f"💪 Момент: {status}", style=style)

            self._log(f"💪 Момент {status} (ID={self.controller.current_id})", "info")

    def _on_closing(self):
        """Обработчик закрытия окна"""
        if self.monitor:
            self.monitor.stop()
        self.controller.disconnect()
        self.destroy()


class ST3215AdvancedGUI(tk.Tk):
    """Advanced GUI with 3D visualization"""

    def __init__(self):
        super().__init__()

        self.title("ST3215 Robot Control - Advanced")
        self.geometry("1400x800")
        self.minsize(1200, 700)

        # Load configuration
        self.config_mgr = ConfigManager()
        self.config_mgr.load()

        # Initialize components
        self.controller = MotorController(self.config_mgr.config.serial_port)
        self.monitor: MotorMonitor = None
        self.kinematics: ForwardKinematics3D = None
        self.visualizer_3d: RobotVisualizer3D = None

        # Data
        self.motor_frames = {}
        self.current_joint_angles = np.zeros(6)

        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_widgets(self):
        """Create main widgets"""
        # Main paned window
        self.main_paned = ttk.PanedWindow(self, orient="horizontal")
        self.main_paned.pack(fill="both", expand=True, padx=5, pady=5)

        # Left panel - Control & Monitoring
        self.left_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.left_frame, weight=1)
        self._create_left_panel()

        # Right panel - 3D Visualization
        self.right_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.right_frame, weight=1)
        self._create_right_panel()

        # Menu bar
        self._create_menu()

        # Status bar
        self._create_status_bar()

    def _create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="📁 Файл", menu=file_menu)
        file_menu.add_command(label="⚙️ Настройки", command=self._open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="🚪 Выход", command=self._on_closing)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="👁️ Вид", menu=view_menu)
        view_menu.add_command(label="🔄 Обновить 3D", command=self._update_3d_view)
        view_menu.add_command(label="🗑️ Очистить след", command=self._clear_trail)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=" Инструменты", menu=tools_menu)
        tools_menu.add_command(label="📊 Кинематика", command=self._show_kinematics)
        tools_menu.add_command(label="🎮 Тест движения", command=self._test_motion)

    def _create_left_panel(self):
        """Create left panel with control and monitoring"""
        # Notebook
        notebook = ttk.Notebook(self.left_frame)
        notebook.pack(fill="both", expand=True)

        # Tab 1: Control
        self.control_tab = ttk.Frame(notebook)
        notebook.add(self.control_tab, text="🎮 Управление")
        self._create_control_tab()

        # Tab 2: Monitoring
        self.monitor_tab = ttk.Frame(notebook)
        notebook.add(self.monitor_tab, text="📊 Мониторинг")
        self._create_monitor_tab()

    def _create_right_panel(self):
        """Create right panel with 3D visualization"""
        # 3D visualization label
        ttk.Label(
            self.right_frame, text="📐 3D Визуализация", font=("Arial", 12, "bold")
        ).pack(pady=5)

        # Canvas for matplotlib
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self.visualizer_3d = RobotVisualizer3D(self.config_mgr)
        self.kinematics = ForwardKinematics3D(self.config_mgr)

        self.visualizer_3d.create_figure(figsize=(6, 5))

        self.canvas = FigureCanvasTkAgg(self.visualizer_3d.fig, master=self.right_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # 3D control buttons
        btn_frame = ttk.Frame(self.right_frame)
        btn_frame.pack(fill="x", pady=5)

        ttk.Button(btn_frame, text="🔄 Обновить", command=self._update_3d_view).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="🗑️ Очистить след", command=self._clear_trail).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="🏠 Home", command=self._move_home).pack(
            side="left", padx=2
        )

    def _create_control_tab(self):
        """Create control tab"""
        # Connection frame
        conn_frame = ttk.LabelFrame(self.control_tab, text="Подключение")
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="Порт:").grid(row=0, column=0, padx=5, pady=5)
        self.port_var = tk.StringVar(value=self.config_mgr.config.serial_port)
        ttk.Entry(conn_frame, textvariable=self.port_var, width=20).grid(
            row=0, column=1, padx=5, pady=5
        )

        self.connect_btn = ttk.Button(
            conn_frame, text="🔌 Подключиться", command=self._toggle_connection
        )
        self.connect_btn.grid(row=0, column=2, padx=5, pady=5)

        # Joint control frame
        joint_frame = ttk.LabelFrame(self.control_tab, text="Управление суставами")
        joint_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Joint sliders
        self.joint_sliders = []
        for i in range(6):
            frame = ttk.Frame(joint_frame)
            frame.pack(fill="x", padx=5, pady=2)

            ttk.Label(frame, text=f"Joint {i + 1}:", width=10).pack(side="left")

            slider = ttk.Scale(
                frame,
                from_=-180,
                to=180,
                orient="horizontal",
                command=lambda val, idx=i: self._on_joint_slider_change(idx, val),
            )
            slider.pack(side="left", fill="x", expand=True, padx=5)

            value_label = ttk.Label(frame, text="0.0°", width=8)
            value_label.pack(side="left")

            self.joint_sliders.append((slider, value_label))

        # Action buttons
        btn_frame = ttk.Frame(self.control_tab)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(
            btn_frame, text="🚀 Применить", command=self._apply_joint_angles
        ).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🏠 Home", command=self._move_home).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="⏹ Стоп", command=self._emergency_stop).pack(
            side="left", padx=2
        )

    def _create_monitor_tab(self):
        """Create monitoring tab"""
        # Scrollable frame
        canvas = tk.Canvas(self.monitor_tab)
        scrollbar = ttk.Scrollbar(
            self.monitor_tab, orient="vertical", command=canvas.yview
        )
        self.monitor_scrollable = ttk.Frame(canvas)

        self.monitor_scrollable.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.monitor_scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _create_status_bar(self):
        """Create status bar"""
        self.status_var = tk.StringVar(value="Готов")
        status_bar = ttk.Label(
            self, textvariable=self.status_var, relief="sunken", anchor="w"
        )
        status_bar.pack(fill="x", side="bottom")

    def _on_joint_slider_change(self, joint_idx: int, value: float):
        """Handle joint slider change"""
        # Update label
        slider, label = self.joint_sliders[joint_idx]
        label.config(text=f"{float(value):.1f}°")

        # Update joint angles
        self.current_joint_angles[joint_idx] = np.radians(float(value))

        # Update 3D visualization
        self._update_3d_view()

    def _update_3d_view(self):
        """Update 3D visualization"""
        if self.visualizer_3d:
            self.visualizer_3d.update_visualization(self.current_joint_angles)
            self.canvas.draw()

    def _clear_trail(self):
        """Clear trail in 3D visualization"""
        if self.visualizer_3d:
            self.visualizer_3d.clear_trail()
            self._update_3d_view()
            self.status_var.set("След очищен")

    def _move_home(self):
        """Move to home position"""
        self.current_joint_angles = np.zeros(6)
        for i, (slider, label) in enumerate(self.joint_sliders):
            slider.set(0)
            label.config(text="0.0°")
        self._update_3d_view()
        self.status_var.set("Home позиция установлена")

    def _emergency_stop(self):
        """Emergency stop"""
        if self.controller and self.controller.current_id:
            self.controller.motor.StopServo(self.controller.current_id)
            self.status_var.set("⚠️ АВАРИЙНАЯ ОСТАНОВКА")
            messagebox.showwarning("Стоп", "Все моторы остановлены!")

    def _apply_joint_angles(self):
        """Apply joint angles to real robot"""
        if not self.controller.connected:
            messagebox.showwarning("Внимание", "Сначала подключитесь!")
            return

        # Get selected motor
        if self.controller.current_id is None:
            messagebox.showwarning("Внимание", "Выберите мотор!")
            return

        # For simplicity, apply only to selected motor
        # In real application, you'd map joints to motors
        motor_id = self.controller.current_id
        joint_idx = motor_id - 1  # Simple mapping

        if 0 <= joint_idx < 6:
            angle_deg = self.current_joint_angles[joint_idx]
            # Convert to position (simplified)
            position = int((angle_deg + 180) / 360 * 4095)

            if self.controller.move_to_position(motor_id, position):
                self.status_var.set(f"✅ Мотор {motor_id} -> {position}")

    def _open_settings(self):
        """Open settings dialog"""
        if open_settings(self, self.config_mgr):
            # Reload configuration
            self.config_mgr.load()
            self.visualizer_3d = RobotVisualizer3D(self.config_mgr)
            self.kinematics = ForwardKinematics3D(self.config_mgr)
            self.visualizer_3d.create_figure(figsize=(6, 5))

            # Recreate canvas
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            self.canvas.get_tk_widget().destroy()
            self.canvas = FigureCanvasTkAgg(
                self.visualizer_3d.fig, master=self.right_frame
            )
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

            self.status_var.set("⚙️ Настройки обновлены")

    def _show_kinematics(self):
        """Show kinematics information"""
        T, states = self.kinematics.compute(self.current_joint_angles)
        ee_pos = T[0:3, 3]

        info = f"Позиция энд-эффектора:\n"
        info += f"X: {ee_pos[0]:.2f} mm\n"
        info += f"Y: {ee_pos[1]:.2f} mm\n"
        info += f"Z: {ee_pos[2]:.2f} mm\n\n"
        info += f"Расстояние от базы: {np.linalg.norm(ee_pos):.2f} mm"

        messagebox.showinfo("Кинематика", info)

    def _test_motion(self):
        """Test motion trajectory"""
        # Simple test trajectory
        trajectory = [
            np.array([0, 0, 0, 0, 0, 0]),
            np.array([0.5, -0.3, 0.8, 0, -0.4, 0]),
            np.array([1.0, -0.5, 1.2, 0, -0.6, 0]),
            np.array([0.5, -0.3, 0.8, 0, -0.4, 0]),
            np.array([0, 0, 0, 0, 0, 0]),
        ]

        # Animate
        for joints in trajectory:
            self.current_joint_angles = joints
            for i, (slider, label) in enumerate(self.joint_sliders):
                slider.set(np.degrees(joints[i]))
                label.config(text=f"{np.degrees(joints[i]):.1f}°")
            self._update_3d_view()
            time.sleep(0.5)
            self.update()

    def _toggle_connection(self):
        """Toggle connection"""
        if self.controller.connected:
            self.controller.disconnect()
            self.connect_btn.config(text="🔌 Подключиться")
            self.status_var.set("Отключено")
        else:
            port = self.port_var.get()
            self.controller.device = port
            if self.controller.connect():
                self.connect_btn.config(text="🔌 Отключиться")
                self.status_var.set(f"Подключено к {port}")
                self._start_monitoring()

    def _start_monitoring(self):
        """Start motor monitoring"""
        if self.monitor:
            self.monitor.stop()

        self.monitor = MotorMonitor(self.controller, self._on_monitor_update)
        self.monitor.start(self.controller.found_servos)

    def _on_monitor_update(self, motor_data: dict):
        """Callback for motor monitoring"""
        self.after(0, self._update_monitor_gui, motor_data)

    def _update_monitor_gui(self, motor_data: dict):
        """Update monitoring GUI"""
        for mid, data in motor_data.items():
            if mid in self.motor_frames:
                self.motor_frames[mid].update_data(data)

    def _on_closing(self):
        """Handle window closing"""
        if self.monitor:
            self.monitor.stop()
        self.controller.disconnect()
        self.destroy()

    def _open_3d_visualization(self):
        """Open 3D visualization window"""
        from visualize_kinematics import KinematicsVisualizer

        # Create visualizer
        vis = KinematicsVisualizer()

        # Set current joint angles if available
        if hasattr(self, "current_joint_angles"):
            for i, slider in enumerate(vis.sliders):
                angle_deg = np.degrees(self.current_joint_angles[i])
                slider.set_val(angle_deg)

        # Show in separate thread
        import threading

        thread = threading.Thread(target=vis.show, daemon=True)
        thread.start()


def main():
    """Точка входа"""
    app = ST3215AdvancedGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
