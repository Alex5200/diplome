#!/usr/bin/env python3
"""
Простое зеркалирование: MuJoCo → реальный робот ST3215.
Управляйте моделью мышью в окне MuJoCo – робот будет повторять движения.
"""

import argparse
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
    parser = argparse.ArgumentParser(description="MuJoCo → Real robot mirroring")
    parser.add_argument(
        "-sim", "--simulate", action="store_true", help="Run in simulation mode without real device"
    )
    parser.add_argument("-p", "--port", default=PORT, help=f"Serial port (default: {PORT})")
    parser.add_argument(
        "-b", "--baudrate", default=BAUDRATE, type=int, help=f"Baudrate (default: {BAUDRATE})"
    )
    parser.add_argument("--no-gui", action="store_true", help="Run without GUI (compute only)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Генерируем модель робота
    xml = generate_robot_mjcf(with_gripper=True, with_table=True)
    ctrl = MuJoCoRobotController(xml)

    # Сбрасываем состояние и устанавливаем домашнюю позицию
    mujoco.mj_resetData(ctrl.model, ctrl.data)
    ctrl.data.qpos[:6] = 0.0
    mujoco.mj_forward(ctrl.model, ctrl.data)

    mirror = None
    if not args.simulate:
        # Создаём зеркало (sim → real)
        mirror = SimToRealMirror(
            ctrl,
            mode="sim_to_real",
            transport="serial",
            port=args.port,
            baudrate=args.baudrate,
            rate_hz=RATE_HZ,
            motor_speed=MOTOR_SPEED,
            safety_check=True,
            joint_offsets_deg=OFFSETS,
        )

        if not mirror.start():
            print(f"❌ Не удалось подключиться к {args.port}")
            sys.exit(1)
        print(f"\n✅ Зеркало запущено. Двигайте модель мышью – робот повторяет.")
    else:
        print("\n✅ Режим симуляции. Двигайте модель мышью для просмотра.")

    print("   Для выхода нажмите Ctrl+C\n")

    # Запуск без GUI (только расчет физики)
    if args.no_gui:
        print("⚙️  Режим без GUI (только физика)")
        print("   Текущие углы суставов выводятся каждые 1 сек\n")
        last_print = 0
        try:
            while True:
                mujoco.mj_step(ctrl.model, ctrl.data)
                if mirror:
                    sim_angles_deg = np.rad2deg(ctrl.data.qpos[:6].copy()).tolist()
                    mirror.push_sim_angles(sim_angles_deg)

                # Выводим позиции раз в секунду
                now = time.time()
                if now - last_print >= 1.0:
                    angles = np.rad2deg(ctrl.data.qpos[:6].copy())
                    print(f"Позиции: {['%.1f°' % a for a in angles]}")
                    last_print = now

                time.sleep(1.0 / RATE_HZ)
        except KeyboardInterrupt:
            print("\n⏹️ Остановка...")
        finally:
            if mirror:
                mirror.stop()
            ctrl.close()
            print("Завершено.")
    else:
        # Запускаем пассивный вьюер MuJoCo
        try:
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

                        # === Отправка углов реальному роботу (если подключен) ===
                        if mirror:
                            sim_angles_deg = np.rad2deg(ctrl.data.qpos[:6].copy()).tolist()
                            mirror.push_sim_angles(sim_angles_deg)

                        # Синхронизируем рендер
                        viewer.sync()

                except KeyboardInterrupt:
                    print("\n⏹️ Остановка...")
                finally:
                    if mirror:
                        mirror.stop()
                    viewer.close()
                    ctrl.close()
                    print("Завершено.")

        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ Ошибка запуска GUI: {e}")
            if "mjpython" in error_msg:
                print(
                    "\n  ⚠️  На macOS GUI требует mjpython, но возникла ошибка с Python библиотекой."
                )
                print("\n  Решение 1 - установите Python через brew:")
                print("     brew install python@3.12")
                print("     /Users/alexandr/.mujoco/mujoco-3.*/bin/mjpython main.py -sim")
                print("\n  Решение 2 - запустите без GUI:")
                print("     python3 main.py -sim --no-gui")
                print("\n  Решение 3 - используйте обычный Python (без GUI):")
                print("     python3 main.py -sim --no-gui")
            else:
                print("   Попробуйте запуск с флагом --no-gui")
            if mirror:
                mirror.stop()
            ctrl.close()
            sys.exit(1)


if __name__ == "__main__":
    main()
