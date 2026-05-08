#!/usr/bin/env python3
"""
Двусторонняя синхронизация MuJoCo ↔ ST3215.
• Torque ON:  Перетаскивание в MuJoCo двигает реального робота.
• Torque OFF: Робот свободен, ручное движение отображается в MuJoCo.
Переключение режима: клавиша 'T' в консоли или фокусе окна.
"""

# import msvcrt  # Windows-only, для неблокирующего чтения клавиш
import sys
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

# ─── Попытка импорта ваших модулей ───────────────────────────────────────────
try:
    from config.constants import CONFIG_FILE, MAX_POSITION, MIN_POSITION
    from controllers.motor_controller import MotorController

    HAS_APP = True
except ImportError:
    HAS_APP = False
    MAX_POSITION = 4095
    MIN_POSITION = 0
    CONFIG_FILE = "robot_config.json"

try:
    from src.mujoco_robot_sim import generate_robot_mjcf

    HAS_SIM = True
except ImportError:
    HAS_SIM = False
    print("⚠️ src.mujoco_robot_sim не найден. Укажите путь к XML вручную.")


# ─── Универсальный интерфейс к моторам ───────────────────────────────────────
class RobotInterface:
    """Абстракция над MotorController и прямой st3215 библиотекой."""

    def __init__(self, port="COM3", baudrate=1_000_000):
        self.port = port
        self.ctrl = None
        self.direct = None
        self.connected = False

        if HAS_APP:
            self.ctrl = MotorController(device=port)
            if Path(CONFIG_FILE).exists():
                self.ctrl.load_config(CONFIG_FILE)
            self.connected = self.ctrl.connect()
        else:
            try:
                from st3215 import ST3215

                self.direct = ST3215(device=port)
                self.connected = True
            except Exception as e:
                print(f"⚠️ Не удалось подключиться: {e}")

        if self.connected:
            print(f"✅ Подключено к {port}")
        else:
            print("⚠️ Работа в режиме СИМУЛЯЦИИ (нет связи с моторами)")

    def set_torque(self, enable: bool):
        if not self.connected:
            return
        if HAS_APP:
            for i in range(1, 7):
                self.ctrl.toggle_torque(i, enable)
        else:
            for i in range(1, 7):
                if enable:
                    self.direct.StartServo(i)
                else:
                    self.direct.StopServo(i)

    def move_to(self, motor_id: int, pos: int, speed: int = 300):
        if not self.connected:
            return
        safe_pos = max(0, min(4095, int(pos)))
        if HAS_APP:
            self.ctrl.move_motor(motor_id, safe_pos, speed=speed)
        else:
            try:
                self.direct.MoveTo(motor_id, safe_pos, speed=speed, acc=50)
            except:
                pass

    def read_position(self, motor_id: int) -> int | None:
        if not self.connected:
            return None
        try:
            if HAS_APP:
                data = self.ctrl.read_motor_data(motor_id)
                return data.get("position")
            else:
                return self.direct.ReadPosition(motor_id)
        except:
            return None


# ─── Менеджер конфигурации суставов ──────────────────────────────────────────
class JointConfig:
    def __init__(self):
        # Настройки по умолчанию (можно менять под вашу кинематику)
        self.motor_ids = [1, 2, 3, 4, 5, 6]
        self.inverted = [False, True, False, False, True, False]
        self.min_pos = [0] * 6
        self.max_pos = [4095] * 6

    def pos_to_angle(self, pos: int, idx: int) -> float:
        p = max(self.min_pos[idx], min(self.max_pos[idx], pos))
        norm = (p - self.min_pos[idx]) / (self.max_pos[idx] - self.min_pos[idx])
        ang = (norm * 360.0) - 180.0
        return -ang if self.inverted[idx] else ang

    def angle_to_pos(self, ang_deg: float, idx: int) -> int:
        if self.inverted[idx]:
            ang_deg = -ang_deg
        ang_deg = max(-180.0, min(180.0, ang_deg))
        norm = (ang_deg + 180.0) / 360.0
        p = self.min_pos[idx] + norm * (self.max_pos[idx] - self.min_pos[idx])
        return int(max(self.min_pos[idx], min(self.max_pos[idx], p)))


# ─── Главная программа ───────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("🤖 MuJoCo ↔ ST3215 Bidirectional Sync")
    print("=" * 60)

    cfg = JointConfig()
    robot = RobotInterface(port="COM3")

    # Загрузка модели
    if HAS_SIM:
        xml = generate_robot_mjcf(with_gripper=True, with_table=True)
        model = mujoco.MjModel.from_xml_string(xml)
    else:
        model = mujoco.MjModel.from_xml_path("assets/scene.xml")

    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)
    mujoco.mj_forward(model, data)

    # Начальное состояние
    torque_on = True
    robot.set_torque(torque_on)
    print("\n💡 Управление:")
    print("   [T] Переключить Torque ON/OFF")
    print("   Torque ON  → Двигайте мышкой в MuJoCo")
    print("   Torque OFF → Двигайте реального робота руками")
    print("   [Esc]      → Выход\n")

    # Главный цикл
    with mujoco.viewer.launch_passive(model, data) as viewer:
        try:
            while viewer.is_running():
                # 1. Обработка клавиши T
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                    if key == "t":
                        torque_on = not torque_on
                        robot.set_torque(torque_on)
                        mode = "MuJoCo → Robot" if torque_on else "Robot → MuJoCo"
                        print(f"\n🔘 TORQUE {'ON' if torque_on else 'OFF'} | {mode}")

                # 2. Синхронизация
                if torque_on:
                    # === MuJoCo управляет реальным роботом ===
                    for i in range(6):
                        ang_rad = data.qpos[i]
                        pos = cfg.angle_to_pos(np.rad2deg(ang_rad), i)
                        robot.move_to(cfg.motor_ids[i], pos, speed=300)
                    mujoco.mj_step(model, data)  # Физика
                else:
                    # === Реальный робот управляет MuJoCo ===
                    for i in range(6):
                        pos = robot.read_position(cfg.motor_ids[i])
                        if pos is not None:
                            ang_rad = np.deg2rad(cfg.pos_to_angle(pos, i))
                            data.qpos[i] = ang_rad
                    mujoco.mj_forward(model, data)  # Обновление кинематики/рендера

                # 3. Рендер
                viewer.sync()
                time.sleep(0.016)  # ~60 FPS

        except KeyboardInterrupt:
            pass
        finally:
            print("\n🛑 Остановка...")
            robot.set_torque(False)
            if HAS_APP and robot.ctrl:
                robot.ctrl.disconnect()
            print("✅ Готово")


if __name__ == "__main__":
    main()
