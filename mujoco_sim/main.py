#!/usr/bin/env python3
"""
Простое зеркалирование: MuJoCo → реальный робот ST3215.
Управляйте моделью мышью в окне MuJoCo – робот будет повторять движения.
"""

import logging
import sys
import threading
import time

import mujoco
import mujoco.viewer
import numpy as np
from src.mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf
from src.mujoco_robot_sim.sim_to_real import SimToRealMirror

# Параметры по умолчанию
PORT = "COM3"
BAUDRATE = 1_000_000
RATE_HZ = 20.0
MOTOR_SPEED = 100
OFFSETS = [0.0] * 6


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Генерируем модель робота
    xml = generate_robot_mjcf(with_gripper=True, with_table=True)
    ctrl = MuJoCoRobotController(xml)

    # Сбрасываем состояние и устанавливаем домашнюю позицию
    mujoco.mj_resetData(ctrl.model, ctrl.data)
    ctrl.data.qpos[:6] = 0.0
    mujoco.mj_forward(ctrl.model, ctrl.data)

    # Создаём зеркало (sim → real)
    mirror = SimToRealMirror(
        ctrl,
        mode="sim_to_real",
        transport="serial",
        port=PORT,
        baudrate=BAUDRATE,
        rate_hz=RATE_HZ,
        motor_speed=MOTOR_SPEED,
        safety_check=True,
        joint_offsets_deg=OFFSETS,
    )

    if not mirror.start():
        print(f"❌ Не удалось подключиться к {PORT}")
        sys.exit(1)

    print("\n✅ Зеркало запущено. Двигайте модель мышью – робот повторяет.")
    print("   Для выхода нажмите Ctrl+C\n")

    # Запускаем пассивный вьюер MuJoCo
    with mujoco.viewer.launch_passive(ctrl.model, ctrl.data) as viewer:
        running = True

        try:
            while running and viewer.is_running():
                # === Безопасное обновление симуляции под блокировкой ===
                with viewer.lock():
                    # Шаг физики
                    mujoco.mj_step(ctrl.model, ctrl.data)

                    # Если стек не пуст – сбрасываем данные (на всякий случай)
                    if ctrl.data.stackuse != 0:
                        logging.warning("⚠️ stackuse не 0, сброс данных")
                        mujoco.mj_resetData(ctrl.model, ctrl.data)
                        ctrl.data.qpos[:6] = 0.0
                        mujoco.mj_forward(ctrl.model, ctrl.data)

                # === Отправка углов реальному роботу (вне блокировки) ===
                # Читаем текущие углы из симуляции
                sim_angles_deg = np.rad2deg(ctrl.data.qpos[:6].copy()).tolist()
                mirror.push_sim_angles(sim_angles_deg)

                # Синхронизируем рендер
                viewer.sync()

        except KeyboardInterrupt:
            print("\n⏹️ Остановка...")
        finally:
            mirror.stop()
            viewer.close()
            ctrl.close()
            print("Завершено.")


if __name__ == "__main__":
    main()
