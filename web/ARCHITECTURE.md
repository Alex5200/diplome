# Web Interface Architecture — ST3215 Robot Control

## Общая концепция

Полноценный веб-интерфейс для управления 6-DOF роботом-манипулятором ST3215 с 3D-визуализацией (Three.js), блочным программированием (Blockly) и экстренной остановкой.

---

## Layout (макет страницы)

```
┌──────────────────────────────────────────────────────────────────────┐
│  Header: статус подключения, E-STOP кнопка, навигация               │
├──────────────────────────────────────┬───────────────────────────────┤
│                                      │                               │
│          3D Viewer (Three.js)        │     Block Programming         │
│          ~65% ширины                 │     (Google Blockly)          │
│                                      │     ~35% ширины               │
│   - URDF / кастомная модель робота   │                               │
│   - Обновление в реальном времени    │   - Блоки: Move, Wait, Loop  │
│   - Orbit controls                   │   - Генерация кода            │
│   - Отображение осей, сетки          │   - Run / Stop / Export       │
│   - IK: клик → целевая точка         │                               │
│                                      │                               │
├──────────────────────────────────────┴───────────────────────────────┤
│  Bottom Bar: телеметрия моторов (mini), лог событий                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Технологический стек

| Слой | Технология | Почему |
|------|-----------|--------|
| UI Framework | **React 18** (Vite) | Компонентный подход, быстрая сборка |
| Стили | **Tailwind CSS** | Utility-first, быстрая стилизация |
| 3D Engine | **Three.js** + `@react-three/fiber` + `@react-three/drei` | Декларативный 3D в React |
| Блочное программирование | **Google Blockly** (`blockly`) | Стандарт индустрии, кастомные блоки |
| State Management | **Zustand** | Легковесный, без boilerplate |
| WebSocket | Нативный `WebSocket` API | Уже есть WS endpoint на бэкенде |
| Backend | **FastAPI** (уже есть) | REST + WS, Python |
| Сборка | **Vite** | HMR, быстрая dev-сборка |

---

## Структура проекта

```
web/
├── frontend/                    # React приложение (Vite)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx             # Entry point
│   │   ├── App.tsx              # Root layout
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx          # Статус, E-STOP, навигация
│   │   │   │   ├── BottomBar.tsx       # Телеметрия + лог
│   │   │   │   └── SplitPane.tsx       # Resizable split (3D | Blockly)
│   │   │   │
│   │   │   ├── viewer3d/
│   │   │   │   ├── RobotScene.tsx      # R3F Canvas + освещение + grid
│   │   │   │   ├── RobotModel.tsx      # 6-DOF манипулятор (меши + joints)
│   │   │   │   ├── JointLink.tsx       # Отдельное звено робота
│   │   │   │   ├── TargetMarker.tsx    # IK целевая точка (draggable)
│   │   │   │   ├── TrajectoryLine.tsx  # Линия траектории
│   │   │   │   └── AxisHelper.tsx      # XYZ оси
│   │   │   │
│   │   │   ├── blockly/
│   │   │   │   ├── BlocklyEditor.tsx   # Обёртка Blockly workspace
│   │   │   │   ├── blocks/            # Кастомные блоки
│   │   │   │   │   ├── move.ts        # Блок перемещения сустава
│   │   │   │   │   ├── wait.ts        # Блок задержки
│   │   │   │   │   ├── loop.ts        # Блок цикла
│   │   │   │   │   ├── ik_move.ts     # Блок IK перемещения (x,y,z)
│   │   │   │   │   ├── gripper.ts     # Блок захвата
│   │   │   │   │   └── index.ts       # Регистрация всех блоков
│   │   │   │   ├── generators/        # Генераторы кода из блоков
│   │   │   │   │   └── python.ts      # → Python/JSON команды
│   │   │   │   ├── toolbox.ts         # Конфигурация тулбокса
│   │   │   │   └── BlocklyControls.tsx # Run / Stop / Export кнопки
│   │   │   │
│   │   │   ├── controls/
│   │   │   │   ├── EmergencyStop.tsx   # Большая красная кнопка E-STOP
│   │   │   │   ├── ConnectionPanel.tsx # COM порт, подключение
│   │   │   │   └── JointSliders.tsx    # 6 слайдеров для суставов
│   │   │   │
│   │   │   └── telemetry/
│   │   │       ├── MotorTable.tsx      # Таблица телеметрии
│   │   │       └── EventLog.tsx        # Лог событий
│   │   │
│   │   ├── stores/
│   │   │   ├── robotStore.ts           # Состояние робота (углы, статус)
│   │   │   ├── connectionStore.ts      # Статус подключения
│   │   │   └── programStore.ts         # Блочная программа, выполнение
│   │   │
│   │   ├── services/
│   │   │   ├── api.ts                  # REST API клиент
│   │   │   ├── websocket.ts            # WebSocket менеджер
│   │   │   └── programRunner.ts        # Исполнитель блочной программы
│   │   │
│   │   ├── utils/
│   │   │   ├── kinematics.ts           # FK/IK портированный из Python
│   │   │   └── constants.ts            # DH параметры, лимиты углов
│   │   │
│   │   └── types/
│   │       └── robot.ts                # TypeScript типы
│   │
│   └── public/
│       └── models/                     # 3D модели (опционально, STL/GLTF)
│
├── api/                         # FastAPI backend (уже есть)
│   ├── routes.py
│   └── websocket.py
├── main.py                      # FastAPI entry point
└── static/                      # Legacy HTML (будет заменён)
    └── index.html
