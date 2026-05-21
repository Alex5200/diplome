import sys
import math
import tty
import termios
import select
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from builtin_interfaces.msg import Time

STEP = 0.01


class TeleopNode(Node):
    def __init__(self):
        super().__init__("teleop_node")

        self.declare_parameter("step", 0.01)
        self.declare_parameter("frame_id", "base_link")

        step = self.get_parameter("step").value
        self._frame_id = self.get_parameter("frame_id").value

        self._x = 0.15
        self._y = 0.0
        self._z = 0.15

        self._pub = self.create_publisher(PoseStamped, "/robot_controls/target_pose", 10)
        self._status_pub = self.create_publisher(String, "/robot_controls/teleop/status", 10)

        self._key_thread = threading.Thread(target=self._key_loop, daemon=True)
        self._running = True

        self._print_help()
        self._key_thread.start()

        self.create_timer(0.5, self._publish_status)
        self.get_logger().info("TeleopNode started — use WASD/QE/+= to move")

    def _print_help(self):
        print()
        print("┌─────────────────────────────────────────────┐")
        print("│         TELEOP — robot_controls            │")
        print("├─────────────────────────────────────────────┤")
        print("│  W/S  — увеличить/уменьшить Z    (вверх/вниз) │")
        print("│  A/D  — уменьшить/увеличить X    (влево/вправо)│")
        print("│  Q/E  — уменьшить/увеличить Y    (ближе/дальше)│")
        print("│  R    — шаг крупнее (×10)                   │")
        print("│  F    — шаг мельче (÷10)                    │")
        print("│  H    — home (0, 0, 0)                     │")
        print("│  Space — отправить позицию                  │")
        print("│  P    — напечатать текущую позицию          │")
        print("│  Ctrl+C — выход                             │")
        print("└─────────────────────────────────────────────┘")
        print()

    def _get_key(self):
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            dr, _, _ = select.select([sys.stdin], [], [], 0.1)
            if dr:
                return sys.stdin.read(1)
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def _key_loop(self):
        step = STEP
        while self._running and rclpy.ok():
            key = self._get_key()
            if key is None:
                continue

            changed = False
            if key == "w":
                self._z += step; changed = True
            elif key == "s":
                self._z -= step; changed = True
            elif key == "a":
                self._x -= step; changed = True
            elif key == "d":
                self._x += step; changed = True
            elif key == "q":
                self._y -= step; changed = True
            elif key == "e":
                self._y += step; changed = True
            elif key == "r":
                step = round(step * 10, 4); print(f"  step={step}")
            elif key == "f":
                step = round(step / 10, 4); print(f"  step={step}")
            elif key == "h":
                self._x = 0.15; self._y = 0.0; self._z = 0.15; changed = True
                print("  HOME")
            elif key == " ":
                self._publish_pose()
                print(
                    f"  SENT: ({self._x:.3f}, {self._y:.3f}, {self._z:.3f})"
                )
            elif key == "p":
                print(
                    f"  POS:  ({self._x:.3f}, {self._y:.3f}, {self._z:.3f})  "
                    f"step={step}"
                )
            elif key == "\x03":
                self._running = False
                break

            if changed:
                self._print_position(step)

    def _print_position(self, step):
        sys.stdout.write(
            f"\r  XYZ: ({self._x:6.3f}, {self._y:6.3f}, {self._z:6.3f})  "
            f"step={step:.4f}  [Space=send, Ctrl+C=quit]  "
        )
        sys.stdout.flush()

    def _publish_pose(self):
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id
        msg.pose.position.x = self._x
        msg.pose.position.y = self._y
        msg.pose.position.z = self._z
        msg.pose.orientation.w = 1.0
        self._pub.publish(msg)

    def _publish_status(self):
        status = String()
        status.data = f"x={self._x:.3f} y={self._y:.3f} z={self._z:.3f}"
        self._status_pub.publish(status)

    def destroy_node(self):
        self._running = False
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = TeleopNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
