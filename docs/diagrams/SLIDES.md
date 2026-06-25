# Структура слайдов — Архитектура и подходы

Данный документ описывает слайды для защиты дипломной работы. 
Каждый раздел = отдельный слайд (или группа слайдов).

---

## Раздел 1: Введение и постановка задачи (3 слайда)

### Слайд 1.1 — Титульный
- Название проекта: "Система управления 6-осевым роботом-манипулятором на базе сервомоторов ST3215"
- Автор: Александр Ляхов
- Научный руководитель
- ВУЗ, кафедра, год

### Слайд 1.2 — Проблематика (три столбца)
1. **Когнитивная перегрузка** — сложные фреймворки (ROS2) отвлекают от изучения кинематики. Решение: блочное программирование как "педагогические леса"
2. **Задержки (Latency)** — DDS в ROS2 вносит недетерминированность. Решение: собственный UART/RS-485 контроллер (3-15 мс)
3. **Sim-to-Real Gap** — опасность тестирования на реальном оборудовании. Решение: цифровой двойник MuJoCo с двунаправленной синхронизацией

### Слайд 1.3 — Цели и задачи работы
- Разработка multi-layered архитектуры (Desktop + Web + ROS2 + AI/ML)
- Единая кодовая база для симуляции и реального робота
- Интеграция VLM (Qwen3 VL) для vision-based управления
- Обучение с подкреплением (DQN/PPO) в симуляции MuJoCo

---

## Раздел 2: Общая архитектура системы (2 слайда)

### Слайд 2.1 — Layered Architecture (Overview)
**Диаграмма:** `architecture_overview.png`

**Слои (сверху вниз):**
1. **User Interfaces** — Desktop (CustomTkinter), Web (React/Three.js), CLI (ROS2)
2. **Application Services** — RobotService, KinematicsService, AI/ML services
3. **Core Modules** — EventBus (Pub-Sub), Container (DI), BaseService, Kinematics (DH/DLS)
4. **Communication Layer** — UART/RS-485, WebSocket, REST API, UDP, DDS
5. **Hardware Layer** — ST3215 servos, USB-Serial

**Ключевые паттерны:**
- `Singleton` — EventBus, RobotHWInterface
- `Dependency Injection` — Container
- `Template Method` — BaseService (init/start/stop)
- `Strategy` — AIProvider (Ollama/LM Studio/OpenAI)
- `Observer` — EventBus (Pub-Sub)

### Слайд 2.2 — Модульность и слабая связность
- Все модули общаются через EventBus (шина событий)
- DI Container управляет зависимостями (ленивая инициализация, singleton)
- BaseService предоставляет единый жизненный цикл (initialize → start → stop)
- Каждый сервис может работать независимо для тестирования

---

## Раздел 3: Desktop-приложение (2 слайда)

### Слайд 3.1 — Архитектура Desktop GUI
**Диаграмма:** `desktop_architecture.png`

**Трехслойная архитектура:**
- **Views (Tkinter)** — RobotControlGUI, панели управления, 3D визуализация (Matplotlib)
- **Services** — RobotService (управление моторами), KinematicsService (FK/IK), ProgramService
- **Controllers** — MotorController (UART), MotorMonitor (асинхронный polling)

### Слайд 3.2 — Возможности Desktop
- Подключение по USB-Serial, сканирование моторов
- Построение карты моторов (ID → сустав)
- Jog-режим (ручное управление) с контролем скорости
- 3D визуализация в реальном времени (DH → forward kinematics)
- Блочное программирование последовательностей
- Безопасность: emergency stop, температурные лимиты

---

## Раздел 4: Web-приложение (2 слайда)

### Слайд 4.1 — Full-stack архитектура
**Диаграмма:** `web_architecture.png`

- **Frontend:** React 19 + TypeScript, Three.js (3D viewer), Blockly (программирование), Zustand (state)
- **Backend:** FastAPI, JWT Auth, REST API, WebSocket telemetry
- **Mock-режим:** разработка без реального робота

### Слайд 4.2 — API и real-time телеметрия
- REST endpoints: `/api/status`, `/api/move`, `/api/ik`, `/api/torque` и др.
- WebSocket: real-time push (положения, температура, нагрузка)
- JWT-аутентификация, API-токены для машин
- Docker Compose: API (:8000) + Frontend (:3000)

