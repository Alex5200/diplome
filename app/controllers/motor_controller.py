#!/usr/bin/env python3

"""
Motor Controller Module
Handles communication with ST3215 motors
"""

import json
import threading
from datetime import datetime

from st3215 import ST3215

from ..config.constants import (
    CONFIG_FILE,
    DEFAULT_ACC,
    DEFAULT_MOTOR_CONFIG,
    DEFAULT_MOTOR_MAPPING,
    DEFAULT_SPEED,
    MAX_POSITION,
    MIN_POSITION,
)


class MotorController:
    def __init__(self, device="COM3"):
        self.device = device
        self.motor = None
        self.connected = False
        self.found_servos: list[int] = []
        self.current_id: int | None = None
        self.torque_states: dict[int, bool] = {}
        self.joint_positions: dict[int, float] = {i: 0.0 for i in range(1, 7)}
        self.cartesian_position = [0.0, 0.0, 0.0]
        self.motor_config = DEFAULT_MOTOR_CONFIG.copy()
        self.motor_mapping = DEFAULT_MOTOR_MAPPING.copy()
        self._read_lock = threading.Lock()
        self._manual_speed = DEFAULT_SPEED

    def connect(self, port_imports: str | None = None):
        if port_imports is None:
            port_imports = self.device
        try:
            self.motor = ST3215(device=port_imports)
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
            print("Не подключено к устройству")
            return []
        try:
            if self.motor is not None:
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
        from ..config.constants import JOINT_NAMES

        return (
            JOINT_NAMES[joint_index] if joint_index < len(JOINT_NAMES) else f"Сустав {joint_index}"
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
        """Движение по индексу сустава (0-5) — автоматически ищет motor_id."""
        motor_id = self.get_motor_id_for_joint(joint_index)
        return self.move_to_position(motor_id, position, speed, acc)

    def move_motor(self, motor_id: int, position: int, speed=None, acc=DEFAULT_ACC):
        """Движение по реальному ID мотора напрямую.
        Автоматически включает момент (torque) если он был выключен.
        """
        if not self.connected or not self.motor:
            return False
        # Включаем момент если нужно
        if not self.torque_states.get(motor_id, False):
            try:
                with self._read_lock:
                    self.motor.StartServo(motor_id)
                self.torque_states[motor_id] = True
            except Exception as e:
                print(f"⚠️ Не удалось включить момент для мотора {motor_id}: {e}")
        return self.move_to_position(motor_id, position, speed, acc)

    def move_all_joints(self, positions: list[int], speed=DEFAULT_SPEED):
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

    def get_joint_positions(self) -> dict[int, float]:
        return self.joint_positions.copy()

    def read_motor_data(self, sts_id: int) -> dict:
        data: dict[str, int | float | None] = {
            "position": None,
            "temperature": None,
            "voltage": None,
            "current": None,
            "load": None,
            "mode": None,
            "moving": None,
        }
        try:
            if not self.connected and not self.motor:
                return {}
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

    def update_motor_mapping(
        self, joint_index: int, motor_id: int, name: str = "", inverted: bool = False
    ):
        key = f"joint_{joint_index}"
        from ..config.constants import JOINT_NAMES

        default_name = (
            JOINT_NAMES[joint_index] if joint_index < len(JOINT_NAMES) else f"Сустав {joint_index}"
        )
        self.motor_mapping[key] = {
            "motor_id": motor_id,
            "name": name or default_name,
            "min_pos": 0,
            "max_pos": MAX_POSITION,
            "inverted": inverted,
        }

    def get_motor_mapping(self) -> dict:
        return self.motor_mapping.copy()

    def update_motor_config(self, motor_id: int, min_pos: int, max_pos: int, name: str = ""):
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
            with open(filename, encoding="utf-8") as f:
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
