import math
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import JointState
from std_msgs.msg import String, Empty
from trajectory_msgs.msg import JointTrajectoryPoint
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from ament_index_python.packages import get_package_prefix

JOINT_NAMES = ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]


@dataclass
class MotorState:
    position_rad: float = 0.0
    velocity_rad_s: float = 0.0
    effort: float = 0.0
    position_raw: int = 2048
    temperature: float = 0.0
    voltage: float = 0.0
    current: float = 0.0
    load: float = 0.0


@dataclass
class RobotParameters:
    speed: float = 0.5
    acceleration: float = 0.3
    torque_limit: float = 100.0
    mode: str = "position"
    gripper_open: float = 0.0


class RobotControlsNode(Node):
    def __init__(self):
        super().__init__("robot_controls_node")

        self.declare_parameter("port", "COM3")
        self.declare_parameter("baudrate", 1_000_000)
        self.declare_parameter("publish_rate_hz", 50.0)
        self.declare_parameter("offline_mode", False)

        port = self.get_parameter("port").value
        baudrate = self.get_parameter("baudrate").value
        publish_rate = self.get_parameter("publish_rate_hz").value
        offline = self.get_parameter("offline_mode").value

        self._connected = offline
        self._motor_states: list[MotorState] = [MotorState() for _ in range(6)]
        self._target_pose: Optional[tuple[float, float, float]] = None
        self._params = RobotParameters()

        if not offline:
            try:
                pkg_prefix = get_package_prefix("robot_control")
                ws_root = os.path.dirname(os.path.dirname(pkg_prefix))
                if ws_root not in sys.path:
                    sys.path.insert(0, ws_root)
            except Exception:
                pass
            try:
                from robot_control.hardware_interface import RobotHWInterface
                self._hw = RobotHWInterface.get_instance()
                ok = self._hw.initialize(port, baudrate, publish_rate)
                if ok:
                    self._connected = True
                    self.get_logger().info(f"Hardware connected: port={port}")
                else:
                    self.get_logger().warn(f"Could not connect to {port} — running in offline mode")
            except ImportError as e:
                self.get_logger().warn(
                    f"robot_control package not found ({e}) — running in offline mode"
                )
        else:
            self.get_logger().info("Offline mode — no hardware connection")

        reliable = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )

        # --- Publishers ---
        self._pub_joint_states = self.create_publisher(JointState, "/joint_states", reliable)
        self._pub_joint_states_robot = self.create_publisher(
            JointState, "/robot_controls/joint_states", reliable
        )
        self._pub_parameters = self.create_publisher(
            String, "/robot_controls/parameters/state", reliable
        )
        self._pub_status = self.create_publisher(String, "/robot_controls/status", reliable)

        # --- Subscribers ---
        self.create_subscription(
            PoseStamped, "/robot_controls/target_pose", self._on_target_pose, reliable
        )
        self.create_subscription(
            String, "/robot_controls/parameters/cmd", self._on_parameters_cmd, 10
        )
        self.create_subscription(
            Empty, "/robot_controls/stop", self._on_stop, 10
        )

        # --- Timers ---
        self.create_timer(1.0 / publish_rate, self._publish_state)
        self.create_timer(1.0, self._publish_parameters)
        self.create_timer(5.0, self._publish_status)

        self.get_logger().info("RobotControlsNode started")
        self.get_logger().info("  Published: /joint_states, /robot_controls/joint_states, /robot_controls/parameters/state")
        self.get_logger().info("  Subscribed: /robot_controls/target_pose, /robot_controls/parameters/cmd")

    # --- Callbacks ---

    def _on_target_pose(self, msg: PoseStamped):
        x_m = msg.pose.position.x
        y_m = msg.pose.position.y
        z_m = msg.pose.position.z
        x_mm = x_m * 1000.0
        y_mm = y_m * 1000.0
        z_mm = z_m * 1000.0
        self._target_pose = (x_mm, y_mm, z_mm)
        self.get_logger().info(f"Target pose: ({x_mm:.1f}, {y_mm:.1f}, {z_mm:.1f}) mm")

        try:
            from robot_control.kinematics_model import RobotKinematics6DOF, InverseKinematics6DOF
            kin = RobotKinematics6DOF()
            ik = InverseKinematics6DOF(kin)
            angles_deg = ik.solve(x_mm, y_mm, z_mm)
            if angles_deg:
                angles_rad = [math.radians(a) for a in angles_deg]
                self._write_to_hardware(angles_rad)
                self.get_logger().info(f"IK solved: {[f'{a:.3f}' for a in angles_rad]} rad")
            else:
                self.get_logger().error("IK failed — target unreachable")
        except ImportError:
            self.get_logger().warn("Kinematics module not available — skipping IK")

    def _on_parameters_cmd(self, msg: String):
        try:
            data = json.loads(msg.data)
            if "speed" in data:
                self._params.speed = float(data["speed"])
            if "acceleration" in data:
                self._params.acceleration = float(data["acceleration"])
            if "torque_limit" in data:
                self._params.torque_limit = float(data["torque_limit"])
            if "mode" in data:
                self._params.mode = str(data["mode"])
            if "gripper_open" in data:
                self._params.gripper_open = float(data["gripper_open"])
            self.get_logger().info(f"Parameters updated: {data}")
        except (json.JSONDecodeError, ValueError) as e:
            self.get_logger().error(f"Invalid parameters: {e}")

    def _on_stop(self, _: Empty):
        self.get_logger().warn("Emergency stop received")
        if self._connected:
            try:
                self._hw.emergency_stop()
            except AttributeError:
                pass

    # --- Hardware ---

    def _write_to_hardware(self, positions_rad: list[float]):
        if not self._connected:
            return
        try:
            self._hw.write_joint_positions(positions_rad)
        except AttributeError as e:
            self.get_logger().warn(f"Failed to write: {e}")

    def _read_from_hardware(self) -> list[MotorState]:
        if not self._connected:
            return [MotorState() for _ in range(6)]
        try:
            states = self._hw.read_joint_states()
            return [
                MotorState(
                    position_rad=s.position_rad,
                    velocity_rad_s=s.velocity_rad_s,
                    effort=s.effort,
                    position_raw=s.position_raw,
                )
                for s in states
            ]
        except AttributeError:
            return [MotorState() for _ in range(6)]

    # --- Publishing ---

    def _publish_state(self):
        self._motor_states = self._read_from_hardware()

        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = JOINT_NAMES
        for s in self._motor_states:
            msg.position.append(s.position_rad)
            msg.velocity.append(s.velocity_rad_s)
            msg.effort.append(s.effort)

        self._pub_joint_states.publish(msg)
        self._pub_joint_states_robot.publish(msg)

    def _publish_parameters(self):
        msg = String()
        msg.data = json.dumps({
            "speed": self._params.speed,
            "acceleration": self._params.acceleration,
            "torque_limit": self._params.torque_limit,
            "mode": self._params.mode,
            "gripper_open": self._params.gripper_open,
            "target_pose_mm": list(self._target_pose) if self._target_pose else None,
        })
        self._pub_parameters.publish(msg)

    def _publish_status(self):
        connected = self._connected
        target = self._target_pose
        msg = String()
        msg.data = json.dumps({
            "connected": connected,
            "mode": self._params.mode,
            "target_pose_mm": list(target) if target else None,
            "motor_count": 6,
        })
        self._pub_status.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RobotControlsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
