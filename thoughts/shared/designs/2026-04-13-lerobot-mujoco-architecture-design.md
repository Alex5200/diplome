---
date: 2026-04-13
topic: "LeRobot MuJoCo ML Architecture for 6-DOF Robot"
status: draft
---

## Problem Statement

Создать архитектуру MuJoCo симуляции для ML обучения (LeRobot) на базе 6-DOF манипулятора с использованием STL моделей звеньев из robot_config.json.

---

## Constraints

- **6 DOF** робот с 6 моторами (из robot_config.json)
- **STL модели** звеньев в mujoco_sim/models/
- **LeRobot data format**: action (7,) = 6 joint angles + gripper, observation.state (6,) = xyz + rpy
- **FPS**: 20
- **MuJoCo version**: 3.1.6
- **Python**: 3.10

---

## Approach

Адаптировать архитектуру из lerobot-mujoco-tutorial под наш 6-DOF робот:

1. **MJCF модель** — генерация XML из STL + robot_config.json
2. **Parser** — MuJoCoParserClass из tutorial + IK solver
3. **Environment** — Gymnasium-совместимая среда с LeRobot observations
4. **Dataset** — формат LeRobot HuggingFace
5. **Training** — ACT/pipeline обучение
6. **Inference** — деплой в симуляции

---

## Architecture

```
mujoco_sim/
├── models/                              # STL звенья (УЖЕ СУЩЕСТВУЕТ)
│   ├── основание.stl
│   ├── плечо1.stl
│   ├── плечо2.stl
│   ├── локоть.stl
│   ├── кисть1.stl
│   └── кисть2.stl
│
├── ml/
│   ├── parser/                          # MuJoCo парсер
│   │   ├── __init__.py
│   │   ├── mujoco_parser.py            # Из tutorial
│   │   ├── ik.py                       # Inverse kinematics
│   │   ├── transforms.py
│   │   └── utils.py
│   │
│   ├── models/                         # MJCF генерация
│   │   ├── __init__.py
│   │   ├── robot_generator.py         # Генерирует MJCF из robot_config.json
│   │   └── templates/
│   │       └── robot_base.xml.j2       # Jinja2 шаблон
│   │
│   ├── environments/                   # RL среды
│   │   ├── __init__.py
│   │   ├── base_robot_env.py          # Существует
│   │   └── lerobot_env.py              # LeRobot-специфичная
│   │
│   ├── dataset/                       # Датасеты
│   │   ├── __init__.py
│   │   ├── lerobot_dataset.py        # LeRobot формат
│   │   └── teleoperation.py          # Keyboard teleop
│   │
│   ├── agents/                        # Агенты
│   │   ├── __init__.py
│   │   ├── act_agent.py             # Action Chunking Transformer
│   │   └── policy.py              # Обученная политика
│   │
│   └── training/                     # Обучение
│       ├── __init__.py
│       ├── train.py
│       └── configs/
│           └── act_6dof.yaml
│
├── config/
│   └── robot_config.json            # Существует
│
└── demo_data/                       # Собранные данные (создаётся при collect)
    ├── data/
    │   └── chunk-000/
    │       └── episode_*.parquet
    └── meta/
        ├── episodes.jsonl
        ├── info.json
        └── stats.json
```

---

## Components

### 1. Robot Generator (robot_generator.py)

**Назначение**: Генерирует MuJoCo MJCF XML из robot_config.json + STL

**Входные данные**:
- robot_config.json — конфиг моторов и mapping
- STL файлы из mujoco_sim/models/

**Логика**:
```python
def generate_robot_mjcf(config: dict) -> str:
    # 1. Загрузить STL → определить bounding box → масштаб
    # 2. Построить kinematic chain из motor_mapping
    # 3. Применить inverted флаги к осям
    # 4. Заполнить шаблон Jinja2
    # 5. Вернуть XML string
```

**Mapping суставов** (из robot_config.json):

