#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor Monitor Module for ST3215
Contains MotorController, MotorMonitor, and MotorData classes
"""

from st3215 import ST3215
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List


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
        """Проверка на перегрев"""
        return self.temperature is not None and self.temperature >= TEMP_CRITICAL

    def is_warning(self) -> bool:
        """Проверка на предупреждение"""
        return (self.temperature is not None and self.temperature >= TEMP_WARNING) or (
            self.load is not None and self.load >= LOAD_WARNING
        )


class MotorController:
    """Контроллер моторов"""

    def __init__(self, device="/dev/ttyUSB0"):
        """
        Инициализация контроллера

        :param device: Последовательный порт
        """
        self.device = device
        self.motor: Optional[ST3215] = None
        self.connected = False
        self.found_servos: List[int] = []
        self.current_id: Optional[int] = None

    def connect(self) -> bool:
        """Подключение к шине"""
        try:
            print(f"🔌 Подключение к {self.device}...")
            self.motor = ST3215(device=self.device)
            self.connected = True
            print(f"✅ Подключение успешно!")
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
        print("🔌 Отключено")

    def scan_servos(self) -> List[int]:
        """Сканирование моторов"""
        if not self.connected:
            return []
        try:
            print("🔍 Сканирование...")
            self.found_servos = self.motor.ListServos()
            print(f"✅ Найдено моторов: {len(self.found_servos)}")
            return self.found_servos
        except Exception as e:
            print(f"❌ Ошибка сканирования: {e}")
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
            print(f"⚠️ Позиция вне диапазона ({MIN_POSITION}-{MAX_POSITION})")
            return False
        try:
            self.motor.StartServo(sts_id)
            self.motor.MoveTo(sts_id, position, speed=speed, acc=acc)
            print(f"🚀 Движение в {position} (ID={sts_id})")
            return True
        except Exception as e:
            print(f"❌ Ошибка движения: {e}")
            return False

    def toggle_torque(self, sts_id: int, enable: bool) -> bool:
        """Вкл/Выкл момента"""
        try:
            if enable:
                result = self.motor.StartServo(sts_id)
                print(f"💪 Момент ВКЛ (ID={sts_id})")
            else:
                result = self.motor.StopServo(sts_id)
                print(f"💪 Момент ВЫКЛ (ID={sts_id})")
            return result is not None
        except Exception as e:
            print(f"❌ Ошибка момента: {e}")
            return False

    def read_position(self, sts_id: int) -> Optional[int]:
        """Чтение позиции"""
        try:
            return self.motor.ReadPosition(sts_id)
        except:
            return None

    def read_temperature(self, sts_id: int) -> Optional[float]:
        """Чтение температуры"""
        try:
            return self.motor.ReadTemperature(sts_id)
        except:
            return None

    def read_voltage(self, sts_id: int) -> Optional[float]:
        """Чтение напряжения"""
        try:
            return self.motor.ReadVoltage(sts_id)
        except:
            return None

    def read_current(self, sts_id: int) -> Optional[float]:
        """Чтение тока"""
        try:
            return self.motor.ReadCurrent(sts_id)
        except:
            return None

    def read_load(self, sts_id: int) -> Optional[float]:
        """Чтение нагрузки"""
        try:
            return self.motor.ReadLoad(sts_id)
        except:
            return None

    def read_mode(self, sts_id: int) -> Optional[int]:
        """Чтение режима"""
        try:
            return self.motor.ReadMode(sts_id)
        except:
            return None

    def is_moving(self, sts_id: int) -> Optional[bool]:
        """Проверка движения"""
        try:
            return self.motor.IsMoving(sts_id)
        except:
            return None


class MotorMonitor:
    """Отдельный поток для мониторинга моторов"""

    def __init__(self, motor_controller: MotorController, update_callback=None):
        """
        Инициализация монитора

        :param motor_controller: Контроллер моторов
        :param update_callback: Callback для обновления GUI
        """
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


# Тест модуля
if __name__ == "__main__":
    print("=" * 60)
    print("Тест модуля motor_monitor")
    print("=" * 60)

    # Тест MotorData
    data = MotorData(motor_id=1)
    print(f"\nMotorData тест:")
    print(f"  ID: {data.motor_id}")
    print(f"  Перегрев: {data.is_overheating()}")
    print(f"  Предупреждение: {data.is_warning()}")

    # Тест с данными
    data.temperature = 75.0
    data.load = 85.0
    print(f"\nС данными (temp=75, load=85):")
    print(f"  Перегрев: {data.is_overheating()}")
    print(f"  Предупреждение: {data.is_warning()}")

    print("\n✅ Тест завершен!")
