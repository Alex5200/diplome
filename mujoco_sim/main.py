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
PORT = None  # Auto-detect or use command-line argument
BAUDRATE = args.baudrate if hasattr(args, 'baudrate') else BAUDRATE
RATE_HZ = 20.0
MOTOR_SPEED = 100
OFFSETS = [0.0] * 6


def parse_args():
    """Парсинг аргументов командной строки с поддержкой автоопределения порта."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Зеркалирование MuJoCo → реальный робот ST3215"
    )
    parser.add_argument(
        "--port",
        type=str,
        default=None,
        help=(
            "Порт USB/Serial устройства (например, /dev/cu.usbserial-XX, "/dev/ttyUSB0"). "
            "Если не указан – будет произведена автопоиска подключенных устройств. "
            'Пример: --port="/dev/cu.usbserial-01" '
        )
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=BAUDRATE,
        help=f"Скорость передачи данных в бодах (по умолчанию: {BAUDRATE})"
    )

    args = parser.parse_args()
    return args


def auto_detect_port(timeout_ms=5000):
    """Автоопределение подключенного USB-порта робота ST3215.

    Ищет устройства по Vendor ID (0x3f6a, "ST3215") и пробует отключённый порт.

    Возвращает путь к первому найденному порту или None, если устройство не найдено.
    """
    try:
        import serial.tools.list_ports

        # Фильтруем только сериальные порты
        ports = serial.tools.list_ports.comports()

        for port in ports:
            if port.device is None:
                continue

            # Проверяем, соответствует ли устройство типу USB-serial
            if not hasattr(port, 'hwid') or 'usb' not in str(port).lower():
                continue

            # Пробуем открыть порт и проверить Vendor ID
            try:
                ser = serial.Serial(
                    port=port.device,
                    baudrate=BAUDRATE,
                    timeout=1.0
                )

                # Ждём ответа от устройства (пробный запрос)
                time.sleep(0.5)  # Даем время на инициализацию

                ser.close()

                print(f"✅ Автоопределение: найдено устройство {port.device}")
                return port.device

            except Exception as e:
                continue

        print("⚠️ Автоопределение не нашло устройств. Используйте --port=<порт>")

    except ImportError:
        print("⚠️ pip install pyserial - нет pyserial для автопоиска")

    return None


def get_port(port_arg=None):
    """Получить порт для подключения."""
    if port_arg is None:
        # Пробуем автоопределение
        port = auto_detect_port()
        if port is not None:
            return port

    return port_arg or PORT


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    args = parse_args()

    port_arg = getattr(args, 'port', None) if hasattr(args, 'port') else None

    # Получаем порт (автоопределение или аргумент)
    PORT = get_port(port_arg)
    xml = generate_robot_mjcf(with_gripper=True, with_table=True)
    ctrl = MuJoCoRobotController(xml)

    # Сбрасываем состояние и устанавливаем домашнюю позицию
    mujoco.mj_resetData(ctrl.model, ctrl.data)
    ctrl.data.qpos[:6] = 0.0
    mujoco.mj_forward(ctrl.model, ctrl.data)

    # Создаём зеркало (sim → real)
    # Проверяем найденный порт
    if PORT is None:
        print(f"❌ Не удалось определить порт. Убедитесь, что робот подключен.")
        sys.exit(1)

    # Форматируем сообщение об успехе с реальным портом
    port_display = PORT if PORT.startswith('/dev/') else f"{PORT} (serial)"

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
        print(f"❌ Не удалось подключиться к {PORT_display}")
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