| MuJoCo Joint | STL Link | Motor ID | Inverted | Axis |
|-------------|---------|----------|----------|------|
| joint_0 | основание.stl | 1 | true | Z |
| joint_1 | плечо1.stl | 2 | false | Y |
| joint_2 | плечо2.stl | 4 | true | Y |
| joint_3 | локоть.stl | 5 | false | Y |
| joint_4 | кисть1.stl | 3 | false | X |
| joint_5 | кисть2.stl | 6 | false | X |

### 2. MuJoCo Parser (mujoco_parser.py)

**Наследование**: Из lerobot-mujoco-tutorial/master/mujoco_env/mujoco_parser.py

**Изменения**:
- Добавить поддержку xml_string (не только файл)
- Интегрировать с robot_generator
- Настроить камеры для нашего робота

### 3. Inverse Kinematics (ik.py)

**Наследование**: Из tutorial

**Метод**: Cyclic Coordinate Descent (CCD) или Jacobian Pseudo-inverse

**Интерфейс**:
```python
def solve_ik(env, joint_names, body_name_trgt, q_init, p_trgt, R_trgt):
    """Вернуть q, ik_err_stack, ik_info"""
```

### 4. LeRobot Environment (lerobot_env.py)

**Наследование**: BaseRobotEnv (существует)

**Action Space**: 
- **eef_pose** — (6,) = delta position (xyz) + delta orientation (rpy)
- **joint_angle** — (7,) = 6 joint angles + gripper (0/1)
- **delta_joint_angle** — (7,) = delta joints + gripper

**Observation Space**:
- **observation.state** — (6,) = ee position (xyz) + orientation (rpy)
- **observation.image** — (256, 256, 3) = RGB camera
- **observation.wrist_image** — (256, 256, 3) = gripper camera (опционально)

**Камеры**:
- top_down — вид сверху
- egocentric — вид от робота
- agentview — общий вид
- gripper — камера на кисти

### 5. Teleoperation (teleoperation.py)

**Управление** (из tutorial):

| Key | Action |
|-----|--------|
| W/S | ±X axis |
| A/D | ±Y axis |
| R/F | ±Z axis |
| Q/E | Tilt rotation |
| ↑/↓ | Pitch |
| ←/→ | Yaw |
| SPACE | Gripper toggle |
| Z | Reset episode |

### 6. Dataset Format (LeRobot)

**Структура**:
```
fps = 20
features = {
    "observation.image": {"dtype": "image", "shape": (256, 256, 3)},
    "observation.state": {"dtype": "float32", "shape": (6,)},
    "action": {"dtype": "float32", "shape": (7,)},  # 6 joints + gripper
}
```

**Хранение**: Parquet + HuggingFace datasets format

### 7. ACT Training (act_agent.py)

**Наследование**: Из tutorial

**Параметры**:
- chunk_size = 10
- hidden_dim = 512
- nheads = 8
- nlayers = 6

---

## Data Flow

```
1. Сбор данных:
   Keyboard → teleop_env → LeRobot Dataset
   
2. Обучение:
   Dataset → ACT Agent → checkpoint
   
3. Инференс:
   Trained Policy → MuJoCo Env → Actions
```

---

## Error Handling

| Error | Strategy |
|-------|-----------|
| IK fails | Fallback → previous valid q |
| STL not found | Raise FileNotFoundError с путём |
| Joint limits | Clamp + warning |
| Camera fails | Return black image |

---

## Testing Strategy

1. **Unit tests**: IK solver, angle conversion
2. **Integration**: Teleop → record → replay
3. **Validation**: EE position matches ground truth

---

## Open Questions

1. **Диапазоны суставов** — robot_config.json использует ticks (0-4095), нужно добавить реальные углы в градусах
2. **Gripper** — кисть2 это gripper? Добавить 7-й "сустав" для gripper state?
3. **MuJoCo версия** — проверить что 3.1.6 установлена

---

## References

- lerobot-mujoco-tutorial: https://github.com/jeongeun980906/lerobot-mujoco-tutorial
- robotis_mujoco_menagerie: https://github.com/ROBOTIS-GIT/robotis_mujoco_menagerie