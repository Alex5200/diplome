#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kinematics for OMY-F3M Robot Arm
6-DOF manipulator with DYNAMIXEL-Y actuators
"""

import numpy as np
from scipy.optimize import least_squares
import math


class OMYF3MKinematics:
    """
    Kinematics class for OMY-F3M robot arm

    Specifications:
    - 6 DOF
    - Reach: 580 mm
    - Joint 1, 2: YM080-230-A099-RH (±360°)
    - Joint 3: YM070-210-A099-RH (±150°)
    - Joint 4, 5, 6: YM070-210-A099-RH (±360°)
    """

    def __init__(self):
        # DH Parameters (modified)
        # Based on the technical drawing dimensions
        # Format: [alpha, a, d, theta_offset]

        # Link lengths from the drawing (in mm)
        self.d1 = 94.0  # Base to Joint 2
        self.a2 = 265.8  # Joint 2 to Joint 3
        self.a3 = 222.0  # Joint 3 to Joint 4
        self.d4 = 51.0  # Offset for Joint 4
        self.d5 = 44.5  # Offset for Joint 5
        self.d6 = 125.0  # Joint 5 to end effector (gripper)

        # Joint limits (in radians)
        self.joint_limits = {
            "q1": (-np.pi, np.pi),  # Joint 1: ±360°
            "q2": (-np.pi, np.pi),  # Joint 2: ±360°
            "q3": (-5 * np.pi / 6, 5 * np.pi / 6),  # Joint 3: ±150°
            "q4": (-np.pi, np.pi),  # Joint 4: ±360°
            "q5": (-np.pi, np.pi),  # Joint 5: ±360°
            "q6": (-np.pi, np.pi),  # Joint 6: ±360°
        }

        # Home position (all joints at 0)
        self.home_position = np.zeros(6)

    def dh_transform(self, alpha, a, d, theta):
        """
        Compute Denavit-Hartenberg transformation matrix

        Args:
            alpha: link twist
            a: link length
            d: link offset
            theta: joint angle

        Returns:
            4x4 homogeneous transformation matrix
        """
        ct = np.cos(theta)
        st = np.sin(theta)
        ca = np.cos(alpha)
        sa = np.sin(alpha)

        T = np.array(
            [
                [ct, -st * ca, st * sa, a * ct],
                [st, ct * ca, -ct * sa, a * st],
                [0, sa, ca, d],
                [0, 0, 0, 1],
            ]
        )

        return T

    def forward_kinematics(self, joint_angles):
        """
        Compute forward kinematics

        Args:
            joint_angles: array of 6 joint angles [q1, q2, q3, q4, q5, q6] in radians

        Returns:
            4x4 homogeneous transformation matrix (end-effector pose)
        """
        q1, q2, q3, q4, q5, q6 = joint_angles

        # DH parameters for each joint
        # Modified DH convention
        T01 = self.dh_transform(-np.pi / 2, 0, self.d1, q1)
        T12 = self.dh_transform(0, 0, 0, q2 - np.pi / 2)
        T23 = self.dh_transform(0, self.a2, 0, q3)
        T34 = self.dh_transform(-np.pi / 2, self.a3, self.d4, q4)
        T45 = self.dh_transform(np.pi / 2, 0, 0, q5)
        T56 = self.dh_transform(-np.pi / 2, 0, 0, q6)

        # End effector transformation (gripper offset)
        T6E = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, self.d6], [0, 0, 0, 1]])

        # Total transformation
        T02 = T01 @ T12
        T03 = T02 @ T23
        T04 = T03 @ T34
        T05 = T04 @ T45
        T06 = T05 @ T56
        T0E = T06 @ T6E

        return T0E

    def get_position(self, joint_angles):
        """
        Get end-effector position

        Args:
            joint_angles: array of 6 joint angles in radians

        Returns:
            position: [x, y, z] in mm
        """
        T = self.forward_kinematics(joint_angles)
        return T[0:3, 3]

    def get_orientation(self, joint_angles):
        """
        Get end-effector orientation as rotation matrix

        Args:
            joint_angles: array of 6 joint angles in radians

        Returns:
            rotation_matrix: 3x3 rotation matrix
        """
        T = self.forward_kinematics(joint_angles)
        return T[0:3, 0:3]

    def get_euler_angles(self, joint_angles):
        """
        Get end-effector orientation as Euler angles (ZYX convention)

        Args:
            joint_angles: array of 6 joint angles in radians

        Returns:
            euler_angles: [roll, pitch, yaw] in radians
        """
        R = self.get_orientation(joint_angles)

        # Extract Euler angles (ZYX convention)
        if R[2, 0] < 1:
            if R[2, 0] > -1:
                pitch = -np.arcsin(R[2, 0])
                roll = np.arctan2(R[2, 1] / np.cos(pitch), R[2, 2] / np.cos(pitch))
                yaw = np.arctan2(R[1, 0] / np.cos(pitch), R[0, 0] / np.cos(pitch))
            else:
                pitch = np.pi / 2
                roll = 0
                yaw = np.arctan2(-R[0, 1], R[1, 1])
        else:
            pitch = -np.pi / 2
            roll = 0
            yaw = np.arctan2(-R[0, 1], R[1, 1])

        return np.array([roll, pitch, yaw])

    def jacobian(self, joint_angles, delta=1e-6):
        """
        Compute geometric Jacobian using numerical differentiation

        Args:
            joint_angles: array of 6 joint angles in radians
            delta: small displacement for numerical differentiation

        Returns:
            J: 6x6 Jacobian matrix
        """
        J = np.zeros((6, 6))

        # Get current transformation
        T0 = self.forward_kinematics(joint_angles)
        p0 = T0[0:3, 3]
        R0 = T0[0:3, 0:3]

        for i in range(6):
            # Perturb joint i
            q_perturbed = joint_angles.copy()
            q_perturbed[i] += delta

            # Get perturbed transformation
            T1 = self.forward_kinematics(q_perturbed)
            p1 = T1[0:3, 3]
            R1 = T1[0:3, 0:3]

            # Linear velocity component
            J[0:3, i] = (p1 - p0) / delta

            # Angular velocity component
            dR = (R1 - R0) / delta
            # Convert to angular velocity using skew-symmetric matrix
            omega = np.array([dR[2, 1] - dR[1, 2], dR[0, 2] - dR[2, 0], dR[1, 0] - dR[0, 1]]) / 2
            J[3:6, i] = omega

        return J

    def inverse_kinematics(self, target_pose, q0=None, max_iter=100, tol=1e-6):
        """
        Compute inverse kinematics using numerical optimization

        Args:
            target_pose: 4x4 homogeneous transformation matrix (desired pose)
            q0: initial guess for joint angles (default: home position)
            max_iter: maximum number of iterations
            tol: convergence tolerance

        Returns:
            joint_angles: array of 6 joint angles in radians (if successful)
            success: boolean indicating if IK converged
        """
        if q0 is None:
            q0 = self.home_position.copy()

        target_pos = target_pose[0:3, 3]
        target_rot = target_pose[0:3, 0:3]

        def ik_objective(q):
            # Compute forward kinematics
            T = self.forward_kinematics(q)
            current_pos = T[0:3, 3]
            current_rot = T[0:3, 0:3]

            # Position error
            pos_error = current_pos - target_pos

            # Orientation error (using rotation matrix difference)
            R_error = current_rot @ target_rot.T
            # Convert to axis-angle representation
            trace = np.trace(R_error)
            if trace > 3:
                trace = 3
            elif trace < -3:
                trace = -3
            angle = np.arccos((trace - 1) / 2)

            if angle < 1e-6:
                orient_error = np.zeros(3)
            else:
                axis = np.array(
                    [
                        R_error[2, 1] - R_error[1, 2],
                        R_error[0, 2] - R_error[2, 0],
                        R_error[1, 0] - R_error[0, 1],
                    ]
                ) / (2 * np.sin(angle))
                orient_error = axis * angle

            # Combined error
            error = np.concatenate([pos_error * 1000, orient_error])  # Weight position more
            return error

        # Solve using least squares
        result = least_squares(ik_objective, q0, method="lm", max_nfev=max_iter, ftol=tol)

        success = result.success and result.cost < 1e-6

        return result.x, success

    def inverse_kinematics_analytical(self, target_pos, target_euler=None):
        """
        Analytical inverse kinematics (simplified geometric solution)

        Args:
            target_pos: [x, y, z] target position in mm
            target_euler: [roll, pitch, yaw] target orientation (optional)

        Returns:
            joint_angles: array of 6 joint angles (if solvable)
            success: boolean
        """
        x, y, z = target_pos

        # Joint 1: Base rotation
        q1 = np.arctan2(y, x)

        # Distance from base to target (projected)
        r = np.sqrt(x**2 + y**2)

        # Simplified geometric solution for joints 2 and 3
        # This is a simplified version - full analytical solution is complex

        # Joint 2: Shoulder
        # Consider the vertical plane
        z_offset = z - self.d1

        # Law of cosines for triangle formed by links 2 and 3
        dist = np.sqrt(r**2 + z_offset**2)

        # Check if target is reachable
        if dist > (self.a2 + self.a3):
            return None, False

        # Angle to target
        psi = np.arctan2(z_offset, r)

        # Angle in triangle
        cos_phi = (self.a2**2 + dist**2 - self.a3**2) / (2 * self.a2 * dist)
        cos_phi = np.clip(cos_phi, -1, 1)
        phi = np.arccos(cos_phi)

        q2 = psi + phi + np.pi / 2

        # Joint 3: Elbow
        cos_q3 = (self.a2**2 + self.a3**2 - dist**2) / (2 * self.a2 * self.a3)
        cos_q3 = np.clip(cos_q3, -1, 1)
        q3 = np.arccos(cos_q3) - np.pi

        # For joints 4, 5, 6, we need orientation
        if target_euler is None:
            q4, q5, q6 = 0, 0, 0
        else:
            # Simplified wrist solution
            roll, pitch, yaw = target_euler
            q4 = roll
            q5 = pitch
            q6 = yaw

        joint_angles = np.array([q1, q2, q3, q4, q5, q6])

        return joint_angles, True

    def check_joint_limits(self, joint_angles):
        """
        Check if joint angles are within limits

        Args:
            joint_angles: array of 6 joint angles in radians

        Returns:
            valid: boolean
            violations: list of joint limit violations
        """
        violations = []
        joint_names = ["q1", "q2", "q3", "q4", "q5", "q6"]

        for i, (q, name) in enumerate(zip(joint_angles, joint_names)):
            q_min, q_max = self.joint_limits[name]
            if q < q_min or q > q_max:
                violations.append(
                    {
                        "joint": i + 1,
                        "name": name,
                        "value": q,
                        "min": q_min,
                        "max": q_max,
                    }
                )

        return len(violations) == 0, violations

    def get_workspace_points(self, n_points=100):
        """
        Generate points in the robot workspace for visualization

        Args:
            n_points: number of points to generate

        Returns:
            points: Nx3 array of reachable positions
        """
        points = []

        # Sample joint space
        for _ in range(n_points):
            q = np.array(
                [
                    np.random.uniform(*self.joint_limits["q1"]),
                    np.random.uniform(*self.joint_limits["q2"]),
                    np.random.uniform(*self.joint_limits["q3"]),
                    np.random.uniform(*self.joint_limits["q4"]),
                    np.random.uniform(*self.joint_limits["q5"]),
                    np.random.uniform(*self.joint_limits["q6"]),
                ]
            )

            pos = self.get_position(q)
            points.append(pos)

        return np.array(points)


# Example usage and testing
if __name__ == "__main__":
    # Create kinematics object
    kinematics = OMYF3MKinematics()

    print("=" * 60)
    print("OMY-F3M Robot Kinematics")
    print("=" * 60)

    # Test forward kinematics
    print("\n1. Forward Kinematics Test:")
    print("-" * 40)

    # Home position
    q_home = np.zeros(6)
    T_home = kinematics.forward_kinematics(q_home)
    pos_home = kinematics.get_position(q_home)
    print(f"Home position: {pos_home}")

    # Test position
    q_test = np.array([0, -np.pi / 4, np.pi / 2, 0, -np.pi / 4, 0])
    T_test = kinematics.forward_kinematics(q_test)
    pos_test = kinematics.get_position(q_test)
    euler_test = kinematics.get_euler_angles(q_test)

    print(f"\nTest joint angles (rad): {q_test}")
    print(f"End-effector position (mm): {pos_test}")
    print(f"End-effector orientation (rad): {euler_test}")

    # Test inverse kinematics
    print("\n2. Inverse Kinematics Test:")
    print("-" * 40)

    # Create target pose
    target_pose = T_test.copy()

    # Solve IK
    q_solution, success = kinematics.inverse_kinematics(target_pose)

    print(f"Target position: {pos_test}")
    print(f"IK solution: {q_solution}")
    print(f"Success: {success}")

    # Verify solution
    if success:
        T_verify = kinematics.forward_kinematics(q_solution)
        pos_verify = kinematics.get_position(q_solution)
        error = np.linalg.norm(pos_verify - pos_test)
        print(f"Verification position: {pos_verify}")
        print(f"Position error: {error:.6f} mm")

    # Test Jacobian
    print("\n3. Jacobian Test:")
    print("-" * 40)
    J = kinematics.jacobian(q_test)
    print(f"Jacobian shape: {J.shape}")
    print(f"Jacobian:\n{J}")

    # Check joint limits
    print("\n4. Joint Limits Check:")
    print("-" * 40)
    valid, violations = kinematics.check_joint_limits(q_test)
    print(f"Within limits: {valid}")
    if violations:
        for v in violations:
            print(
                f"  Joint {v['joint']}: {v['value']:.2f} rad "
                f"(limits: [{v['min']:.2f}, {v['max']:.2f}])"
            )

    print("\n" + "=" * 60)
    print("Kinematics test completed!")
    print("=" * 60)
