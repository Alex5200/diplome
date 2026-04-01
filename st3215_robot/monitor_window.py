#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Separate Motor Monitoring Window for ST3215
Can be opened independently or from main GUI
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import serial.tools.list_ports
from typing import Optional, Dict, List
from motor_monitor import MotorController, MotorMonitor, MotorData

# --- КОНСТАНТЫ ---
MONITOR_INTERVAL = 0.5
TEMP_WARNING = 70
TEMP_CRITICAL = 80
LOAD_WARNING = 80
# -----------------


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
            self, mode="determinate", maximum=max_value, length=250
        )
        self.progress.pack(fill="x", pady=(2, 0))

        # Value label
        self.value_label = ttk.Label(self, text=f"-- {unit}", font=("Arial", 9))
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
        super().__init__(parent, text=f"🔧 Мотор ID: {motor_id}", **kwargs)

        self.motor_id = motor_id
        self._create_widgets()

    def _create_widgets(self):
        """Создание виджетов"""
        # Grid layout
        self.columnconfigure(1, weight=1)

        row = 0

        # Температура
        self.temp_bar = ProgressBarWithLabel(
            self, "🌡️ Температура", 100, "°C", warning_threshold=TEMP_WARNING
        )
        self.temp_bar.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        row += 1

        # Нагрузка
        self.load_bar = ProgressBarWithLabel(
            self, "💪 Нагрузка", 100, "%", warning_threshold=LOAD_WARNING
        )
        self.load_bar.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        row += 1

        # Напряжение
        self.volt_bar = ProgressBarWithLabel(self, "🔋 Напряжение", 25, "V")
        self.volt_bar.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        row += 1

        # Ток
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

        ttk.Label(
            self.status_frame, text="📍 Позиция:", font=("Arial", 9, "bold")
        ).grid(row=0, column=0, sticky="w")
        self.pos_label = ttk.Label(
            self.status_frame, text="--", font=("Arial", 9, "bold"), foreground="blue"
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
        self.torque_label = ttk.Label(
            self.status_frame, text="ВЫКЛ", foreground="red", font=("Arial", 9, "bold")
        )
        self.torque_label.grid(row=2, column=1, sticky="w", padx=5)

        # Индикатор ошибок
        self.error_label = ttk.Label(
            self, text="", foreground="red", font=("Arial", 8, "italic")
        )
        self.error_label.grid(row=row + 1, column=0, columnspan=2, sticky="ew", padx=5)

        # Alert frame (скрыт по умолчанию)
        self.alert_frame = ttk.Frame(self, relief="solid", borderwidth=2, padding=5)
        self.alert_frame.grid(
            row=row + 2, column=0, columnspan=2, sticky="ew", padx=5, pady=5
        )
        self.alert_frame.grid_remove()

        self.alert_label = ttk.Label(
            self.alert_frame,
            text="",
            foreground="red",
            wraplength=300,
            font=("Arial", 9, "bold"),
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
            text="✓ Да"
            if data.moving
            else "✗ Нет"
            if data.moving is not None
            else "--",
            foreground="green" if data.moving else "gray",
        )
        self.torque_label.config(
            text="✓ ВКЛ" if data.torque_enabled else "✗ ВЫКЛ",
            foreground="green" if data.torque_enabled else "red",
        )

        # Ошибки
        if data.error_count > 2:
            self.error_label.config(text=f"⚠️ Ошибок связи: {data.error_count}")
        else:
            self.error_label.config(text="")

        # Предупреждения
        if data.is_overheating():
            self._show_alert(f"🔥 ПЕРЕГРЕВ! {data.temperature}°C", "red", "#ffcccc")
        elif data.is_warning():
            alerts = []
            if data.temperature and data.temperature >= TEMP_WARNING:
                alerts.append(f"Температура: {data.temperature}°C")
            if data.load and data.load >= LOAD_WARNING:
                alerts.append(f"Нагрузка: {data.load}%")
            self._show_alert("⚠️ " + ", ".join(alerts), "darkorange", "#fff3cd")
        else:
            self._hide_alert()

    def _show_alert(self, message: str, color: str, bg_color: str):
        """Показать предупреждение"""
        self.alert_label.config(text=message, foreground=color)
        self.alert_frame.config(background=bg_color)
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


class MotorMonitorWindow(tk.Toplevel):
    """Отдельное окно мониторинга моторов"""

    def __init__(self, parent, controller: MotorController = None):
        super().__init__(parent)

        self.parent = parent
        self.controller = controller if controller else MotorController()
        self.monitor: Optional[MotorMonitor] = None
        self.monitor_frames: Dict[int, MotorMonitorFrame] = {}

        self.title("📊 Мониторинг моторов ST3215")
        self.geometry("600x700")
        self.minsize(500, 600)

        self._setup_styles()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_styles(self):
        """Настройка стилей"""
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Success.TLabel", foreground="green")
        style.configure("Warning.TLabel", foreground="orange")
        style.configure("Error.TLabel", foreground="red")
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))

    def _create_widgets(self):
        """Создание виджетов"""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(
            header_frame, text="📊 Мониторинг моторов", style="Header.TLabel"
        ).pack(side="left")

        self.status_label = ttk.Label(
            header_frame, text="⭕ Не подключено", foreground="gray"
        )
        self.status_label.pack(side="right")

        # Connection frame
        conn_frame = ttk.LabelFrame(self, text="🔌 Подключение")
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="Порт:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )

        ports = [p.device for p in serial.tools.list_ports.comports()]

        self.port_combo = ttk.Combobox(
            conn_frame, values=ports, width=25, state="readonly"
        )
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)
        if ports:
            self.port_combo.current(0)

        self.connect_btn = ttk.Button(
            conn_frame, text="Подключиться", command=self._toggle_connection
        )
        self.connect_btn.grid(row=0, column=2, padx=5, pady=5)

        self.scan_btn = ttk.Button(
            conn_frame,
            text="🔍 Сканировать",
            command=self._scan_servos,
            state="disabled",
        )
        self.scan_btn.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

        # Monitor area (scrollable)
        monitor_frame = ttk.LabelFrame(self, text="📈 Данные моторов")
        monitor_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Canvas with scrollbar
        self.monitor_canvas = tk.Canvas(monitor_frame)
        self.monitor_scrollbar = ttk.Scrollbar(
            monitor_frame, orient="vertical", command=self.monitor_canvas.yview
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
            text="Подключитесь и просканируйте моторы\nдля начала мониторинга",
            font=("Arial", 11),
            foreground="gray",
        )
        self.placeholder_label.pack(pady=50)

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(btn_frame, text="🔄 Обновить", command=self._refresh_monitor).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="🗑️ Очистить", command=self._clear_monitor).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="❌ Закрыть", command=self._on_closing).pack(
            side="right", padx=2
        )

        # Log area
        log_frame = ttk.LabelFrame(self, text="📋 Лог событий")
        log_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.log_text = tk.Text(
            log_frame, height=4, font=("Consolas", 8), state="disabled"
        )
        self.log_text.pack(fill="x", padx=5, pady=5)

    def _log(self, message: str, level: str = "info"):
        """Добавление сообщения в лог"""
        self.log_text.config(state="normal")

        timestamp = time.strftime("%H:%M:%S")
        colors = {
            "info": "black",
            "warning": "darkorange",
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

    def _toggle_connection(self):
        """Подключение/отключение"""
        if self.controller.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        """Подключение"""
        port = self.port_combo.get()
        if not port:
            messagebox.showwarning("Предупреждение", "Выберите порт!")
            return

        self.controller.device = port
        if self.controller.connect():
            self._log(f"✅ Подключено к {port}", "success")
            self.status_label.config(text="✅ Подключено", foreground="green")
            self.connect_btn.config(text="Отключиться")
            self.scan_btn.config(state="normal")
            self.port_combo.config(state="disabled")
        else:
            self._log(f"❌ Ошибка подключения к {port}", "error")
            self.status_label.config(text="❌ Ошибка", foreground="red")

    def _disconnect(self):
        """Отключение"""
        if self.monitor:
            self.monitor.stop()
            self.monitor = None

        self.controller.disconnect()
        self._log("🔌 Отключено", "info")

        self.status_label.config(text="⭕ Не подключено", foreground="gray")
        self.connect_btn.config(text="Подключиться")
        self.scan_btn.config(state="disabled")
        self.port_combo.config(state="readonly")

        self._clear_monitor()

    def _scan_servos(self):
        """Сканирование моторов"""
        self._log("🔍 Сканирование...", "info")
        self.config(cursor="watch")
        self.update()

        servos = self.controller.scan_servos()

        if servos:
            self._log(f"✅ Найдено моторов: {len(servos)}", "success")
            self._start_monitoring(servos)
        else:
            self._log("⚠️ Моторы не найдены", "warning")
            messagebox.showinfo(
                "Информация", "Моторы не найдены.\nПроверьте питание и подключение."
            )

        self.config(cursor="")

    def _start_monitoring(self, motor_ids: List[int]):
        """Запуск мониторинга"""
        self._clear_monitor()
        self.placeholder_label.pack_forget()

        # Создание фреймов мониторинга
        for mid in motor_ids:
            frame = MotorMonitorFrame(self.monitor_scrollable, motor_id=mid)
            frame.pack(fill="x", padx=10, pady=5)
            self.monitor_frames[mid] = frame

        # Запуск потока мониторинга
        self.monitor = MotorMonitor(self.controller, self._on_monitor_update)
        self.monitor.start(motor_ids)

        self._log(f"🔍 Мониторинг запущен для {len(motor_ids)} моторов", "success")
        self.status_label.config(
            text=f"🟢 Мониторинг: {len(motor_ids)} моторов", foreground="green"
        )

    def _clear_monitor(self):
        """Очистка мониторинга"""
        for frame in self.monitor_frames.values():
            frame.destroy()
        self.monitor_frames.clear()
        self.placeholder_label.pack(pady=50)

        if self.monitor:
            self.monitor.stop()
            self.monitor = None

        self._log("🗑️ Мониторинг очищен", "info")

    def _refresh_monitor(self):
        """Обновление мониторинга"""
        if self.monitor and self.controller.connected:
            self._log("🔄 Обновление данных...", "info")
        else:
            self._log("⚠️ Сначала подключитесь!", "warning")

    def _on_monitor_update(self, motor_data: Dict[int, MotorData]):
        """Callback для обновления GUI"""
        self.after(0, self._update_monitor_gui, motor_data)

    def _update_monitor_gui(self, motor_data: Dict[int, MotorData]):
        """Обновление GUI с данными"""
        for mid, data in motor_data.items():
            if mid in self.monitor_frames:
                self.monitor_frames[mid].update_data(data)

    def _on_closing(self):
        """Обработчик закрытия"""
        if self.monitor:
            self.monitor.stop()
        self.controller.disconnect()
        self.destroy()


# ============================================================
# ⭐ ФУНКЦИЯ ДЛЯ ОТКРЫТИЯ ОКНА (без импорта из самого себя!)
# ============================================================


def open_monitor_window(parent, controller=None):
    """
    Открыть окно мониторинга

    :param parent: Родительское окно
    :param controller: MotorController (опционально)
    :return: MotorMonitorWindow instance
    """
    monitor_window = MotorMonitorWindow(parent, controller)
    monitor_window.focus_force()
    return monitor_window


# Тест как отдельное приложение
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    monitor = MotorMonitorWindow(root)

    root.mainloop()