```

---

## Ключевые компоненты

### 1. RobotModel.tsx — 3D модель робота

Портирование логики из `app/views/kinematics_3d_panel.py` и `app/models/kinematics.py`:

```
DH параметры (из kinematics.py):
  L0 = 19mm  (база)
  L1 = 104mm (плечо 1)
  L2 = 95mm  (плечо 2)
  L3 = 34mm  (локоть)
  L4 = 35mm  (запястье)
  L5 = 0mm   (инструмент)
```

Каждое звено — `<mesh>` с цилиндрической/коробчатой геометрией. Суставы вращаются через вложенные `<group>` с `rotation`. Forward kinematics считается на клиенте для мгновенного отклика, а реальные позиции приходят по WebSocket.

### 2. BlocklyEditor.tsx — блочное программирование

Кастомные блоки:
- **move_joint** — перемещение конкретного сустава (J1-J6, позиция, скорость)
- **move_ik** — перемещение в точку XYZ через IK
- **wait** — пауза N секунд
- **loop** — повторение N раз
- **gripper** — открыть/закрыть захват
- **home** — вернуть в home-позицию

Генерация: блоки → JSON массив команд → отправка на backend через REST API последовательно.

### 3. EmergencyStop.tsx — экстренная остановка

```
Принцип работы:
1. Большая красная кнопка ВСЕГДА видна в Header
2. При нажатии:
   a) Немедленный POST /api/stop
   b) Остановка выполнения блочной программы (programStore.abort())
   c) WebSocket: отправка {"type": "emergency_stop"}
   d) Визуальная индикация (пульсация, блокировка UI)
3. Клавиша Escape — альтернативный триггер
4. После E-STOP требуется явный "Reset" для продолжения работы
```

---

## Потоки данных

### Телеметрия (реальное время)
```
Robot → Serial → FastAPI (MotorController) → WebSocket → React (robotStore) → UI
                                                                    ↓
                                                            3D Model обновляется
                                                            Таблица телеметрии
```

### Управление
```
UI (слайдер/блок) → robotStore → REST API (POST /api/move) → MotorController → Serial → Robot
```

### Блочная программа
```
Blockly Workspace → JSON commands → programRunner.ts → REST API (последовательно) → Robot
                                          ↓
                                   robotStore (текущий шаг)
                                          ↓
                                   3D Viewer (подсветка)
```

---

## Подключение к реальному роботу — без REST API?

### Вариант 1: WebSocket-only (рекомендуемый)
Уже есть `/ws` endpoint. Можно расширить протокол:

```json
// Client → Server
{"type": "move", "joint": 1, "position": 2048, "speed": 2400}
{"type": "stop"}
{"type": "ik", "x": 150, "y": 0, "z": 100}

