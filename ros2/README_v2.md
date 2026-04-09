# Robot Control v2 - Инструкция по запуску и управлению

## Обзор

Robot Control v2 использует **единый Hardware Interface** (singleton pattern) для всех ROS 2 нод. Это решает проблему конфликтов при подключении к моторам ST3215.

### Ключевые отличия от v1

| Feature | v1 | v2 |
|---------|----|----|
| Подключение к моторам | Каждая нода создаёт своё | Одно shared соединение |
| Конфликты порта | Возможны | Исключены |
| Синхронизация данных | Ручная | Автоматическая через cache |
| Производительность | Низкая (дублирование) | Высокая (shared state) |

---

## Установка

### 1. Установка зависимостей

```bash
# Перейти в рабочую директорию
cd /Users/alexandr/Documents/GitHub/diplome2026/ros2

# Установить пакет в development mode
pip install -e .

# Проверить ROS 2 окружение
ros2 pkg list | grep robot_control
```

### 2. Сборка пакета (опционально для colcon)

```bash
# Если используете colcon
rosdep install --from-paths . --ignore-src -r -y
colcon build --packages-select robot_control
source install/setup.bash
```

---

## Запуск

### Способ 1: Через Launch File (рекомендуется)

```bash
# Базовый запуск (COM3)
ros2 launch robot_control robot_v2.launch.py

# С указанием порта
ros2 launch robot_control robot_v2.launch.py port:=/dev/ttyUSB0

# С полными параметрами
ros2 launch robot_control robot_v2.launch.py port:=COM3 baudrate:=1000000
```

### Способ 2: Отдельные ноды

```bash
# Терминал 1: Запуск robot_node_v2 (инициализирует hardware)
ros2 run robot_control robot_node_v2 --ros-args -p port:=COM3

# Терминал 2: Запуск monitor_node_v2 (использует shared hardware)
ros2 run robot_control monitor_node_v2
```

### Способ 3: Только мониторинг (без управления)

```bash
# Запуск только монитора (использует существующий hardware)
ros2 run robot_control monitor_node_v2
```

---

## Проверка работы

### 1. Проверка топиков

```bash
# Список всех топиков
ros2 topic list

# Ожидаемый вывод:
# /robot/alarms
# /robot/diagnostics
# /robot/joint_states
# /robot/status
# /robot/temperature
```

### 2. Просмотр joint_states

```bash
# Потоковый вывод
ros2 topic echo /robot/joint_states

# Один раз
ros2 topic echo /robot/joint_states --once
```

### 3. Проверка diagnostics

```bash
ros2 topic echo /robot/diagnostics

# Ожидаемый формат:
# data: '{"1": {"position": 2048, "temperature": 45.2, ...}, ...}'
```

### 4. Проверка alarms

```bash
ros2 topic echo /robot/alarms

# Вывод при перегреве:
# data: '[{"motor": 1, "type": "TEMP_WARNING", "value": 72.5}]'
```

---

## Управление

### 1. Отправка команд на движение

```bash
# Двигать все суставы в позицию 0.5 радиан
ros2 topic pub /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.5, 0.0, 0.0, 0.0, 0.0, 0.0]}"

# Движение в домашнюю позицию (все 0)
ros2 topic pub /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"

# Движение с заданной скоростью (через параметры)
ros2 topic pub /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.5, -0.3, 0.2, 0.0, 0.0, 0.0], velocities: [0.1, 0.1, 0.1, 0.1, 0.1, 0.1]}"
```

### 2. Emergency Stop

```bash
# Аварийная остановка
ros2 topic pub /robot/stop std_msgs/Empty "{}"

# Или через Ctrl+C в терминале с нодой
```

### 3. Проверка состояния

```bash
# Просмотр всех нод
ros2 node list

# Инфо о robot_node_v2
ros2 node info /robot_node_v2

# Параметры
ros2 param list /robot_node_v2
ros2 param get /robot_node_v2 port
ros2 param get /robot_node_v2 baudrate
```

---

## Отладка

### 1. Проверка логов

```bash
# Логи в реальном времени
ros2 topic echo /rosout

# Фильтр по ноде
ros2 topic echo /rosout --filter 'node_name == "robot_node_v2"'
```

### 2. Проверка соединения

```bash
# Проверка подключения
ros2 service call /robot/connect std_srvs/SetBool "{data: true}"

# Отключение
ros2 service call /robot/connect std_srvs/SetBool "{data: false}"
```

### 3. Запуск с отладкой

