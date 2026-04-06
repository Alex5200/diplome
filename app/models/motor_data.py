#!/usr/bin/env python3

"""
Motor Data Models

Модели данных для моторов и программы.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# Температурные пороги (дублируем, чтобы не было кругового импорта)
TEMP_WARNING = 70
TEMP_CRITICAL = 80
LOAD_WARNING = 80


class MotorStatus(Enum):
    """Статус мотора."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass
class MotorData:
    """
    Данные мотора ST3215.

    Attributes:
        motor_id: ID мотора в шине
        position: Текущая позиция (0-4095)
        temperature: Температура в градусах C
        voltage: Напряжение в вольтах
        current: Ток в амперах
        load: Нагрузка в процентах
        mode: Режим работы
        moving: Флаг движения
        torque_enabled: Момент включен
        last_update: Время последнего обновления
        error_count: Счетчик ошибок
    """

    motor_id: int
    position: int | None = None
    temperature: float | None = None
    voltage: float | None = None
    current: float | None = None
    load: float | None = None
    mode: int | None = None
    moving: bool | None = None
    torque_enabled: bool = False
    last_update: float = 0.0
    error_count: int = 0

    # Вычисляемые поля
    _status: MotorStatus | None = field(default=None, init=False)

    def __post_init__(self):
        self._status = self._calculate_status()

    def _calculate_status(self) -> MotorStatus:
        """Вычисление статуса на основе данных."""
        if self.position is None:
            return MotorStatus.DISCONNECTED
        if self.temperature is not None and self.temperature >= TEMP_CRITICAL:
            return MotorStatus.ERROR
        if self.load is not None and self.load >= LOAD_WARNING:
            return MotorStatus.WARNING
        if self.temperature is not None and self.temperature >= TEMP_WARNING:
            return MotorStatus.WARNING
        return MotorStatus.OK

    @property
    def status(self) -> MotorStatus:
        """Текущий статус мотора."""
        return self._calculate_status()

    @property
    def status_icon(self) -> str:
        """Иконка статуса для UI."""
        icons = {
            MotorStatus.OK: "✅",
            MotorStatus.WARNING: "⚠️",
            MotorStatus.ERROR: "❌",
            MotorStatus.DISCONNECTED: "⭕",
        }
        return icons.get(self.status, "❓")

    def is_overheating(self) -> bool:
        """Проверка перегрева."""
        return self.temperature is not None and self.temperature >= TEMP_CRITICAL

    def is_overloaded(self) -> bool:
        """Проверка перегрузки."""
        return self.load is not None and self.load >= LOAD_WARNING

    def is_moving(self) -> bool:
        """Проверка движения."""
        return self.moving is True

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь."""
        data = asdict(self)
        data["status"] = self.status.value
        data["status_icon"] = self.status_icon
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MotorData":
        """Создание из словаря."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class JointState:
    """
    Состояние сустава робота.

    Attributes:
        index: Индекс сустава (0-5)
        name: Название сустава
        angle_deg: Угол в градусах
        position: Позиция мотора (0-4095)
        motor_id: ID связанного мотора
    """

    index: int
    name: str
    angle_deg: float = 0.0
    position: int = 2048
    motor_id: int = 0
    min_angle: float = -180.0
    max_angle: float = 180.0

    def to_motor_position(self, angle: float) -> int:
        """Конвертация угла в позицию мотора."""
        normalized = (angle - self.min_angle) / (self.max_angle - self.min_angle)
        return int(normalized * 4095)

    def to_angle(self, position: int) -> float:
        """Конвертация позиции в угол."""
        normalized = position / 4095.0
        return self.min_angle + normalized * (self.max_angle - self.min_angle)


@dataclass
class RobotState:
    """
    Состояние всего робота.

    Агрегирует данные всех моторов и суставов.
    """

    joints: list[JointState] = field(default_factory=list)
    motors: dict[int, MotorData] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    is_connected: bool = False
    is_moving: bool = False

    @property
    def all_motors_ok(self) -> bool:
        """Все ли моторы в норме."""
        return all(motor.status == MotorStatus.OK for motor in self.motors.values())

    @property
    def any_motor_warning(self) -> bool:
        """Есть ли предупреждения."""
        return any(motor.status == MotorStatus.WARNING for motor in self.motors.values())

    @property
    def any_motor_error(self) -> bool:
        """Есть ли ошибки."""
        return any(motor.status == MotorStatus.ERROR for motor in self.motors.values())

    def get_joint_angles(self) -> list[float]:
        """Получение углов всех суставов."""
        return [joint.angle_deg for joint in self.joints]

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "joints": [asdict(j) for j in self.joints],
            "motors": {k: v.to_dict() for k, v in self.motors.items()},
            "timestamp": self.timestamp.isoformat(),
            "is_connected": self.is_connected,
            "is_moving": self.is_moving,
            "status": {
                "all_ok": self.all_motors_ok,
                "any_warning": self.any_motor_warning,
                "any_error": self.any_motor_error,
            },
        }


@dataclass
class ProgramBlock:
    """
    Блок программы для блочного программирования.

    Attributes:
        id: Уникальный ID блока
        block_type: Тип блока (move_to, wait, torque, etc.)
        params: Параметры блока
        order: Порядок выполнения
    """

    id: int
    block_type: str
    params: dict[str, Any]
    order: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "id": self.id,
            "type": self.block_type,
            "params": self.params,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgramBlock":
        """Создание из словаря."""
        return cls(
            id=data.get("id", 0),
            block_type=data.get("type", ""),
            params=data.get("params", {}),
            order=data.get("order", 0),
        )


@dataclass
class RobotProgram:
    """
    Программа выполнения последовательности действий.
    """

    name: str = ""
    blocks: list[ProgramBlock] = field(default_factory=list)
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    version: str = "1.0"

    def add_block(self, block: ProgramBlock) -> None:
        """Добавление блока."""
        self.blocks.append(block)
        self.modified = datetime.now()

    def remove_block(self, block_id: int) -> bool:
        """Удаление блока."""
        for i, block in enumerate(self.blocks):
            if block.id == block_id:
                self.blocks.pop(i)
                self.modified = datetime.now()
                return True
        return False

    def clear(self) -> None:
        """Очистка программы."""
        self.blocks.clear()
        self.modified = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "name": self.name,
            "blocks": [b.to_dict() for b in self.blocks],
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RobotProgram":
        """Создание из словаря."""
        program = cls(
            name=data.get("name", ""),
            created=datetime.fromisoformat(data["created"])
            if "created" in data
            else datetime.now(),
            modified=datetime.fromisoformat(data["modified"])
            if "modified" in data
            else datetime.now(),
            version=data.get("version", "1.0"),
        )
        program.blocks = [ProgramBlock.from_dict(b) for b in data.get("blocks", [])]
        return program
