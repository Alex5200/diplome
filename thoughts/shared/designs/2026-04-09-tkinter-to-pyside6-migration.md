---
date: 2026-04-09
topic: "Миграция интерфейса Tkinter → PySide6"
status: validated
---

## Problem Statement

Текущее приложение использует устаревший Tkinter для GUI. Необходимо переписать на PySide6 для:
- Современного внешнего вида (Qt styling)
- Лучшей производительности и стабильности
- Доступа к расширенным виджетам (таблицы, деревья, 3D)
- Кросс-платформенной поддержки

## Constraints

1. **Обратная совместимость**: Сохранить все функциональные панели и возможности
2. **Тема**: Использовать светлую пастельную тему (текущие цвета)
3. **Зависимости**: PySide6 + дополнительные библиотеки для 3D
4. **Архитектура**: MVVM паттерн с signals/slots

## Approach

**Выбранный подход**: Постепенная миграция с созданием новой архитектуры на PySide6, сохраняя логику контроллеров.

**Почему не PyQt6**: PySide6 — официальный Qt for Python от Qt Company (LGPL), лучшая поддержка и документация.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  MainWindow (QMainWindow)                                   │
│  ┌─────────────────────────────────────────────────────────┤
│  │ MenuBar | ToolBar                                        │
│  ├─────────────────────────────────────────────────────────┤
│  │ StatusBar (mode, speed, connection, clock)              │
│  ├────────────┬────────────────────────────────────────────┤
│  │ Sidebar    │  TabWidget (основные вкладки)              │
│  │ (dock)     │  ┌─────────────────────────────────────────┤
│  │            │  │ Dashboard | Jog | 3D | Registers |      │
│  │ - Connect  │  │ Teach | Program | Setup | XYZ | Alarms  │
│  │ - Scan     │  │ AI Vision | AI Control                  │
│  │ - Home     │  └─────────────────────────────────────────┤
│  │ - E-Stop   │                                            │
│  │ - Speed    │                                            │
│  ├────────────┴────────────────────────────────────────────┤
│  │ Bottom Panel (мониторинг моторов + лог)                 │
│  └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

### Component Mapping

| Tkinter | PySide6 |
|---------|---------|
| tk.Tk() | QMainWindow |
| tk.Frame | QWidget / QFrame |
| ttk.Frame | QWidget |
| tk.Label | QLabel |
| tk.Button | QPushButton |
| ttk.Notebook | QTabWidget |
| tk.Canvas | QGraphicsView / QOpenGLWidget |
| tk.Scale | QSlider |
| tk.Entry | QLineEdit |
| ttk.Spinbox | QSpinBox / QDoubleSpinBox |
| ttk.Treeview | QTreeWidget / QTableWidget |
| tk.Scrolledtext | QTextEdit |
| tk.Menu | QMenuBar / QMenu |
| tk.LabelFrame | QGroupBox |

## Components

### 1. MainWindow (main_window.py)

```python
class RobotMainWindow(QMainWindow):
    # Сигналы для связи между компонентами
    connection_changed = Signal(bool)
    speed_changed = Signal(int)
    jog_mode_changed = Signal(str)
    
    # Основные виджеты
    self.status_bar: QStatusBar
    self.tab_widget: QTabWidget
    self.sidebar: QDockWidget
    self.bottom_panel: QWidget
```

### 2. StatusBar Component

```python
class FANUCStatusBar(QWidget):
    mode_changed = Signal(str)
    speed_changed = Signal(int)
    
    # Метки
    self.mode_label: QLabel      # JOINT/CARTESIAN
    self.speed_label: QLabel      # 50%
    self.coord_label: QLabel      # WORLD
    self.prog_status: QLabel      # IDLE/RUN/PAUSE
    self.clock_label: QLabel      # 00:00:00
    self.connection_indicator: QLabel  # LED indicator
```

### 3. Panels (каждая панель — отдельный класс)

- **DashboardPanel** — подключение, статус, быстрые действия
- **JogPanel** — ручное управление суставами
- **Kinematics3DPanel** — 3D визуализация (PyQtGraph/VTK)
- **PositionRegisterPanel** — таблица регистров PR
- **TeachPendantPanel** — обучение траекториям
- **BlockProgrammingPanel** — блочное программирование
- **MotorMappingPanel** — настройка моторов
- **CoordinatesPanel** — XYZ координаты
- **AlarmHistoryPanel** — история аварий
- **VisionTrackerPanel** — AI Vision
- **AIControlPanel** — AI Control

### 4. Bottom Monitor Panel

```python
class BottomMonitorPanel(QWidget):
    # Мониторинг всех 6 моторов
    self.motor_widgets: list[MotorStatusWidget]
    # Лог
    self.log_text: QTextEdit
```

## Data Flow

```
User Input → PySide6 Widget → Signal → Controller (MotorController)
                                      ↓
                              MotorController → ST3215 Servo
                                      ↓
                              Signal → Update UI (Slot)
```

## Key Changes from Tkinter

### 1. Signals/Slots вместо Callbacks
```python
# Tkinter
button.config(command=callback)

# PySide6
button.clicked.connect(self.handle_click)
```

### 2. Layout Managers
```python
# Tkinter
frame.pack(fill="both", expand=True)

# PySide6 (QVBoxLayout, QHBoxLayout, QGridLayout)
layout = QVBoxLayout()
layout.addWidget(widget)
```

### 3. Таблицы
```python
# Tkinter
tree = ttk.Treeview(columns=columns)

# PySide6
table = QTableWidget()
table.setColumnCount(len(columns))
table.setHorizontalHeaderLabels(columns)
```

### 4. 3D Визуализация
- Текущее: matplotlib + mpl_toolkits.mplot3d
- Новое: **PyQtGraph** (быстрее) или **PyVista** (полная 3D)

## Error Handling

- Использовать QMessageBox для диалогов
- Логировать в QTextEdit (bottom panel)
- Исключения обрабатывать в контроллерах

## Testing Strategy

1. unit tests для контроллеров (существующие)
2. GUI тесты с pytest-qt
3. Ручное тестирование всех панелей

## Dependencies

```txt
PySide6>=6.5.0
PyQtGraph>=0.13.0  # Для 3D визуализации
numpy>=1.24.0
```

## Open Questions

1. **3D визуализация**: matplotlib работает с PySide6, но медленно. Рассмотреть PyQtGraph или VisPy.
2. **Matplotlib embedded**: Использовать FigureCanvasQtag или QOpenGLWidget?
3. **Стилизация**: QSS (Qt Style Sheets) vs ресурсные файлы?