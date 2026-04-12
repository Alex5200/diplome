# Инструкция по запуску Robot Control

Выберите вашу ОС:
- [Windows](#windows)
- [Linux](#linux)

---

## Windows

### 1. Найти COM порт робота

Откройте PowerShell и выполните:

```powershell
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB' }
```

Найдите устройство ST3215 (обычно `COM3`, `COM4` и т.д.).

### 2. Установка Docker

1. Установите **Docker Desktop**: https://docs.docker.com/desktop/install/windows-install/
2. Проверьте установку:
```powershell
docker --version
```

### 3. Сборка и запуск

```powershell
# Перейдите в папку проекта
cd C:\Users\SahaA\Documents\GitHub\diplome\ros2

# Соберите Docker образ
make docker-build

# Запустите контейнер
make docker-run
```

### 4. Запуск robot node

Внутри контейнера:

```bash
# Инициализируйте ROS2
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash

# Запустите robot node
ros2 run robot_control robot_node_v2 --ros-args -p port:=COM3
```

### 5. Управление (из другого терминала)

```powershell
# Home position
make pub-home

# Ready позиция
make pub-ready

# Кастомная позиция
make pub-cmd-all POSITIONS='[0.0, -0.5, 0.8, 0.0, 0.5, 0.0]'

# Emergency stop
make docker-stop
```

### 6. Terminal UI (TUI)

```powershell
# Robot node в фоне + TUI
make docker-all

# Или только TUI
make docker-tui
```

### 7. Проверка

```bash
# Список топиков
make docker-topics

# Проверка joint_states
ros2 topic echo /robot/joint_states

# Проверка status
ros2 topic echo /robot/status
```

---

## Linux

### 1. Найти USB устройство робота

```bash
# Посмотреть все USB serial устройства
ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "No USB serial devices"

# Более подробно
dmesg | grep -i usb | tail -20
```

Обычно устройство: `/dev/ttyUSB0`

### 2. Права доступа к USB

```bash
# Добавить пользователя в группу dialout
sudo usermod -a -G dialout $USER

# Или дать права напрямую
sudo chmod 666 /dev/ttyUSB0

# Перелогиньтесь после добавления в группу
```

### 3. Установка Docker

```bash
# Установите Docker
sudo apt update
sudo apt install -y docker.io docker-compose

# Добавьте пользователя в группу docker
sudo usermod -a -G docker $USER
# Перелогиньтесь

# Проверьте
docker --version
```

### 4. Сборка и запуск

```bash
# Перейдите в папку проекта
cd ~/Documents/GitHub/diplome/ros2

# Соберите Docker образ
make docker-build

# Запустите контейнер
make docker-run
```

### 5. Запуск robot node

Внутри контейнера:

```bash
# Инициализируйте ROS2
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash

# Запустите robot node
ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0
```

### 6. Управление (из другого терминала)

```bash
# Home position
make pub-home

# Ready позиция
make pub-ready

# Кастомная позиция
make pub-cmd-all POSITIONS='[0.0, -0.5, 0.8, 0.0, 0.5, 0.0]'

# Emergency stop
make docker-stop
```

### 7. Terminal UI (TUI)

```bash
# Robot node в фоне + TUI
make docker-all

# Или только TUI
make docker-tui
```

### 8. Полный USB доступ

Если `/dev/ttyUSB0` не работает:

```bash
# Запуск с --privileged
make docker-run-usb
```

### 9. Проверка

```bash
# Список топиков
make docker-topics

# Проверка joint_states
ros2 topic echo /robot/joint_states

# Частота топиков
ros2 topic hz /robot/joint_states
```

---

## Нативная установка (без Docker)

### Windows

```powershell
# 1. Установите ROS 2 Humble
# https://docs.ros.org/en/humble/Installation.html

# 2. Или через Chocolatey
choco install ros-humble-ros-base -y

# 3. Установите пакет
cd C:\Users\SahaA\Documents\GitHub\diplome\ros2
colcon build --packages-select robot_control
call install\setup.bat

# 4. Запуск
call C:\opt\ros\humble\setup.bat
ros2 run robot_control robot_node_v2 --ros-args -p port:=COM3
```

### Linux

```bash
# 1. Установите ROS 2 Humble
# https://docs.ros.org/en/humble/Installation.html

# 2. Установите пакет
cd ~/Documents/GitHub/diplome/ros2
colcon build --packages-select robot_control
source install/setup.bash

# 3. Запуск
source /opt/ros/humble/setup.bash
ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0
```

---

## Makefile команды

### Docker

```bash
make docker-build       # Собрать образ
make docker-run         # Запустить контейнер
make docker-run-usb     # Запустить с полным USB доступом
make docker-exec        # Shell в контейнер
make docker-tui         # Запустить TUI
make docker-all         # Robot + TUI вместе
make docker-robot       # Запустить robot node
make docker-topics      # Список топиков
make docker-stop        # Emergency stop
make docker-clean       # Остановить контейнер
```

### Хост машина

```bash
make pub-home           # Home position
make pub-ready          # Ready position
make pub-cmd-all       # Кастомная позиция
make list-topics        # ros2 topic list
make echo-joints        # ros2 topic echo
```

### Переменные

```bash
# Windows
make docker-run USB_DEVICE=COM3
make pub-cmd-all POSITIONS='[0.0, 0.5, 1.0, -0.5, 0.3, 0.0]'

# Linux
make docker-run USB_DEVICE=/dev/ttyUSB0
make pub-cmd-all POSITIONS='[0.0, 0.5, 1.0, -0.5, 0.3, 0.0]'
```

---

## Terminal UI (TUI)

Rich-based интерактивный интерфейс для управления роботом.

### Запуск

```bash
# Robot + TUI вместе
make docker-all

# Или только TUI
make docker-tui
```

### Управление

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

## ROS2 Topics API

### Опубликованные топики (robot_node_v2)

| Топик | Тип | Описание |
|-------|------|---------|
| `/robot/joint_states` | sensor_msgs/JointState | Текущие позиции 6 суставов |
| `/robot/status` | std_msgs/String | JSON статус робота |

### Подписки (robot_node_v2)

| Топик | Тип | Описание |
|-------|------|---------|
| `/robot/joint_cmd` | trajectory_msgs/JointTrajectoryPoint | Команда на движение |
| `/robot/stop` | std_msgs/Empty | Emergency stop |

### Примеры команд

```bash
# Home position
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"

# Ready позиция
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, -0.5, 0.8, 0.0, 0.5, 0.0]}"

# Кастомная позиция
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.5, -0.3, 0.2, 0.0, 0.0, 0.0]}"

# Emergency stop
ros2 topic pub --once /robot/stop std_msgs/Empty "{}"
```

---

## Troubleshooting

### Windows

| Проблема | Решение |
|----------|---------|
| Docker не запускается | Включите WSL2 в BIOS или Hyper-V |
| `COM3 не найден` | Проверьте через `Get-PnpDevice` |
| Нет прав на COM порт | Запустите от администратора |
| Контейнер не видит USB | Используйте `make docker-run-usb` |

### Linux

| Проблема | Решение |
|----------|---------|
| `/dev/ttyUSB0: Permission denied` | `sudo chmod 666 /dev/ttyUSB0` или добавьте в группу `dialout` |
| `docker: permission denied` | `sudo usermod -a -G docker $USER` и перелогиньтесь |
| USB не определяется | Проверьте кабель, попробуйте другой |
| Контейнер не видит USB | Используйте `make docker-run-usb` |

### Общие

| Проблема | Решение |
|----------|---------|
| `Could not connect` | Проверьте порт и питание робота |
| `HW not initialized` | Запустите robot_node первым |
| Topic не найден | Подождите 1-2 сек после запуска |

---

## Быстрый старт (COPY-PASTE)

### Windows (Docker)

```powershell
cd C:\Users\SahaA\Documents\GitHub\diplome\ros2
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB' }
make docker-build
make docker-run
```

Внутри контейнера:
```bash
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash
ros2 run robot_control robot_node_v2 --ros-args -p port:=COM3
```

### Linux (Docker)

```bash
cd ~/Documents/GitHub/diplome/ros2
ls -la /dev/ttyUSB*
sudo chmod 666 /dev/ttyUSB0
make docker-build
make docker-run
```

Внутри контейнера:
```bash
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash
ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0
```
