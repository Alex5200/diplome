# robot_controls

ROS2 пакет для управления 6-осевым роботом ST3215 через colcon. Принимает XYZ-цели, решает обратную кинематику (IK), отправляет позиции в моторы, записывает rosbag.

## Архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│  RViz2 / CLI / rqt                                              │
│  ──────────────────────────────                                  │
│  Пользователь отправляет XYZ                                    │
└────────────────┬─────────────────────────────────────────────────┘
                 │ /robot_controls/moveit/goal [PoseStamped]
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│  moveit_bridge      (опционально)                                │
│  ──────────────                                                  │
│  Подключается к move_group, проверяет достижимость               │
│  Форвардит цель в /robot_controls/target_pose                   │
└────────────────┬─────────────────────────────────────────────────┘
                 │ /robot_controls/target_pose [PoseStamped]
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│  robot_controls_node    ═══  ГЛАВНАЯ НОДА                       │
│  ─────────────────────                                          │
│  1. Принимает XYZ (м) через /robot_controls/target_pose         │
│  2. Решает IK (мм → JointState) через kinematics_model          │
│  3. Пишет позиции в ST3215 моторы через hardware_interface     │
│  4. Публикует /joint_states (для RViz)                          │
│  5. Принимает параметры скорости/ускорения через топик          │
└────────────────┬─────────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│  bag_recorder                                                    │
│  ────────────                                                    │
│  Автоматически записывает все топики в rosbag                   │
└──────────────────────────────────────────────────────────────────┘
```

## Топики

| Топик | Тип | Описание |
|-------|-----|----------|
| `/robot_controls/target_pose` | `PoseStamped` | **Вход**: XYZ в метрах (frame_id: base_link) |
| `/robot_controls/moveit/goal` | `PoseStamped` | **Вход**: цель для MoveIt (форвардится в target_pose) |
| `/robot_controls/parameters/cmd` | `String` | **Вход**: JSON параметры (speed, acceleration, torque_limit, mode) |
| `/robot_controls/parameters/state` | `String` | **Выход**: текущие параметры робота |
| `/robot_controls/status` | `String` | **Выход**: статус подключения |
| `/robot_controls/joint_states` | `JointState` | **Выход**: позиции 6 суставов (рад) |
| `/joint_states` | `JointState` | **Выход**: для RViz / robot_state_publisher |
| `/robot_controls/moveit/status` | `String` | **Выход**: статус MoveIt bridge |
| `/robot_controls/bag/status` | `String` | **Выход**: статус rosbag-записи |
| `/robot_controls/stop` | `Empty` | **Вход**: экстренная остановка |

## Параметры (JSON)

В `/robot_controls/parameters/cmd`:
```json
{
  "speed": 0.8,
  "acceleration": 0.5,
  "torque_limit": 100.0,
  "mode": "position",
  "gripper_open": 0.0
}
```

## Быстрый старт

### 1. Подключение USB в WSL2

На **Windows** (от Администратора):
```powershell
usbipd list                       # найти BUSID (например 2-11)
usbipd bind --busid 2-11
usbipd attach --wsl --busid 2-11
```

В **WSL2**:
```bash
ls /dev/ttyACM*                   # или /dev/ttyUSB*
sudo chmod 666 /dev/ttyACM0       # дать права
```

### 2. Сборка

```bash
git pull
colcon build --packages-select robot_controls robot_control
source install/setup.bash
```

### 3. Запуск с реальной рукой

```bash
# Терминал 1 — hardware + IK
ros2 run robot_controls robot_controls_node --ros-args \
  -p port:=/dev/ttyACM0 -p baudrate:=1000000 -p offline_mode:=false

# Терминал 2 — тест
ros2 topic pub --once /robot_controls/target_pose geometry_msgs/PoseStamped \
  '{header: {frame_id: "base_link"}, pose: {position: {x: 0.15, y: 0.0, z: 0.1}}}'
```

### 4. Запуск с MoveIt2 + RViz

```bash
ros2 launch robot_controls moveit2.launch.py use_robot_hardware:=true port:=/dev/ttyACM0
```

### 5. Офлайн (без железа)

```bash
ros2 launch robot_controls moveit2.launch.py use_robot_hardware:=false
```

## Команды

### Отправить цель
```bash
ros2 topic pub /robot_controls/target_pose geometry_msgs/PoseStamped \
  '{header: {frame_id: "base_link"}, pose: {position: {x: 0.2, y: 0.0, z: 0.3}}}'
```

### Отправить через MoveIt
```bash
ros2 topic pub /robot_controls/moveit/goal geometry_msgs/PoseStamped \
  '{header: {frame_id: "base_link"}, pose: {position: {x: 0.2, y: 0.0, z: 0.3}}}'
```

### Установить параметры
```bash
ros2 topic pub /robot_controls/parameters/cmd std_msgs/String \
  '{data: "{\"speed\": 0.5, \"acceleration\": 0.3}"}'
```

### Экстренная остановка
```bash
ros2 topic pub --once /robot_controls/stop std_msgs/Empty "{}"
```

### Просмотр данных
```bash
ros2 topic echo /robot_controls/joint_states
ros2 topic echo /robot_controls/parameters/state
ros2 topic echo /joint_states
rqt_graph
```

## Работа с rosbag

### Автоматическая запись (через bag_recorder)
Запускается вместе с `moveit2.launch.py`. Баг сохраняется в `robot_bag_<timestamp>/`.

### Ручная
```bash
ros2 bag record -o my_session \
  /joint_states \
  /robot_controls/target_pose \
  /robot_controls/parameters/state

# Воспроизвести
ros2 bag play my_session
```

## Управление в RViz

1. `ros2 launch robot_controls moveit2.launch.py use_rviz:=true`
2. В RViz: **Interact** (верхняя панель) → перетащи InteractiveMarker
3. MotionPlanning → **Plan** → **Plan & Execute**

### Если MotionPlanning панель не видна

```bash
sudo apt install ros-humble-moveit-ros-visualization
```

## Файлы конфигурации

| Файл | Описание |
|------|----------|
| `config/st3215.srdf` | Semantic Robot Description — группа `arm` (chain: base→tool) |
| `config/kinematics.yaml` | IK solver: KDL |
| `config/ompl_planning.yaml` | Планировщики: RRTConnect, RRTstar, BKPIECE |
| `config/moveit.rviz` | RViz presets: TF, RobotModel, MotionPlanning |

## Возможные проблемы

### `No module named 'st3215'`
```bash
sudo /usr/bin/python3 -m pip install st3215
```

### `colcon build` не видит пакет
`robot_controls` должен лежать в корне workspace (`~/diplome/robot_controls/`), не внутри другого пакета.

### USB не виден в WSL
```powershell
# Windows (Администратор)
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```

### Рука не двигается при IK Success
Проверь что:
- `robot_control` собран (`colcon build --packages-select robot_control`)
- `hardware_interface.py` импортируется без ошибок
- Порт имеет права `sudo chmod 666 /dev/ttyACM0`
