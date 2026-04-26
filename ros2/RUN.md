# Запуск Robot Control

## Быстрый старт (Ubuntu + Docker)

```bash
# 1. Найти USB-порт робота
ls /dev/ttyUSB* /dev/ttyACM*

# 2. Собрать образ (один раз)
cd ~/Documents/GitHub/diplome/ros2
make docker-build

# 3. Запустить робот + TUI в одном контейнере
make docker-all USB_DEVICE=/dev/ttyUSB0
```

Всё. В одном терминале запускается `robot_node_v2` в фоне и `robot_tui.py` интерактивно.

---

## Содержание

- [Требования](#требования)
- [Найти USB-порт](#найти-usb-порт)
- [Права доступа к USB](#права-доступа-к-usb)
- [Сборка Docker-образа](#сборка-docker-образа)
- [Способ 1 — всё в одном контейнере (рекомендуется)](#способ-1--всё-в-одном-контейнере)
- [Способ 2 — два отдельных контейнера](#способ-2--два-отдельных-контейнера)
- [Способ 3 — вручную внутри контейнера](#способ-3--вручную-внутри-контейнера)
- [TUI — управление](#tui--управление)
- [Makefile — все команды](#makefile--все-команды)
- [ROS2 Topics API](#ros2-topics-api)
- [Troubleshooting](#troubleshooting)

---

## Требования

- Ubuntu 20.04 / 22.04 / 24.04
- Docker Engine ≥ 24.0
- USB-кабель к роботу ST3215

### Установка Docker

```bash
sudo apt update
sudo apt install -y docker.io

# Добавить себя в группу docker (чтобы не нужен sudo)
sudo usermod -aG docker $USER
newgrp docker          # применить без перелогина

docker --version       # проверить
```

---

## Найти USB-порт

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
# Обычно: /dev/ttyUSB0

# Подробно:
dmesg | grep -i tty | tail -10
```

Запомните порт — он нужен везде как `USB_DEVICE=`.

---

## Права доступа к USB

```bash
# Добавить пользователя в группу dialout (постоянно)
sudo usermod -aG dialout $USER
newgrp dialout

# Или временно для текущей сессии
sudo chmod 666 /dev/ttyUSB0
```

---

## Сборка Docker-образа

```bash
cd ~/Documents/GitHub/diplome/ros2
make docker-build
```

Сборка занимает 3–7 минут (скачивает `osrf/ros:humble-desktop`).
Повторять только при изменении кода или зависимостей.

---

## Способ 1 — всё в одном контейнере

**Рекомендуется.** Робот-нода и TUI работают в одном процессе — ROS2 DDS видит обоих без сети.

```bash
make docker-all USB_DEVICE=/dev/ttyUSB0
```

Что происходит внутри:
1. `robot_node_v2` стартует в фоне на порту `/dev/ttyUSB0`
2. Пауза 2 секунды
3. `robot_tui.py` запускается интерактивно

Для остановки нажмите `q` в TUI или `Ctrl+C`.

---

## Способ 2 — два отдельных контейнера

Используйте если нужно запустить TUI в другом терминале.
Работает через `--network host` (только Linux).

**Терминал 1 — робот:**

```bash
make docker-robot-bg USB_DEVICE=/dev/ttyUSB0
# Контейнер запускается в фоне
```

**Терминал 2 — TUI:**

```bash
make docker-tui
```

**Важно:** оба контейнера используют `--network host` и `ROS_DOMAIN_ID=42` — это позволяет им видеть друг друга через DDS.

---

## Способ 3 — вручную внутри контейнера

Для отладки и разработки.

```bash
# Открыть shell в контейнере
make docker-shell USB_DEVICE=/dev/ttyUSB0

# Внутри контейнера:
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash
export PYTHONPATH=/ws/app:$PYTHONPATH

# Запустить робот-ноду (в одном окне / tmux)
ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0

# В другом окне (docker exec из второго терминала)
python3 /ws/robot_tui.py
```

Если хотите два окна в одном контейнере — используйте `tmux`:

```bash
# Внутри контейнера
tmux new-session -d -s robot 'ros2 run robot_control robot_node_v2 --ros-args -p port:=/dev/ttyUSB0'
python3 /ws/robot_tui.py
```

---

## TUI — управление

TUI работает через простой `input()` — вводите команду и нажимаете Enter.

```
  Команды
  ────────
  1-6       выбрать сустав (> показывает текущий)
  a / z     двигать выбранный сустав  -0.1 / +0.1 рад
  A / Z     двигать выбранный сустав  -0.5 / +0.5 рад
  h         позиция HOME  [0, 0, 0, 0, 0, 0]
  r         позиция READY [0, -0.5, 0.8, 0, 0.5, 0]
  s         EMERGENCY STOP
  p         напечатать текущее состояние
  ?         показать помощь
  q         выйти
```

Пример сессии:

```
  > 2          # выбрать joint_1
  > z          # +0.1 рад
  > z          # ещё +0.1 рад
  > h          # вернуть в HOME
  > q          # выйти
```

---

## Makefile — все команды

### Docker

| Команда | Описание |
|---------|----------|
| `make docker-build` | Собрать Docker-образ |
| `make docker-all USB_DEVICE=/dev/ttyUSB0` | **Робот + TUI в одном контейнере** |
| `make docker-robot-bg USB_DEVICE=/dev/ttyUSB0` | Робот в фоне (отдельный контейнер) |
| `make docker-tui` | TUI (подключается к роботу по host сети) |
| `make docker-shell` | Интерактивный shell с ROS2 |
| `make docker-run` | Пустой контейнер (bash) |
| `make docker-exec` | Войти в запущенный контейнер |
| `make docker-topics` | Список активных ROS2 топиков |
| `make docker-stop` | Emergency stop (из-за контейнера) |
| `make docker-clean` | Остановить и удалить контейнер |
| `make stop-all` | Остановить все robot_control контейнеры |

### Команды на хосте (если ROS2 установлен нативно)

| Команда | Описание |
|---------|----------|
| `make pub-home` | Отправить позицию HOME |
| `make pub-ready` | Отправить позицию READY |
| `make pub-cmd-all POSITIONS='[0.5, 0, 0, 0, 0, 0]'` | Кастомная позиция |
| `make list-topics` | `ros2 topic list` |
| `make echo-joints` | Читать `/robot/joint_states` |

### Переменные

```bash
USB_DEVICE=/dev/ttyUSB0   # порт робота (default: /dev/ttyUSB0)
POSITIONS='[0.0, ...]'    # позиции суставов в радианах
BAG_PATH=my_session       # путь для rosbag
```

---

## ROS2 Topics API

### Публикуемые топики (`robot_node_v2`)

| Топик | Тип | Описание |
|-------|-----|----------|
| `/robot/joint_states` | `sensor_msgs/JointState` | Текущие позиции 6 суставов |
| `/robot/status` | `std_msgs/String` | JSON-статус (`connected`, `motors`) |

### Подписки (`robot_node_v2`)

| Топик | Тип | Описание |
|-------|-----|----------|
| `/robot/joint_cmd` | `trajectory_msgs/JointTrajectoryPoint` | Команда на позицию |
| `/robot/stop` | `std_msgs/Empty` | Emergency stop |

### Примеры команд вручную

```bash
# HOME
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint \
  "{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"

# READY
ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint \
  "{positions: [0.0, -0.5, 0.8, 0.0, 0.5, 0.0]}"

# Emergency stop
ros2 topic pub --once /robot/stop std_msgs/Empty "{}"

# Посмотреть текущие позиции
ros2 topic echo /robot/joint_states

# Частота обновления
ros2 topic hz /robot/joint_states
```

---

## Rosbag

```bash
# Записать сессию
make bag-record USB_DEVICE=/dev/ttyUSB0 BAG_PATH=my_session

# Воспроизвести без железа
make bag-play BAG_PATH=my_session

# Информация о записи
make bag-info BAG_PATH=my_session
```

---

## Troubleshooting

### `Could not connect to /dev/ttyUSB0`

```bash
# Проверить права
ls -la /dev/ttyUSB0
# Должно быть: crw-rw---- 1 root dialout ...

# Добавить в группу dialout
sudo usermod -aG dialout $USER && newgrp dialout

# Или временно
sudo chmod 666 /dev/ttyUSB0
```

### Контейнер не видит USB

Убедитесь что `--privileged -v /dev/bus/usb:/dev/bus/usb` передан (в `docker-all` это уже есть).
Или проверьте, что USB подключён до старта контейнера.

### TUI не видит топики (`DISCONNECTED`, `no data`)

Значит `robot_node_v2` ещё не запущен или не подключился к железу.

```bash
# Проверить топики из второго терминала
docker exec robot_control_container bash -c \
  "source /opt/ros/humble/setup.bash && ros2 topic list"
```

Если топика `/robot/joint_states` нет — нода не стартовала. Проверьте порт USB.

### Два отдельных контейнера не видят друг друга

Оба должны использовать `--network host` и одинаковый `ROS_DOMAIN_ID`.
Проверьте командами `make docker-robot-bg` и `make docker-tui` — они уже настроены правильно.

### `Permission denied` в Docker

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Пересобрать образ после изменений кода

```bash
make docker-build
```
