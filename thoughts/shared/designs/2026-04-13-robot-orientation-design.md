---
date: 2026-04-13
topic: "Robot Orientation — Left/Right Configuration"
status: validated
---

# Robot Orientation Design

## Problem Statement

Робот-манипулятор может быть установлен в разных ориентациях относительно базовой системы координат:
- **Front** — стандартная установка (робот смотрит "вперёд")
- **Left** — робот повернут на -90° влево
- **Right** — робот повернут на +90° вправо
- **Back** — робот повернут на 180° назад

Нужно:
1. Добавить настройку ориентации в конфигурацию
2. Учитывать ориентацию в кинематических расчётах
3. Предоставить UI для выбора ориентации

## Constraints

- Сохранить обратную совместимость (по умолчанию orientation = front)
- Минимальные изменения в существующем API кинематики
- Визуальная индикация выбранной ориентации

## Approach

**Выбранный подход: Глобальная трансформация базы**

Добавить поворот базовой системы координат перед расчётом кинематики.

**Преимущества:**
- Прозрачно для остальной логики
- Легко тестировать
- Одно изменение в расчётах

## Architecture

### Data Model

```python
class RobotOrientation(Enum):
    FRONT = 0      # 0°
    LEFT = -90     # -90° (против часовой)
    RIGHT = 90     # +90° (по часовой)
    BACK = 180     # 180°
```

### KinematicsService Changes

**Новый метод:**
```python
def set_orientation(self, orientation: RobotOrientation) -> None
```

**Изменения в forward_kinematics:**
```python
def forward_kinematics(self, angles: list[float]) -> KinematicsResult:
    # Применить трансформацию ориентации
    base_rotation = self._orientation_matrix(self._orientation)
    
    # Расчёт позиций
    positions = self._kinematics.get_all_joint_positions(angles)
    
    # Применить поворот к позициям
    rotated_positions = [
        self._rotate_point(pos, base_rotation) for pos in positions
    ]
```

### MotorMappingPanel Changes

**Новый UI элемент:**
- Выпадающий список или radio buttons для выбора ориентации
- Визуальная схема с направлением
- Сохранение в конфигурацию

```
┌─────────────────────────────────────────────────────────────┐
│ ROBOT ORIENTATION                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│    ← LEFT      FRONT →      RIGHT →      BACK →            │
│   [◉]         [ ]          [ ]          [ ]                │
│                                                             │
│   Current: LEFT (-90°)                                      │
│   Robot is facing to the left side                          │
└─────────────────────────────────────────────────────────────┘
```

### Configuration Changes

**robot_config.json:**
```json
{
  "robot_orientation": "left",
  "orientation_angle": -90,
  ...
}
```

## Components

### RobotOrientation Enum

```python
from enum import Enum

class RobotOrientation(Enum):
    FRONT = 0
    LEFT = -90
    RIGHT = 90
    BACK = 180
    
    @property
    def radians(self) -> float:
        return math.radians(self.value)
    
    @property
    def label(self) -> str:
        return {
            RobotOrientation.FRONT: "Front (0°)",
            RobotOrientation.LEFT: "Left (-90°)",
            RobotOrientation.RIGHT: "Right (+90°)",
            RobotOrientation.BACK: "Back (180°)",
        }[self]
```

### KinematicsService Integration

```python
class KinematicsService:
    def __init__(self):
        self._orientation = RobotOrientation.FRONT
    
    def set_orientation(self, orientation: RobotOrientation) -> None:
        self._orientation = orientation
        self._emit_event("orientation_changed", {"orientation": orientation.value})
    
    def get_orientation(self) -> RobotOrientation:
        return self._orientation
    
    def _orientation_matrix(self, orientation: RobotOrientation) -> np.ndarray:
        """Rotation matrix around Z-axis."""
        angle = orientation.radians
        c, s = math.cos(angle), math.sin(angle)
        return np.array([
            [c, -s, 0],
            [s,  c, 0],
            [0,  0, 1]
        ])
    
    def _rotate_point(self, point: tuple, matrix: np.ndarray) -> tuple:
        """Apply rotation to 3D point."""
        vec = np.array(point)
        rotated = matrix @ vec
        return tuple(rotated)
```

### MotorMappingPanel UI

**Новые элементы:**
- `orientation_var: tk.StringVar` — выбранная ориентация
- Radio buttons для выбора
- Label с текущим значением

**Методы:**
- `_save_orientation()` — сохранение в конфиг
- `_load_orientation()` — загрузка из конфига

## Data Flow

**Загрузка:**
```
1. MotorMappingPanel._load_orientation()
2. Чтение из controller.robot_orientation
3. Установка radio button
4. KinematicsService.set_orientation()
```

**Сохранение:**
```
1. Пользователь выбирает ориентацию
2. _save_orientation() вызывается
3. controller.set_orientation()
4. controller.save_config()
5. KinematicsService обновляется
```

**Расчёт кинематики:**
```
1. forward_kinematics(angles)
2. Расчёт позиций в локальных координатах
3. Применение orientation_matrix
4. Возврат rotated позиций
```

## Error Handling

- Валидация значения ориентации при загрузке
- Default к FRONT при невалидном значении
- Событие "orientation_changed" для обновления UI

## Testing Strategy

1. Выбрать LEFT — проверить поворот на -90°
2. Сохранить конфиг — перезагрузить — проверить восстановление
3. IK расчёт — проверить корректность позиций
