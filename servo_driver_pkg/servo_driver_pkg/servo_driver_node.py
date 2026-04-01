import rclpy
from rclpy.node import Node
from rclpy.timer import Timer
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32MultiArray, Bool
from st3215 import ST3215  # Твоя библиотека
import time


class ServoDriverNode(Node):
    def __init__(self):
        super().__init__("servo_driver_node")

        # --- Параметры ---
        self.declare_parameter("port", "COM3")
        self.declare_parameter("servo_ids", [1, 2, 3, 4, 5, 6])
        self.declare_parameter("update_rate_hz", 20.0)  # Частота опроса (Гц)

        self.port = self.get_parameter("port").get_parameter_value().string_value
        self.ids = (
            self.get_parameter("servo_ids").get_parameter_value().integer_array_value
        )
        self.rate = (
            self.get_parameter("update_rate_hz").get_parameter_value().double_value
        )

        # --- Инициализация сервоприводов ---
        try:
            self.servo_bus = ST3215(self.port)
            self.get_logger().info(f"✓ Connected to {self.port}")
        except Exception as e:
            self.get_logger().error(f"❌ Failed to connect to {self.port}: {e}")
            raise e

        # --- Публикаторы (Топики для данных) ---
        # Позиция и Нагрузка (Effort)
        self.pub_joint_state = self.create_publisher(
            JointState, "/servos/joint_states", 10
        )
        # Температура (отдельно, т.к. в JointState нет поля для темп)
        self.pub_temp = self.create_publisher(
            Float32MultiArray, "/servos/temperatures", 10
        )
        # Статус движения (общий или можно сделать массив)
        self.pub_moving = self.create_publisher(Bool, "/servos/is_moving", 10)

        # --- Подписчик (Команды на движение) ---
        # Ожидает массив целевых позиций [pos1, pos2, ...]
        self.sub_command = self.create_subscription(
            Float32MultiArray, "/servos/command", self.command_callback, 10
        )

        # --- Таймер (Опрос данных) ---
        self.timer = self.create_timer(1.0 / self.rate, self.timer_callback)

        self.get_logger().info(f"🚀 Servo Driver Node started for IDs: {self.ids}")

    def command_callback(self, msg):
        """Получение команды на движение"""
        targets = msg.data
        if len(targets) != len(self.ids):
            self.get_logger().warn(
                f"Command length mismatch! Expected {len(self.ids)}, got {len(targets)}"
            )
            return

        self.get_logger().info("📩 Received movement command")

        for i, servo_id in enumerate(self.ids):
            target_pos = int(targets[i])
            # Вызываем MoveTo из твоей библиотеки
            # wait=False важно, чтобы не блокировать ноду
            try:
                self.servo_bus.MoveTo(
                    servo_id, target_pos, speed=100, acc=50, wait=False
                )
            except Exception as e:
                self.get_logger().error(f"Failed to move servo {servo_id}: {e}")

    def timer_callback(self):
        """Периодический опрос состояния сервоприводов"""
        joint_msg = JointState()
        temp_msg = Float32MultiArray()
        moving_status = False  # Флаг: движется ли хоть один

        joint_msg.header.stamp = self.get_clock().now().to_msg()
        joint_msg.name = [f"servo_{id}" for id in self.ids]

        temp_data = []

        for servo_id in self.ids:
            try:
                # 1. Позиция
                pos = self.servo_bus.ReadPosition(servo_id)
                joint_msg.position.append(float(pos))
                joint_msg.velocity.append(0.0)  # Если библиотека не дает скорость

                # 2. Нагрузка (Load/Torque) -> мапим в Effort
                # ПРОВЕРЬ НАЗВАНИЕ МЕТОДА В БИБЛИОТЕКЕ (например ReadLoad или ReadCurrent)
                try:
                    load = self.servo_bus.ReadLoad(servo_id)
                except AttributeError:
                    load = 0.0  # Заглушка, если метода нет
                joint_msg.effort.append(float(load))

                # 3. Температура
                # ПРОВЕРЬ НАЗВАНИЕ МЕТОДА (например ReadTemperature)
                try:
                    temp = self.servo_bus.ReadTemperature(servo_id)
                except AttributeError:
                    temp = 0.0
                temp_data.append(float(temp))

                # 4. Статус движения
                is_moving = self.servo_bus.IsMoving(servo_id)
                if is_moving:
                    moving_status = True

            except Exception as e:
                self.get_logger().warn(f"Error reading servo {servo_id}: {e}")
                # Заполняем нулями при ошибке, чтобы не ломать массив
                joint_msg.position.append(0.0)
                joint_msg.effort.append(0.0)
                temp_data.append(0.0)

        # Публикация данных
        temp_msg.data = temp_data
        self.pub_joint_state.publish(joint_msg)
        self.pub_temp.publish(temp_msg)
        self.pub_moving.publish(Bool(data=moving_status))


def main(args=None):
    rclpy.init(args=args)
    node = ServoDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
