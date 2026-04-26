# ST3215 Robot Control - Техническая документация

## Обзор проекта

Веб-приложение для управления 6-осевым роботом-манипулятором ST3215. Состоит из двух частей:

```
diplome/web/
├── main.py              # Точка входа API
├── api/                 # REST API endpoints
│   ├── auth.py         # Аутентификация JWT
│   ├── routes.py       # Управление роботом
│   └── websocket.py    # WebSocket телеметрия
├── frontend/           # React веб-интерфейс
└── docker-compose.yml # Docker разворот
```

---

## Backend (main.py)

### main.py - Точка входа
```bash
python main.py [опции]
```

**Опции:**
- `--no-auth` - Отключить авторизацию
- `--no-auth-secret` - Секрет для ограниченного доступа
- `--mock` - Использовать мок-контроллер (без робота)
- `--host` - Хост для запуска
- `--port` - Порт для запуска

**Примеры запуска:**
```bash
# Разработка без робота
python main.py --no-auth --mock

# Продакшен
python main.py

# Docker
docker-compose up -d
```

**Переменные окружения:**
- `JWT_SECRET` - Секрет для JWT токенов
- `ADMIN_PASSWORD` - Пароль админа (по умолч. admin)
- `AUTH_ENABLED` - Включить авторизацию (true/false)
- `MOCK_MODE` - Режим мока (true/false)

---

## API модули

### web/api/auth.py - Аутентификация

**Назначение:** JWT аутентификация и авторизация

**Компоненты:**

```python
# Переменные окружения
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me...")
JWT_ALGO = "HS256"
TOKEN_EXP_H = 24  # часов

# Пользователи (можно изменить через env)
_USERS = {
    "admin": os.environ.get("ADMIN_PASSWORD", "admin"),
    "operator": os.environ.get("OPERATOR_PASSWORD", "operator"),
}

# API токены для машин
_api_tokens: dict[str, APIToken] = {}
```

**Функции:**

1. `_create_jwt(payload, exp_hours)` - Создание JWT токена
2. `_decode_jwt(token)` - Проверка JWT токена
3. `_verify_api_token(token)` - Проверка API токена
4. `_verify_user(username, password)` - Проверка логина/пароля

**Endpoints:**

| Метод | Путь | Описание |
|------|------|----------|
| POST | /auth/login | Авторизация (username/password → JWT) |
| POST | /auth/token/generate | Генерация API токена |
| GET | /auth/token/list | Список токенов |
| DELETE | /auth/token/{prefix} | Удаление токена |
| GET | /auth/me | Информация о текущем user |

**Защита:**
```python
require_token  # Depends() - требует авторизацию
```

---

### web/api/routes.py - Управление роботом

**Назначение:** REST API для управления моторами

**Компоненты:**

```python
# Mock контроллер для разработки
class MockMotorController:
    def __init__(self, device="COM3"):
        self.device = device
        self.connected = False
        self.found_servos = [1, 2, 3, 4, 5, 6]
        self._positions = {i: 2048 for i in range(1, 7)}
    
    # Методы:
    # connect()    - подключение
    # disconnect() - отключение
    # scan_servos() - поиск моторов
    # read_motor_data(id) - чтение данных мотора
    # move_joint(index, pos, speed) - движение
    # move_all_joints(positions, speed) - движение всех
    # emergency_stop_all() - аварийная остановка
    # toggle_torque(id, enable) - вкл/выкл момент
```

**Endpoints:**

| Метод | Путь | Защита | Описание |
|------|------|--------|----------|
| GET | /api/status | Нет | Статус робота |
| POST | /api/connect | Да | Подключение |
| POST | /api/disconnect | Да | Отключение |
| POST | /api/scan | Да | Поиск моторов |
| POST | /api/move | Да | Движение сустава |
| POST | /api/move_all | Да | Движение всех |
| POST | /api/stop | Да | Аварийная остановка |
| POST | /api/torque | Да | Управление моментом |
| POST | /api/ik | Да | Инверсная кинематика |
| GET | /api/config | Да | Конфигурация |
| POST | /api/config/speed | Да | Установка скорости |

**Request/Response форматы:**

```python
# POST /api/connect
Request:  {"port": "COM3", "baudrate": 1000000}
Response: {"connected": True, "port": "COM3", "motors_found": [1,2,3,4,5,6]}

# POST /api/move
Request:  {"joint": 0, "position": 2048, "speed": 2400}
Response: {"joint": 0, "position": 2048, "speed": 2400}

# POST /api/move_all
Request:  {"positions": [2048, 2048, 2048, 2048, 2048, 2048], "speed": 2400}
Response: {"positions": [2048, 2048, 2048, 2048, 2048, 2048], "speed": 2400}

# POST /api/torque
Request:  {"motor_id": 1, "enable": True}
Response: {"motor_id": 1, "torque_enabled": True}

# POST /api/ik
Request:  {"x": 100, "y": 50, "z": 200}
Response: {"angles_deg": [0.0, -45.5, -30.2, ...], "error_mm": 0.15}
```

---

### web/api/websocket.py - Телеметрия

**Назначение:** Real-time передача данных моторов

```python
# Клиенты WebSocket
_clients: set[WebSocket] = set()

# Endpoint: GET /ws
# Формат сообщения:
{
    "type": "telemetry",
    "motors": {
        "1": {"position": 2048, "temperature": 35.5, ...},
        "2": {"position": 2049, "temperature": 36.0, ...},
        ...
    }
}
```

**Использование на клиенте:**
```javascript
const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "telemetry") {
        updateMotors(data.motors);
    }
};
```

---

## Frontend структура

