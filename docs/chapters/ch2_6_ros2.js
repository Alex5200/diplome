/**
 * ГЛАВА 2.6 — ROS2 интеграция
 *
 * Содержание:
 *   - Архитектура ROS2-пакета robot_control
 *   - Три ноды: robot_node, monitor_node, ik_service_node
 *   - Топики, сервисы, параметры
 *   - Launch-файл
 *   - Диаграмма взаимодействия нод
 *
 * Нумерация: таблицы 2.10–2.11, рисунки 2.9–2.10, листинги 2.13–2.14
 * Целевой объём: ~2–3 страницы
 */
module.exports = function (h) {
  const c = [];

  c.push(h.heading2("2.6 Интеграция с ROS2"));

  c.push(h.p("Robot Operating System 2 (ROS2) — это распределённый фреймворк для разработки робототехнических систем, обеспечивающий межпроцессное взаимодействие через типизированные топики и сервисы, управление жизненным циклом нод и интеграцию с широкой экосистемой робототехнических пакетов. Интеграция разработанного ПО с ROS2 открывает возможность использования манипулятора в составе сложных робототехнических систем: совместная работа с другими роботами, интеграция с системами компьютерного зрения, использование навигационного стека и инструментов визуализации (RViz2)."));

  c.push(h.p("ROS2-слой реализован как стандартный пакет ament_python с именем robot_control (директория ros2/robot_control/). Пакет содержит три независимых ноды, каждая из которых выполняет специализированную функцию и может быть запущена отдельно или совместно через launch-файл."));

  // --- Ноды ---
  c.push(h.heading3("Архитектура нод"));

  c.push(h.emptyLine());
  c.push(h.tableCaption("Таблица 2.10 — ROS2-ноды пакета robot_control"));
  c.push(h.makeTable(
    ["Нода", "Файл", "Частота", "Назначение"],
    [
      ["robot_node", "robot_node.py", "10 Гц", "Основное управление: приём команд, публикация состояния"],
      ["monitor_node", "monitor_node.py", "1 Гц", "Диагностика: температура, напряжение, нагрузка, алармы"],
      ["ik_service_node", "ik_service_node.py", "по запросу", "Сервис IK: решение обратной кинематики по запросу"],
    ],
    [2000, 2000, 1200, 3800]
  ));
  c.push(h.emptyLine());

  c.push(h.p("Разделение функциональности на три ноды (таблица 2.10) соответствует рекомендациям ROS2 по декомпозиции: каждая нода выполняет одну чётко определённую задачу и может быть перезапущена независимо от остальных. Нода robot_node работает на частоте 10 Гц, обеспечивая приём команд движения и публикацию текущего состояния суставов. Нода monitor_node работает на пониженной частоте 1 Гц, что достаточно для мониторинга медленно меняющихся параметров (температура, напряжение). Нода ik_service_node работает в реактивном режиме, обрабатывая запросы по мере поступления."));

  // --- Топики и сервисы ---
  c.push(h.heading3("Топики и сервисы"));

  c.push(h.emptyLine());
  c.push(h.tableCaption("Таблица 2.11 — Топики и сервисы ROS2-пакета"));
  c.push(h.makeTable(
    ["Тип", "Имя", "Тип сообщения", "Направление"],
    [
      ["Топик", "/robot/joint_states", "sensor_msgs/JointState", "Публикация (10 Гц)"],
      ["Топик", "/robot/joint_cmd", "trajectory_msgs/JointTrajectoryPoint", "Подписка"],
      ["Топик", "/robot/stop", "std_msgs/Empty", "Подписка"],
      ["Топик", "/robot/diagnostics", "diagnostic_msgs/DiagnosticArray", "Публикация (1 Гц)"],
      ["Топик", "/robot/temperature", "sensor_msgs/Temperature", "Публикация (1 Гц)"],
      ["Топик", "/robot/alarms", "std_msgs/String", "Публикация (по событию)"],
      ["Сервис", "/robot/ik/solve", "robot_control/SolveIK", "Запрос-ответ"],
    ],
    [1200, 2600, 3000, 2200]
  ));
  c.push(h.emptyLine());

  c.push(h.p("Таблица 2.11 содержит полный перечень топиков и сервисов ROS2-пакета. Состояния суставов публикуются в стандартном формате sensor_msgs/JointState, что обеспечивает совместимость с инструментами визуализации RViz2, пакетами планирования движения MoveIt2 и другими компонентами экосистемы ROS2. Команды движения принимаются в формате trajectory_msgs/JointTrajectoryPoint с позициями суставов в радианах."));

  c.push(h.p("Топик /robot/stop принимает сообщения типа std_msgs/Empty для экстренной остановки. Использование пустого сообщения гарантирует минимальную задержку обработки — не требуется десериализация полезной нагрузки. При получении сообщения на данный топик нода robot_node немедленно вызывает emergency_stop контроллера, прерывая любое текущее движение."));

  c.push(h.codeCaption("Листинг 2.13 — Нода robot_node: публикация состояния суставов"));
  c.push(...h.codeBlock([
    "class RobotNode(Node):",
    "    def __init__(self):",
    "        super().__init__('robot_node')",
    "        self.declare_parameter('port', 'COM3')",
    "        self.declare_parameter('baudrate', 1_000_000)",
    "        self.declare_parameter('publish_rate', 10.0)",
    "",
    "        self.joint_pub = self.create_publisher(",
    "            JointState, '/robot/joint_states', 10)",
    "        self.cmd_sub = self.create_subscription(",
    "            JointTrajectoryPoint, '/robot/joint_cmd', self._on_cmd, 10)",
    "        self.stop_sub = self.create_subscription(",
    "            Empty, '/robot/stop', self._on_stop, 10)",
    "",
    "        rate = self.get_parameter('publish_rate').value",
    "        self.create_timer(1.0 / rate, self._publish_state)",
  ]));
  c.push(h.emptyLine());

  c.push(h.p("Листинг 2.13 демонстрирует инициализацию ноды robot_node. Параметры (порт, скорость, частота публикации) объявляются через стандартный механизм ROS2-параметров, что позволяет изменять их при запуске через launch-файл или через командную строку. Частота публикации состояния суставов по умолчанию составляет 10 Гц — стандартное значение для задач мониторинга и визуализации."));

  // --- Launch ---
  c.push(h.heading3("Launch-файл"));

  c.push(h.p("Для одновременного запуска всех трёх нод с предконфигурированными параметрами реализован launch-файл ros2/launch/robot.launch.py. Launch-файл написан на Python (стандарт ROS2) и использует декларативный API для описания запускаемых нод, их параметров и зависимостей. При запуске через команду ros2 launch robot_control robot.launch.py все три ноды стартуют параллельно, при этом параметры подключения (COM-порт и baudrate) передаются через общий конфигурационный словарь."));

  c.push(h.codeCaption("Листинг 2.14 — Фрагмент launch-файла"));
  c.push(...h.codeBlock([
    "def generate_launch_description():",
    "    config = {'port': 'COM3', 'baudrate': 1_000_000}",
    "    return LaunchDescription([",
    "        Node(package='robot_control', executable='robot_node',",
    "             parameters=[config], output='screen'),",
    "        Node(package='robot_control', executable='monitor_node',",
    "             parameters=[config], output='screen'),",
    "        Node(package='robot_control', executable='ik_service_node',",
    "             output='screen'),",
    "    ])",
  ]));
  c.push(h.emptyLine());

  c.push(h.emptyLine());
  c.push(...h.figurePlaceholder("Рисунок 2.9 — Граф ROS2-нод и топиков (rqt_graph)"));
  c.push(h.emptyLine());

  c.push(h.p("На рисунке 2.9 представлен граф взаимодействия ROS2-нод, полученный с помощью инструмента rqt_graph. Граф наглядно демонстрирует однонаправленный поток данных: robot_node является центральным хабом, публикующим состояние суставов и принимающим команды; monitor_node подписывается на состояние суставов для дополнительной диагностики; ik_service_node работает независимо, обрабатывая запросы по мере поступления."));

  c.push(h.pageBreak());
  return c;
};
