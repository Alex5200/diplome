#!/usr/bin/env python3
"""
Просмотр камеры top_down в реальном времени.
"""

import time

import mujoco
import mujoco.viewer
import numpy as np
from src.mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf


def main():
    print("=" * 60)
    print("📹 Просмотр камеры Top-Down")
    print("=" * 60)

    # Загрузка модели
    xml = generate_robot_mjcf(with_gripper=True, with_objects=True, with_table=True)
    ctrl = MuJoCoRobotController(xml, camera_width=640, camera_height=480)

    # Начальная поза
    ctrl.set_joint_angles([0, -30, 60, -30, 0, 0], immediate=True)
    ctrl.open_gripper()

    print("\n💡 Управление:")
    print("   [Space] — сделать снимок и сохранить")
    print("   [Q] — выход")
    print("   Двигайте мышь в окне MuJoCo для вращения камеры\n")

    # Запуск viewer
    with mujoco.viewer.launch_passive(ctrl.model, ctrl.data) as viewer:
        frame_count = 0

        try:
            while viewer.is_running():
                # Шаг физики
                mujoco.mj_step(ctrl.model, ctrl.data)

                # Рендеринг верхней камеры
                rgb = ctrl.render_camera("top_down", depth=False)
                depth = ctrl.render_camera("top_down", depth=True)

                # Отображение информации
                if frame_count % 30 == 0:
                    ee_pos = ctrl.get_ee_position_mm()
                    print(
                        f"\r📸 Frame {frame_count} | EE: ({ee_pos[0]:.0f}, {ee_pos[1]:.0f}, {ee_pos[2]:.0f}) мм",
                        end="",
                        flush=True,
                    )

                # Сохранение по пробелу
                if viewer.user_scn and viewer.user_scn.ngeom >= 0:
                    # Проверка нажатия клавиш через mujoco
                    pass

                viewer.sync()
                frame_count += 1
                time.sleep(0.016)

        except KeyboardInterrupt:
            pass

    print("\n✅ Завершено")


if __name__ == "__main__":
    main()
