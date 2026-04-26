# ST3215 Robot Control Application

Модульное приложение для управления роботом-манипулятором на основе сервомоторов ST3215.

## 📋 Содержание

- [Обзор](#обзор)
- [Архитектура](#архитектура)
- [Установка](#установка)
- [Запуск](#запуск)
- [Использование](#использование)
- [API Reference](#api-reference)
- [Структура проекта](#структура-проекта)

---

## 📖 Обзор

Приложение предоставляет полный интерфейс для управления 6-осевым роботом-манипулятором:

- **Подключение к моторам** через последовательный порт (USB)
- **Сканирование и определение** подключенных сервомоторов
- **Настройка соответствия** физических ID моторов логическим суставам
- **Ручное управление** каждым суставом с регулировкой скорости
- **3D визуализация** положения робота в реальном времени
- **Асинхронный мониторинг** температуры, нагрузки, позиции
- **Блочное программирование** последовательностей движений

---

## 🏗️ Архитектура

Приложение построено по принципу **разделения ответственности** (Separation of Concerns):

```
┌─────────────────────────────────────────────────────────────┐
│                     RobotControlGUI                          │
│                      (Main Window)                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Views     │  │ Controllers │  │      Utils          │  │
│  │  (Tkinter)  │◄─┤  (Motors)   │◄─┤  (Logger, Config)   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │                │                                    │
│         ▼                ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    Models                                │ │
│  │            (MotorData, ProgramBlock)                     │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   ST3215 Motor  │
                    │   (Hardware)    │
                    └─────────────────┘
```

### Компоненты

| Компонент | Описание |
|-----------|----------|
| **config** | Константы, цвета, настройки по умолчанию |
| **models** | Модели данных (MotorData, ProgramBlock) |
| **controllers** | MotorController, MotorMonitor |
| **views** | GUI панели (Tkinter + Matplotlib) |
| **utils** | Logger, ConfigManager, ProgramExecutor |

---

## 📦 Установка

### Требования

- Python 3.8+
- Windows 10/11 (для работы с COM портами)

### Зависимости

```bash
pip install pyserial matplotlib tkinter
```

### Структура зависимостей

```
st3215          # Драйвер моторов ST3215 (локальный модуль)
pyserial        # Работа с последовательным портом
matplotlib      # 3D визуализация
tkinter         # GUI интерфейс
```

---

## 🚀 Запуск

### Из директории проекта

```bash
python app/main.py
```

### Как модуль

```bash
python -m app.main
```

### Из main.py (корневой)

```bash
python main.py
```

---

## 🎮 Использование

### 1. Подключение к роботу

1. Выберите COM порт из выпадающего списка
2. Нажмите **🔌 Подключиться**
3. Нажмите **🔍 Сканировать** для поиска моторов

### 2. Настройка моторов

Перейдите на вкладку **🔗 Настройка моторов**:

- Назначьте ID моторов каждому суставу
- Задайте отображаемые имена
- Используйте **🔍 Автоопределение** для автоматической настройки

### 3. Ручное управление

На вкладке **🎮 Мануальное**:

- Выберите сустав кнопками J1-J6
- Используйте **◀ Назад** / **▶ Вперед** для движения
- Регулируйте скорость ползунком
- Быстрые команды: **🏠 В 0**, **🔄 В центр**, **🔒 ВКЛ**, **🔓 ВЫКЛ**

### 4. 3D визуализация

На вкладке **🔬 3D Кинематика**:

- Введите углы суставов в градусах (-180° до +180°)
- Нажмите **OK** для применения к суставу
- **📤 Применить все** - применить все углы сразу
- **🔄 Обновить 3D** - обновить визуализацию

### 5. Блочное программирование

На вкладке **📦 Программы**:

1. Добавьте блоки из палитры слева
2. Настройте параметры каждого блока
3. Нажмите **▶️ Запустить** для выполнения

#### Типы блоков

| Блок | Описание | Параметры |
|------|----------|-----------|
| 🔄 Движение | Перемещение сустава в позицию | joint, position |
| 🏠 Home | Возврат в домашнюю позицию | joint (или 'all') |
| ⏱ Ждать | Пауза выполнения | seconds |
| 💪 ВКЛ | Включение момента | joint |
| 💪 ВЫКЛ | Выключение момента | joint |

---

## 📚 API Reference

### Controllers

#### MotorController

```python
from app.controllers import MotorController

controller = MotorController(device='COM3')

# Подключение
controller.connect()
controller.disconnect()

# Управление
controller.move_to_position(motor_id=1, position=2048, speed=2400)
controller.move_joint(joint_index=0, position=2048)
controller.toggle_torque(motor_id=1, enable=True)

# Чтение данных
data = controller.read_motor_data(motor_id=1)
# Возвращает: {position, temperature, voltage, current, load, mode, moving}

# Конфигурация
controller.update_motor_mapping(joint_index=0, motor_id=1, name='База')
controller.save_config('robot_config.json')
controller.load_config('robot_config.json')
```

#### MotorMonitor

```python
from app.controllers import MotorMonitor

monitor = MotorMonitor(controller, update_callback=my_callback)
monitor.start(motor_ids=[1, 2, 3, 4, 5, 6])

# Получение данных
data = monitor.get_data(motor_id=1)
all_data = monitor.get_all_data()

# Остановка
monitor.stop()
```

### Models

#### MotorData

```python
from app.models import MotorData

data = MotorData(
    motor_id=1,
    position=2048,
    temperature=45.5,
    voltage=12.0,
    current=0.5,
    load=30.0,
    torque_enabled=True
)

# Проверка перегрева
if data.is_overheating():
    print("Мотор перегревается!")

# Конвертация в словарь
data_dict = data.to_dict()
```

#### ProgramBlock

```python
from app.models import ProgramBlock

block = ProgramBlock(
    id=1,
    block_type='motion',
    params={'type': 'move_to', 'joint': 0, 'position': 2048},
    order=0
)
```

### Utils

#### AppLogger

```python
from app.utils import AppLogger

logger = AppLogger('my_app', log_file='app.log')

logger.info('Информационное сообщение')
logger.success('Успешное действие')
logger.warning('Предупреждение')
logger.error('Ошибка')
logger.debug('Отладочная информация')

logger.close()
```

#### ConfigManager

```python
from app.utils import ConfigManager

config = ConfigManager()

# Загрузка/сохранение
data = config.load_config('robot_config.json')
config.save_config('robot_config.json', data)

# Программы
program = config.load_program('robot_program.json')
config.save_program('robot_program.json', program)

# Настройки моторов
motor_config = config.get_motor_config(motor_id=1)
mapping = config.get_motor_mapping()
```

#### ProgramExecutor

```python
from app.utils import ProgramExecutor

executor = ProgramExecutor(controller)

# Callback функции
executor.on_block_start = lambda params, id: print(f"Блок {id} начался")
executor.on_block_complete = lambda params, id: print(f"Блок {id} завершен")
executor.on_program_complete = lambda result: print(f"Программа завершена: {result.success}")

# Выполнение
result = executor.execute(program_blocks, async_mode=True)

# Управление выполнением
executor.pause()
executor.resume()
executor.stop()
```

---

## 📁 Структура проекта

```
diplome/
├── main.py                     # Точка входа (монолитная версия)
├── robot_config.json           # Конфигурационный файл
├── st3215/                     # Модуль драйвера моторов
│   └── ...
└── app/                        # Модульное приложение
    ├── __init__.py             # Экспорт основных символов
    ├── main.py                 # Точка входа app
    ├── README.md               # Эта документация
    │
    ├── config/
    │   ├── __init__.py
    │   └── constants.py        # Константы приложения
    │
    ├── models/
    │   ├── __init__.py
    │   └── motor_data.py       # MotorData, ProgramBlock
    │
    ├── controllers/
    │   ├── __init__.py
    │   ├── motor_controller.py # MotorController
    │   └── motor_monitor.py    # MotorMonitor
    │
    ├── views/
    │   ├── __init__.py
    │   ├── main_window.py          # RobotControlGUI
    │   ├── manual_control_panel.py # ManualControlPanel
    │   ├── motor_mapping_panel.py  # MotorMappingPanel
    │   ├── kinematics_3d_panel.py  # Kinematics3DPanel
    │   ├── bottom_monitor_panel.py # BottomMonitorPanel
    │   └── block_programming.py    # BlockPalette, ProgramCanvas
    │
    └── utils/
        ├── __init__.py
        ├── logger.py           # AppLogger
        ├── config_manager.py   # ConfigManager
        └── program_executor.py # ProgramExecutor
```

---

## ⚙️ Константы и настройки

### Позиции

| Константа | Значение | Описание |
|-----------|----------|----------|
| MIN_POSITION | 0 | Минимальная позиция мотора |
| MAX_POSITION | 4095 | Максимальная позиция мотора |
| DEFAULT_SPEED | 2400 | Скорость по умолчанию (шаг/сек) |
| DEFAULT_ACC | 50 | Ускорение по умолчанию |

### Температурные пороги

| Константа | Значение | Описание |
|-----------|----------|----------|
| TEMP_WARNING | 70°C | Порог предупреждения |
| TEMP_CRITICAL | 80°C | Порог перегрева |

### Суставы по умолчанию

```python
JOINT_NAMES = [
    '🏗️ База',
    '💪 Плечо 1',
    '💪 Плечо 2',
    '🦾 Локоть',
    '🖐️ Кисть 1',
    '🖐️ Кисть 2'
]
```

---

## 🔧 Расширение

### Добавление нового типа блока

1. Откройте `app/views/block_programming.py`
2. Добавьте тип в `BlockPalette._create_categories()`
3. Откройте `app/utils/program_executor.py`
4. Добавьте метод `_execute_<type>()`
5. Добавьте обработку в `_execute_block()`

### Добавление новой панели

1. Создайте файл в `app/views/` с классом, наследующим `ttk.Frame`
2. Импортируйте в `app/views/__init__.py`
3. Добавьте в главное окно в `RobotControlGUI._create_widgets()`

---

## 📝 Лицензия

Проект создан в образовательных целях для дипломной работы.

---

## 👥 Авторы

- **Alexandr Lyachov** - Основная разработка
- **ST3215 Driver** - Драйвер для сервомоторов Lewansoul/Hiwonder
