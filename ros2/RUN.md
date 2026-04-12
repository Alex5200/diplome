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

Или через Диспетчер устройств:
1. Нажмите `Win + X` → `Диспетчер устройств`
2. Найдите раздел "Порты (COM и LPT)"
3. Запомните номер COM порта

### 2. Установка ROS 2 Humble

#### Вариант A: ROS 2 + Docker (рекомендуется)

```powershell
# 1. Установите Docker Desktop
# https://docs.docker.com/desktop/install/windows-install/

# 2. Проверьте установку
docker --version

# 3. Перейдите в папку проекта
cd C:\Users\SahaA\Documents\GitHub\diplome\ros2

# 4. Соберите образ
make docker-build

# 5. Запустите контейнер
make docker-run USB_DEVICE=COM3
```

#### Вариант B: Нативная установка

```powershell
# 1. Установите Chocolatey (если нет)
Set-ExecutionPolicy Bypass -Scope Process -Force
iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

# 2. Установите ROS 2
choco install ros-humble-ros-base -y

# 3. Или скачайте вручную:
# https://github.com/ros2/ros2/releases

# 4. Инициализируйте ROS
call C:\opt\ros\humble\setup.bat

# 5. Установите пакет
cd C:\Users\SahaA\Documents\GitHub\diplome\ros2
colcon build --packages-select robot_control
call install\setup.bat
```

### 3. Запуск

#### Docker

```powershell
# Терминал 1: Запуск robot_node
make docker-run USB_DEVICE=COM3
# Внутри контейнера:
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash
ros2 run robot_control robot_node_v2 --ros-args -p port:=COM3
```

```powershell
# Терминал 2: Публикация команд (с host машины)
make pub-cmd-all POSITIONS='[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]'
```

```powershell
# Или через docker exec
make docker-exec
# Затем внутри:
source /opt/ros/humble/setup.bash && ros2 topic list
```

#### Нативная установка

```powershell
# Терминал 1: Robot node
call C:\opt\ros\humble\setup.bat
call install\setup.bat
ros2 run robot_control robot_node_v2 --ros-args -p port:=COM3

# Терминал 2: Мониторинг
call C:\opt\ros\humble\setup.bat
call install\setup.bat
ros2 topic echo /robot/joint_states

# Терминал 3: Команды
call C:\opt\ros\humble\setup.bat
call install\setup.bat
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"
```

### 4. Управление

```powershell
# Движение в home position
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"

# Движение в ready позицию
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, -0.5, 0.8, 0.0, 0.5, 0.0]}"

# Кастомная позиция
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.5, -0.3, 0.2, 0.0, 0.0, 0.0]}"

# Emergency stop
ros2 topic pub --once /robot/stop std_msgs/Empty "{}"
```

### 5. Проверка

```powershell
# Список топиков
ros2 topic list

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

# Или более подробно
dmesg | grep -i usb | tail -20

# Найти ST3215
lsusb | grep -i st
# или
lsusb | grep -i robot
```

Обычно устройство: `/dev/ttyUSB0`

### 2. Права доступа к USB

```bash
# Добавить пользователя в группу dialout
sudo usermod -a -G dialout $USER

# Или дать права напрямую
sudo chmod 666 /dev/ttyUSB0

# Проверить
ls -la /dev/ttyUSB0
# Должно быть: crw-rw-rw-
```

**Перелогиньтесь** после добавления в группу.

### 3. Установка ROS 2 Humble

#### Вариант A: Docker (рекомендуется)

```bash
# 1. Установите Docker
sudo apt update
sudo apt install -y docker.io docker-compose

# 2. Добавьте пользователя в группу docker
sudo usermod -a -G docker $USER
# Перелогиньтесь

# 3. Проверьте
docker --version

# 4. Перейдите в папку проекта
cd ~/Documents/GitHub/diplome/ros2

# 5. Соберите образ
make docker-build

# 6. Запустите с USB
make docker-run USB_DEVICE=/dev/ttyUSB0
```

#### Вариант B: Нативная установка

```bash
# 1. Установите ROS 2 Humble
# https://docs.ros.org/en/humble/Installation.html

# Быстрая установка:
sudo apt update
sudo apt install -y curl
curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | sudo gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install -y ros-humble-ros-base python3-colcon-common-extensions

# 2. Source ROS
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc

# 3. Установите пакет
cd ~/Documents/GitHub/diplome/ros2
colcon build --packages-select robot_control
source install/setup.bash
```

### 4. Запуск

#### Docker

```bash
# Терминал 1: Запуск контейнера с USB
make docker-run USB_DEVICE=/dev/ttyUSB0

# Внутри контейнера:
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash
ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0
```