// Server → Client
{"type": "telemetry", "motors": {...}}
{"type": "move_ack", "joint": 1, "ok": true}
{"type": "error", "message": "..."}
```

Преимущество: двунаправленная связь, низкая задержка (~5-15ms по LAN).

### Вариант 2: WebSerial API (браузер → робот напрямую)
**Да, это реально!** Без сервера вообще.

```
Браузер (Chrome/Edge) → WebSerial API → USB-Serial → Робот
```

- `navigator.serial.requestPort()` — выбор COM порта из браузера
- Прямая отправка пакетов SCServo протокола
- **Ограничения**: только Chrome/Edge, требует HTTPS или localhost, пользователь вручную выбирает порт
- **Плюс**: zero-latency, не нужен Python backend
- **Минус**: нужно портировать SCServo протокол в JavaScript, нет backend мониторинга

### Вариант 3: WebUSB API
Аналогично WebSerial, но на уровне USB-устройства. Менее удобно для Serial-устройств.

### Вариант 4: Electron / Tauri
Десктоп-приложение с полным доступом к Serial без ограничений браузера. Overkill для текущей задачи.

### Рекомендация
**WebSocket (Вариант 1)** — оптимальный баланс. FastAPI backend уже работает с роботом, WS даёт real-time. Для дипломного проекта этого более чем достаточно. WebSerial интересен как дополнительная фича (direct mode), но это усложнение.

---

## Новые API endpoints (нужно добавить в backend)

```python
# POST /api/program/run — запуск блочной программы
# POST /api/program/stop — остановка программы
# POST /api/home — возврат в home-позицию
# GET  /api/kinematics/fk — прямая кинематика (углы → xyz)
# WS   /ws — расширить протокол (move, stop, ik через WS)
```

---

## Зависимости frontend (package.json)

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "@react-three/fiber": "^8.17",
    "@react-three/drei": "^9.114",
    "three": "^0.170",
    "blockly": "^11.2",
    "zustand": "^5.0",
    "react-split-pane": "^0.1.92"
  },
  "devDependencies": {
    "@types/react": "^18.3",
    "@types/three": "^0.170",
    "typescript": "^5.6",
    "vite": "^6.0",
    "@vitejs/plugin-react": "^4.3",
    "tailwindcss": "^3.4",
    "autoprefixer": "^10.4",
    "postcss": "^8.4"
  }
}
```

---

## Порядок реализации (roadmap)

### Phase 1: Каркас (1-2 дня)
- [ ] `npm create vite` + React + TypeScript + Tailwind
- [ ] Базовый layout: Header, SplitPane, BottomBar
- [ ] EmergencyStop (кнопка + Escape hotkey)
- [ ] ConnectionPanel (подключение к backend)

### Phase 2: 3D Viewer (2-3 дня)
- [ ] Three.js сцена с освещением и grid
- [ ] RobotModel — 6 звеньев с DH параметрами
- [ ] JointSliders → обновление 3D модели
- [ ] WebSocket телеметрия → автообновление модели
- [ ] OrbitControls, камера

### Phase 3: Blockly (2-3 дня)
- [ ] Интеграция Google Blockly в React
- [ ] Кастомные блоки (move, wait, loop, ik_move)
- [ ] Генератор JSON команд
- [ ] programRunner: последовательное выполнение
- [ ] UI: Run / Stop / Save / Load

### Phase 4: Полировка (1-2 дня)
- [ ] Полная телеметрия в BottomBar
- [ ] IK через клик в 3D
- [ ] Анимация траекторий
- [ ] Responsive design
- [ ] Тёмная тема (как в desktop приложении)

---

## Интеграция с Vite + FastAPI

В `vite.config.ts` настроить proxy на FastAPI:

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true }
    }
  },
  build: {
    outDir: '../static/dist'  // Продакшн: собрать в static/
  }
})
```

В продакшне: `vite build` → FastAPI раздаёт статику из `static/dist/`.
