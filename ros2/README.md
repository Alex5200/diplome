# Robot Control ROS2 Package

> **Важно:** Пути в примерах замените на свои.

## Сборка пакета (colcon build)

### Требования

- ROS2 Humble (или другой дистрибутив)
- Python 3.8+
- st3215 пакет: `pip install st3215`

### Сборка

```bash
# 1. Перейдите в директорию пакета
cd ~/Documents/GitHub/diplome/ros2

# 2. Установите зависимости
rosdep install --from-paths . --ignore-src -r -y

# 3. Сборка через colcon
colcon build --packages-select robot_control

# 4. Source установочного файла
source install/setup.bash
```

### Запуск после сборки

```bash
# Запуск robot node
ros2 run robot_control robot_node --ros-args -p port:=/dev/ttyUSB0

# Запуск monitor node (в другом терминале)
ros2 run robot_control monitor_node --ros-args -p port:=/dev/ttyUSB0

# Проверка топиков
ros2 topic list
ros2 topic echo /robot/joint_states
```

### Альтернативная сборка (без colcon)

```bash
# Установка в режиме development
pip install -e .

# Запуск напрямую
python -m robot_control.robot_node --ros-args -p port:=/dev/ttyUSB0
```

---

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

## Быстрый старт (Docker)

### Windows

```powershell
cd C:\Users\SahaA\Documents\GitHub\diplome\ros2

# 1. Собрать образ
make docker-build

# 2. Запустить контейнер
make docker-run

# 3. Внутри контейнера - запустить robot node
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash
ros2 run robot_control robot_node_v2 --ros-args -p port:=COM3
```

### Linux

```bash
cd ~/Documents/GitHub/diplome/ros2

# 1. Собрать образ
make docker-build

# 2. Запустить контейнер
make docker-run

# 3. Внутри контейнера - запустить robot node
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash
ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0
```

---

## Найти USB устройство

### Windows

```powershell
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB' }
```

### Linux

```bash
ls -la /dev/ttyUSB* /dev/ttyACM*
```

---

## Управление роботом

### Из другого терминала (host machine)

```bash
# Список топиков
make docker-topics

# Home position (все нули)
make pub-home

# Ready позиция
make pub-ready

# Кастомная позиция
make pub-cmd-all POSITIONS='[0.0, -0.5, 0.8, 0.0, 0.5, 0.0]'

# Emergency stop
make docker-stop
```

### Terminal UI (TUI)

Интерактивный интерфейс с Rich:

```bash
# Запустить robot node в фоне + TUI
make docker-all

# Или отдельно TUI
make docker-tui
```

**Управление TUI:**
```
j/J         - Выбрать prev/next сустав (1-6)
a/z         - Decrease/Increase позицию (0.1 rad)
A/Z         - Decrease/Increase позицию (1.0 rad)
1-6         - Выбрать сустав напрямую
h           - Go to HOME (все нули)
r           - Go to READY position [0, -0.5, 0.8, 0, 0.5, 0]
s           - EMERGENCY STOP
t           - Toggle torque
q           - Quit (выход)
```

---

## Нативная установка (без Docker)

### Установка зависимостей

```bash
cd ~/Documents/GitHub/diplome/ros2

# Установить пакет в development mode
pip install -e .

# Или собрать через colcon
rosdep install --from-paths . --ignore-src -r -y
colcon build --packages-select robot_control
source install/setup.bash
```

### Запуск

```bash
# Терминал 1: Robot node
ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0

# Терминал 2: Проверка
ros2 topic echo /robot/joint_states

# Терминал 3: Команды
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"
```

---

## ROS2 Topics API

### Опубликованные топики

| Топик | Тип | Описание |
|-------|------|---------|
| `/robot/joint_states` | sensor_msgs/JointState | Текущие позиции 6 суставов |
| `/robot/status` | std_msgs/String | JSON статус робота |

### Подписки

| Топик | Тип | Описание |
|-------|------|---------|
| `/robot/joint_cmd` | trajectory_msgs/JointTrajectoryPoint | Команда на движение |
| `/robot/stop` | std_msgs/Empty | Emergency stop |

---

## Makefile

### Основные команды

```bash
make help              # Справка
make docker-build     # Собрать Docker образ
make docker-run       # Запустить контейнер
make docker-exec     # Shell в контейнер
make docker-tui       # Запустить TUI
make docker-all       # Robot + TUI вместе
make docker-robot     # Запустить robot node
make docker-topics    # Список топиков
make docker-stop      # Emergency stop
make docker-clean     # Остановить контейнер

# Публикация команд
make pub-home         # Home position
make pub-ready        # Ready position
make pub-cmd-all      # Кастомная позиция
```

### Переменные

```bash
USB_DEVICE=COM3         # USB устройство
POSITIONS='[0.0, 0.5, 1.0, -0.5, 0.3, 0.0]'  # Позиции
```

---

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| Docker не запускается | Включите WSL2/Hyper-V |
| USB не найден | Проверьте через `Get-PnpDevice` |
| `/dev/ttyUSB0: Permission denied` | `sudo chmod 666 /dev/ttyUSB0` |
| Контейнер не видит USB | Используйте `make docker-run-usb` |
| `Could not connect` | Проверьте порт и питание робота |
| Topic не найден | Подождите 1-2 сек после запуска |

---

## Интеграция с существующим кодом

### Использование из Python

```python
import rclpy
from rclpy.node import Node
from robot_control.hardware_interface import RobotHWInterface

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
```

---

## Структура файлов

```
ros2/
├── dockerfile           # Docker образ с ROS2 Humble
├── build_docker.sh      # Скрипт сборки
├── Makefile             # Команды для Docker
├── robot_tui.py         # Rich-based Terminal UI
├── RUN.md               # Подробная инструкция по запуску
├── README_v2.md         # Этот файл
├── package.xml          # ROS2 package.xml
├── setup.py             # Python package setup
├── robot_control/       # ROS2 ноды
│   ├── hardware_interface.py
│   ├── robot_node_v2.py
│   └── monitor_node_v2.py
└── launch/              # Launch файлы
    └── robot_v2.launch.py
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

# Запись команд
success = hw.write_joint_positions([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

# Безопасность
hw.emergency_stop()
hw.shutdown()
```

---

## Следующие шаги

1. **Phase 2** — Action Server для траекторий
2. **Phase 3** — Safety Limits
3. **Phase 4** — ros2_control интеграция

Смотри design документы в `/docs/plans/`.