```bash
# Подробный вывод
ros2 run robot_control robot_node_v2 --ros-args --log-level debug

# В файл
ros2 run robot_control robot_node_v2 --ros-args --log-level debug 2>&1 | tee robot.log
```

### 4. Проблемы и решения

| Проблема | Причина | Решение |
|----------|---------|---------|
| `Could not connect to COM3` | Порт занят или неправильный | Проверьте `Get-PnpDevice` |
| `HW not initialized yet` | Нода запущена до robot_node | Запустите robot_node_v2 первым |
| `Cannot move: not connected` | Моторы не подключены | Проверьте питание и кабель |
| Данные не обновляются | Cache устарел | Проверьте rate_hz параметр |

---

## Интеграция с существующим кодом

### Использование из Python

```python
import rclpy
from rclpy.node import Node
from hardware_interface import RobotHWInterface

class MyNode(Node):
    def __init__(self):
        super().__init__('my_node')
        
        # Получаем singleton instance
        self._hw = RobotHWInterface.get_instance()
        
        # Ждём инициализации
        if not self._hw.is_initialized():
            self.get_logger().warn('HW not ready yet')
        
    def move_joints(self, positions):
        """Движение через shared interface."""
        if self._hw.is_connected():
            success = self._hw.write_joint_positions(positions)
            return success
        return False
    
    def read_positions(self):
        """Чтение позиций из cache."""
        states = self._hw.read_joint_states()
        return [s.position_rad for s in states]
```

### Сохранение совместимости с v1

```bash
# v1 и v2 могут работать параллельно (разные порты)
# Но v2 рекомендуется для новых проектов

# Запуск v1 (старый способ)
ros2 run robot_control robot_node

# Запуск v2 (новый способ)
ros2 run robot_control robot_node_v2
```

---

## Тестирование

### Unit тесты

```bash
# Запуск всех тестов
cd /Users/alexandr/Documents/GitHub/diplome2026/ros2
python -m pytest tests/test_hw_interface.py -v

# Конкретный тест
python -m pytest tests/test_hw_interface.py::TestRobotHWInterface::test_singleton_pattern -v
```

### Ручное тестирование

```bash
# 1. Проверка singleton
cd /Users/alexandr/Documents/GitHub/diplome2026/ros2
python -c "
from robot_control.hardware_interface import RobotHWInterface
hw1 = RobotHWInterface.get_instance()
hw2 = RobotHWInterface.get_instance()
print(f'Same instance: {hw1 is hw2}')
print(f'ID1: {id(hw1)}, ID2: {id(hw2)}')
"

# 2. Проверка конверсии
python -c "
from robot_control.hardware_interface import RobotHWInterface
for pos in [0, 1024, 2048, 3072, 4095]:
    rad = RobotHWInterface._position_to_rad(pos)
    back = RobotHWInterface._rad_to_position(rad)
    print(f'Pos {pos:4d} -> {rad:.4f} rad -> {back} pos')
"
```

---

## API Reference

### RobotHWInterface

```python
# Получение instance
hw = RobotHWInterface.get_instance()

# Инициализация
success = hw.initialize(port="COM3", baudrate=1000000, monitor_rate_hz=50.0)

# Проверка состояния
is_ready = hw.is_initialized()
is_connected = hw.is_connected()

# Чтение данных
states = hw.read_joint_states()  # List[JointState]
motor_data = hw.get_motor_data(1)  # MotorData
all_data = hw.get_all_motor_data()  # Dict[int, MotorData]

# Запись команд
success = hw.write_joint_positions([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

# Безопасность
hw.emergency_stop()
hw.shutdown()
```

### JointState

```python
@dataclass
class JointState:
    position_rad: float      # Позиция в радианах
    velocity_rad_s: float    # Скорость в рад/с
    effort: float            # Усилие
    position_raw: int        # Позиция мотора (0-4095)
```

---

## Сравнение производительности

### v1 (старый способ)

```bash
# Запуск
ros2 launch robot_control robot.launch.py

# Проблемы:
# - Две ноды = два serial соединения
# - Конфликты при одновременной записи
# - Несинхронизированные данные
```

### v2 (новый способ)

```bash
# Запуск
ros2 launch robot_control robot_v2.launch.py

# Преимущества:
# - Одно serial соединение
# - Shared cache с thread-safe доступом
# - Консистентные данные между нодами
```

---

## Что дальше

1. **Phase 2** — Action Server для траекторий
2. **Phase 3** — Safety Limits
3. **Phase 4** — ros2_control интеграция

Смотри design документы в:
- `/Users/alexandr/Documents/GitHub/diplome2026/thoughts/shared/designs/`
