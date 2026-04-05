#!/usr/bin/env python3
import math
from app.models.kinematics import RobotKinematics6DOF, InverseKinematics6DOF

k = RobotKinematics6DOF()
ik = InverseKinematics6DOF(k)

# Точки которые мы знаем что достижимы (из прямой кинематики)
test_points = [
    (267.3, 0, -0.5, [0, -30, 60, -30, 0, 0]),
    (230.9, 0, -8.6, [0, -45, 90, -45, 0, 0]),
    (284.2, 0, 5.7, [0, -20, 40, -20, 0, 0]),
    (298, 0, 19, [0, 0, 0, 0, 0, 0]),
    (100, 0, 150, None),  # Сложная точка
    (150, 0, 100, None),  # Сложная точка
]

print('Тест IK:')
for x, y, z, expected_angles in test_points:
    angles = ik.solve(x, y, z, max_iterations=300, tolerance=0.5)
    if angles:
        pos = k.get_end_effector_position(angles)
        dx = pos[0] - x
        dy = pos[1] - y
        dz = pos[2] - z
        error = math.sqrt(dx*dx + dy*dy + dz*dz)
        print(f'({x:6.1f}, {y:6.1f}, {z:6.1f}): IK={[round(a,1) for a in angles]}')
        print(f'  -> pos={pos}, error={error:.2f}')
    else:
        print(f'({x:6.1f}, {y:6.1f}, {z:6.1f}): IK=None')