---

## Раздел 5: ROS2 интеграция (1-2 слайда)

### Слайд 5.1 — Архитектура ROS2
**Диаграмма:** `ros2_architecture.png`

- **Ноды:** robot_node_v2 (joint_states + joint_cmd), monitor_node, IK service
- **Топики:** `/robot/joint_states`, `/robot/joint_cmd`, `/robot/diagnostics`
- **ros2_control:** Hardware Interface bridge для ros2_control
- **Gazebo:** симуляция с URDF/xacro моделью
- **Rosbag:** запись и воспроизведение траекторий

**Ключевое решение:** критический путь "зрение → мотор" НЕ проходит через ROS2 DDS — используется прямой UART (3-15 мс вместо 50-200 мс через DDS)

---

## Раздел 6: AI/ML подсистема (2 слайда)

### Слайд 6.1 — Архитектура AI/ML
**Диаграмма:** `ai_ml_architecture.png`

- **AIProvider (Strategy Pattern):** единый фасад для Ollama, LM Studio, OpenAI
- **AIRobotControllerService:** VLM-цикл (кадр камеры → промпт → движение)
- **VisionTrackerService:** PID-регулятор + VLM детекция объекта
- **MLTrackingService:** локальный PyTorch/YOLO трекинг

### Слайд 6.2 — Обучение с подкреплением (RL)
- **Среда:** RobotArmEnv (Gymnasium, 18-dim obs, 7-dim action)
- **Агенты:** DQN (discrete) и PPO (continuous)
- **Curriculum Learning:** поэтапное усложнение (reach → pick → place)
- **Sim-to-Real:** MuJoCo digital twin → перенос на реального робота

---

## Раздел 7: Коммуникация и развертывание (1 слайд)

### Слайд 7.1 — Deployment и Latency Budget
**Диаграмма:** `deployment_communication.png`

| Протокол | Задержка | Применение |
|----------|----------|------------|
| UART/RS-485 | 3-15 мс | Управление моторами (критический путь) |
| WebSocket | 10-50 мс | Real-time телеметрия |
| HTTP | 100-500 мс | REST API |
| DDS (ROS2) | 50-200 мс | Мониторинг, диагностика |
| VLM (Ollama) | 1-5 с | Vision-based управление |

**Деплоймент:** Host PC (Desktop + Web + Ollama + MuJoCo) + Docker (ROS2 + Gazebo)

---

## Раздел 8: Заключение (1-2 слайда)

### Слайд 8.1 — Итоги
- Разработана multi-layered система с Desktop, Web, ROS2 и AI интерфейсами
- Решены три ключевые проблемы: когнитивная перегрузка (блоки), latency (UART 3-15ms), Sim-to-Real (MuJoCo mirror)
- Единая кодовая база для симуляции и реального робота
- Интегрированы современные AI/ML подходы (VLM, RL, Computer Vision)

### Слайд 8.2 — Перспективы развития
- **RRTConnect + FCL:** планирование пути без столкновений
- **MediaPipe:** жестовое управление (21 точка кисти)
- **Zero-copy video:** снижение задержек видео (shared memory)

---

## Приложение: Соответствие диаграмм слайдам

| Слайд | Диаграмма | Файл |
|-------|-----------|------|
| 2.1 | Общая архитектура | `architecture_overview.png` |
| 3.1 | Desktop GUI | `desktop_architecture.png` |
| 4.1 | Web full-stack | `web_architecture.png` |
| 5.1 | ROS2 интеграция | `ros2_architecture.png` |
| 6.1 | AI/ML подсистема | `ai_ml_architecture.png` |
| 7.1 | Развертывание | `deployment_communication.png` |

---

## Рекомендации по оформлению слайдов

1. **Используйте PlantUML как источник**: любые изменения в коде → обновляете .puml → регенерируете .png
2. **Общий стиль**: минималистично, без лишних анимаций, монохромно-синяя гамма
3. **Аннотации на диаграммах**: ключевые цифры (latency, количество сервоприводов)
4. **Демонстрация**: показать работу Desktop + камера + VLM + робот (1-2 мин видео)