```bash
# Терминал 2: Публикация команд (с host)
make pub-cmd-all POSITIONS='[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]'
```

```bash
# Или exec в контейнер
make docker-exec
# Затем:
source /opt/ros/humble/setup.bash && ros2 topic list
```

#### Полный USB доступ (Linux)

Если `/dev/ttyUSB0` не работает, попробуйте:

```bash
# Запуск с --privileged
make docker-run-usb
```

Или вручную:

```bash
docker run -it --rm \
  --name robot_control \
  --privileged \
  -v /dev/bus/usb:/dev/bus/usb \
  robot_control_dev
```

#### Нативная установка

```bash
# Терминал 1: Robot node
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0

# Терминал 2: Мониторинг
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 topic echo /robot/joint_states

# Терминал 3: Команды
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"
```

### 5. Управление

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

### 6. Проверка

```bash
# Список топиков
ros2 topic list

# Проверка joint_states
ros2 topic echo /robot/joint_states

# Проверка status
ros2 topic echo /robot/status

# Частота топиков
ros2 topic hz /robot/joint_states
```

---

## Использование Makefile

### Найти USB

```bash
make list-usb
```

### Docker команды

```bash
make docker-build       # Собрать образ
make docker-run         # Запустить контейнер
make docker-exec       # Shell в контейнер
make docker-robot      # Запустить robot node
make docker-topics     # Список топиков
make docker-stop       # Emergency stop
make docker-clean      # Остановить контейнер
```

### Нативные команды

```bash
make list-topics       # ros2 topic list
make echo-joints       # ros2 topic echo /robot/joint_states
make pub-home          # Home position
make pub-ready         # Ready position
make stop              # Emergency stop
make run-robot         # Запустить robot_node_v2
make run-monitor       # Запустить monitor_node_v2
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

## Troubleshooting

### Windows

| Проблема | Решение |
|----------|---------|
| Docker не запускается | Включите WSL2 в BIOS или Hyper-V |
| `COM3 не найден` | Проверьте через `Get-PnpDevice` |
| Нет прав на COM порт | Запустите от администратора |
| Контейнер не видит USB | Используйте `--privileged` |

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
| `Cannot move: not connected` | Проверьте подключение |
| Topic не найден | Подождите 1-2 сек после запуска |

---

## Быстрый старт (COPY-PASTE)

### Windows (Docker)

```powershell
cd C:\Users\SahaA\Documents\GitHub\diplome\ros2
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB' }
make docker-build
make docker-run USB_DEVICE=COM3
```
Внутри контейнера:
```bash
source /opt/ros/humble/setup.bash && source /ws/install/setup.bash && ros2 run robot_control robot_node_v2 --ros-args -p port:=COM3
```

### Linux (Docker)

```bash
cd ~/Documents/GitHub/diplome/ros2
ls -la /dev/ttyUSB*
sudo chmod 666 /dev/ttyUSB0
make docker-build
make docker-run USB_DEVICE=/dev/ttyUSB0
```
Внутри контейнера:
```bash
source /opt/ros/humble/setup.bash && source /ws/install/setup.bash && ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0
```

---

## Terminal UI (TUI)

Интерактивный интерфейс для управления роботом через терминал.

### Запуск

```bash
cd ros2
make docker-tui
```

Или вручную:
```bash
docker run -it --rm \
    --privileged \
    -v $(pwd)/robot_tui.py:/robot_tui.py \
    robot_control_dev bash -c "source /opt/ros/humble/setup.bash && source /ws/install/setup.bash && python3 /robot_tui.py"
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

### Robot + TUI вместе

```bash
# Запустить robot node в фоне + TUI
make docker-all

# Или вручную:
# Терминал 1:
docker run -d --rm --name robot_control-robot --privileged robot_control_dev bash -c "source /opt/ros/humble/setup.bash && source /ws/install/setup.bash && ros2 run robot_control robot_node_v2"

# Терминал 2:
make docker-tui
```

### Robot Node отдельно

```bash
# В фоне
make docker-robot

# Или вручную в контейнере:
docker run -it --rm --privileged robot_control_dev bash -c "source /opt/ros/humble/setup.bash && source /ws/install/setup.bash && ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0"
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
# Движение в home
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"

# Движение в ready
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.0, -0.5, 0.8, 0.0, 0.5, 0.0]}"

# Кастомная позиция
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint "{positions: [0.5, -0.3, 0.2, 0.0, 0.0, 0.0]}"

# Emergency stop
ros2 topic pub --once /robot/stop std_msgs/Empty "{}"

# Мониторинг
ros2 topic echo /robot/joint_states
ros2 topic echo /robot/status
```