```
frontend/src/
├── main.tsx              # Точка входа React
├── App.tsx               # Главный компонент
├── stores/
│   └── robotStore.ts    # Zustand store (состояние)
├── services/
│   ├── api.ts           # API вызовы
│   └── websocket.ts     # WebSocket менеджер
├── components/
│   ├── layout/
│   │   ├── Header.tsx   # Верхняя панель
│   │   ├── BottomBar.tsx # Нижняя панель
│   │   └── Footer.tsx    # Подвал
│   ├── controls/
│   │   ├── ConnectionPanel.tsx  # Подключение
│   │   ├── JointSliders.tsx     # Слайдеры суставов
│   │   ├── PosePresets.tsx       # Пресеты положений
│   │   ├── MotorConfigPanel.tsx # Настройки моторо��
│   │   └── EmergencyStop.tsx    # Аварийная остановка
│   ├── viewer3d/
│   │   ├── RobotScene.tsx     # 3D сцена
│   │   └── RobotModel.tsx       # 3D модель робота
│   ├── telemetry/
│   │   ├── MotorTable.tsx     # Таблица моторов
│   │   └── EventLog.tsx        # Лог событий
│   ├── docs/
│   │   └── DocsPanel.tsx       # Документация
│   └── blockly/
│       └── BlocklyEditor.tsx   # Программирование
├── types/
│   └── robot.ts         # TypeScript типы
├── utils/
│   ├── constants.ts    # Константы (DH параметры, имена)
│   └── kinematics.ts    # Прямая кинематика
└── index.css           # Глобальные стили
```

---

## Zustand Store (robotStore.ts)

```typescript
interface RobotState {
    // Подключение
    status: ConnectionStatus;  // disconnected | connecting | connected | error
    port: string;
    speed: number;           // 100-3400
    
    // Суставы
    jointAngles: number[];  // 6 углов в градусах
    
    // Телеметрия
    motors: Record<string, MotorData>;
    
    // Конфигурация моторов
    motorConfig: Record<string, MotorConfig>;
    
    // Режим свободных моторов
    freeMode: boolean;
    
    // Аварийная остановка
    isStopped: boolean;
    
    // Лог
    logs: LogEntry[];
    
    // IK цель
    ikTarget: [number, number, number] | null;
}
```

**Константы DH параметры (constants.ts):**
```typescript
DH_PARAMS = {
    L0: 19,   // База (мм)
    L1: 104,  // Плечо 1
    L2: 95,   // Плечо 2
    L3: 34,   // Локоть
    L4: 35,   // Запястье
    L5: 0,    // Инструмент
}

JOINT_NAMES = ["База (J1)", "Плечо 1 (J2)", ...]
SAFE_ANGLE_LIMITS = [[-180, 180], ...]
LINK_COLORS = ["#7dd3c0", "#a8e6cf", ...]
```

---

## API поток данных

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React)                        │
├─────────────────────────────────────────────────────────────┤
│  robotStore ──store──> State                               │
│       ↑                                                    │
│       │ setMotors() / setJointAngle()                      │
├─────────────────────────────────────────────────────────────┤
│  api.ts ──────────> fetch() ─────────> /api/*              │
│  websocket.ts ───> WebSocket ──────> /ws                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                       │
├───────────────────────────────────────────────────────���─���───┤
│  main.py ──────> app = FastAPI()                           │
│       │                                                    │
│       ├── routes.py ──> _controller = MotorController      │
│       │   ├── connect() ──> Serial/USB ──> Robot         │
│       │   ├── move_joint() ──> Serial ──> Мотор           │
│       │   ├── read_motor_data() ──> Serial ──> Мотор     │
│       │                                                    │
│       ├── websocket.py ──> push_telemetry() ──> Broadcast   │
│       │                                                    │
│       └── auth.py ───> require_token() ──> JWT verify     │
│           (или MockMotorController в режиме --mock)         │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
┌─────────────────────┐           ┌─────────────────────┐
│   ROBOT (Hardware)  │           │   WebSocket        │
│   ST3215 Robot     │           │   Browser Clients   │
│   via USB/Serial   │           │   Real-time updates  │
└─────────────────────┘           └─────────────────────┘
```

---

## Безопасность

### Защищённые endpoints (требуют токен):
- `/api/connect`
- `/api/disconnect`
- `/api/move`
- `/api/move_all`
- `/api/stop`
- `/api/torque`
- `/api/ik`
- `/api/config`

### Публичные endpoints:
- `/api/status` - Статус робота
- `/auth/login` - Авториза��ия

### Токен передаётся в заголовке:
```
Authorization: Bearer <token>
```

### Режимы авторизации:

1. **Полная авторизация** (AUTH_ENABLED=true)
   - Требуется JWT токен

2. **Отключённая** (--no-auth)
   - Требуется NO_AUTH_SECRET

3. **Мок режим** (--mock)
   - Работает без реального робота

---

## Docker разворот

```bash
# Создать .env файл
cp .env.example .env

# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Логи
docker-compose logs -f

# Остановить
docker-compose down
```

**Сервисы:**
- `robot-api` :8000 - API сервер
- `robot-web` :3000 - Веб-интерфейс

---

## Разработка

```bash
# Backend
pip install -e .
python main.py --no-auth --mock

# Frontend
cd frontend
npm install
npm run dev
```

---

## Файлы конфигурации

| Файл | Назначение |
|------|------------|
| `.env` | Локальные переменные |
| `.env.example` | Пример конфигурации |
| `docker-compose.yml` | Docker стек |
| `Dockerfile` | API Docker образ |
| `frontend/Dockerfile` | Frontend Docker образ |
| `Makefile` | Удобные команды |
| `pyproject.toml` | Python зависимости |
| `frontend/package.json` | Node зависимости |

---

## Version: 2.0.0