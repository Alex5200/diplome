#!/usr/bin/env python3
"""
Kinematics Node for 6-DOF Robot Arm.

Subscribes to /robot/target_pose (geometry_msgs/PoseStamped) in meters,
solves Inverse Kinematics (IK) using core logic, and publishes
joint commands to /robot/joint_cmd for the robot and
/joint_states for external tools like Lerobot/MuJoCo.
"""

import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from trajectory_msgs.msg import JointTrajectoryPoint
from sensor_msgs.msg import JointState

# Import local kinematics model (copied from core/)
from robot_control.kinematics_model import RobotKinematics6DOF, InverseKinematics6DOF


class KinematicsNode(Node):
    def __init__(self):
        super().__init__('kinematics_node')
        
        # Initialize Kinematics
        self.kin = RobotKinematics6DOF()
        self.ik = InverseKinematics6DOF(self.kin)
        
        # QoS profiles
        reliable_qos = rclpy.qos.QoSProfile(
            reliability=rclpy.qos.QoSReliabilityPolicy.RELIABLE,
            history=rclpy.qos.QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # Subscriber: Target Pose (XYZ in meters)
        self.pose_sub = self.create_subscription(
            PoseStamped, '/robot/target_pose', self.pose_callback, reliable_qos)
        
        # Publisher: Command for robot_node_v2
        self.joint_cmd_pub = self.create_publisher(
            JointTrajectoryPoint, '/robot/joint_cmd', reliable_qos)
        
        # Publisher: Standard JointState for Lerobot / MuJoCo / RViz
        self.joint_state_pub = self.create_publisher(
            JointState, '/joint_states', reliable_qos)
            
        # Publisher: Additional command topic for Lerobot
        self.joint_commands_pub = self.create_publisher(
            JointState, '/joint_commands', reliable_qos)

        self.get_logger().info('Kinematics Node started.')
        self.get_logger().info('Listening on: /robot/target_pose')
        self.get_logger().info('Publishing to: /robot/joint_cmd, /joint_states, /joint_commands')

    def pose_callback(self, msg: PoseStamped):
        # Convert meters to mm (kinematics works in mm)
        x = msg.pose.position.x * 1000.0
        y = msg.pose.position.y * 1000.0
        z = msg.pose.position.z * 1000.0
        
        self.get_logger().info(f'Received target: ({x:.1f}, {y:.1f}, {z:.1f}) mm')
        
        # Solve IK
        angles_deg = self.ik.solve(x, y, z)
        
        if angles_deg is None:
            self.get_logger().error('IK Failed: Target out of reach or no solution found.')
            return
            
        # Convert degrees to radians for ROS messages
        angles_rad = [math.radians(a) for a in angles_deg]
        
        # 1. Publish to /robot/joint_cmd (JointTrajectoryPoint for robot_node_v2)
        jt_msg = JointTrajectoryPoint()
        jt_msg.positions = angles_rad
        jt_msg.velocities = [0.0] * 6
        self.joint_cmd_pub.publish(jt_msg)
        
        # 2. Publish to /joint_states (Standard for Lerobot/MuJoCo)
        js_msg = JointState()
        js_msg.header.stamp = self.get_clock().now().to_msg()
        js_msg.header.frame_id = 'base_link'
        js_msg.name = ['joint_0', 'joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5']
        js_msg.position = angles_rad
        js_msg.velocity = []
        js_msg.effort = []
        
        self.joint_state_pub.publish(js_msg)
        self.joint_commands_pub.publish(js_msg)  # Duplicate for Lerobot compatibility
        
        self.get_logger().info(f'IK Success: {[f"{a:.3f}" for a in angles_rad]} rad')


def main(args=None):
    rclpy.init(args=args)
    node = KinematicsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
