#!/usr/bin/env python3
"""
Двусторонняя синхронизация MuJoCo ↔ ST3215 + Инструменты для обучения.
• Torque ON/OFF (клавиша T)
• Исправление оси локтя (Pitch)
• Сглаживание движений (EMA)
• Запись траектории для обучения (R - запись, S - стоп)
• Снимок с камеры (C)
"""

import msvcrt
import re
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
    print("⚠️ src.mujoco_robot_sim не найден.")


# ─── Утилита: Исправление осей (Локоть и Кисти) ──────────────────────────────
def fix_pitch_axes(xml_str: str, joint_indices: list[int]) -> str:
    """
    Меняет axis="0 0 1" на axis="0 1 0" для указанных суставов.
    Нужно, чтобы локоть (и кисти) гнулись вверх/вниз, а не вращались вокруг оси.
    """
    for idx in joint_indices:
        pattern = rf'(<joint[^>]*name="joint{idx}"[^>]*axis=")0 0 1(")'
        xml_str = re.sub(pattern, r"\g<1>0 1 0\g<2>", xml_str)
    return xml_str


# ─── Универсальный интерфейс к моторам ───────────────────────────────────────
class RobotInterface:
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

        print(
            f"{'✅' if self.connected else '⚠️'} Робот: {'Подключен' if self.connected else 'Симуляция'}"
        )

    def set_torque(self, enable: bool):
        if not self.connected:
            return
        if HAS_APP:
            for i in range(1, 7):
                self.ctrl.toggle_torque(i, enable)
        else:
            for i in range(1, 7):
                (self.direct.StartServo if enable else self.direct.StopServo)(i)

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
                return self.ctrl.read_motor_data(motor_id).get("position")
            else:
                return self.direct.ReadPosition(motor_id)
        except:
            return None


# ─── Менеджер конфигурации суставов ──────────────────────────────────────────
class JointConfig:
    def __init__(self):
        self.motor_ids = [1, 2, 3, 4, 5, 6]
        # Инверсия (поменяйте True/False если робот крутится не туда)
        self.inverted = [False, True, False, False, True, False]

        # 🔥 СМЕЩЕНИЯ (OFFSETS):
        # Важно для локтя (idx 3). Если в симуляции рука смотрит вниз,
        # а в реальности вперед, поставьте здесь -90 или 90.
        self.offset_deg = [0, 0, 0, -90, 0, 0]

        self.min_pos = [0] * 6
        self.max_pos = [4095] * 6

    def pos_to_angle(self, pos: int, idx: int) -> float:
        p = max(self.min_pos[idx], min(self.max_pos[idx], pos))
        norm = (p - self.min_pos[idx]) / (self.max_pos[idx] - self.min_pos[idx])
        ang = (norm * 360.0) - 180.0
        if self.inverted[idx]:
            ang = -ang
        return ang + self.offset_deg[idx]

    def angle_to_pos(self, ang_deg: float, idx: int) -> int:
        raw = ang_deg - self.offset_deg[idx]
        if self.inverted[idx]:
            raw = -raw
        raw = max(-180.0, min(180.0, raw))
        norm = (raw + 180.0) / 360.0
        p = self.min_pos[idx] + norm * (self.max_pos[idx] - self.min_pos[idx])
        return int(max(self.min_pos[idx], min(self.max_pos[idx], p)))


# ─── Главная программа ───────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("🤖 MuJoCo ↔ ST3215 | Sync + Training Tools")
    print("=" * 60)

    cfg = JointConfig()
    robot = RobotInterface(port="COM3")

    # 1. Загрузка и исправление модели
    try:
        if HAS_SIM:
            xml = generate_robot_mjcf(with_gripper=True, with_table=True)
        else:
            with open("assets/scene.xml", "r", encoding="utf-8") as f:
                xml = f.read()

        # 🔥 Исправляем оси для Локтя(3) и Запястий(4,5) на Pitch (0 1 0)
        xml = fix_pitch_axes(xml, joint_indices=[3, 4, 5])
        model = mujoco.MjModel.from_xml_string(xml)
    except Exception as e:
        print(f"❌ Ошибка модели: {e}")
        return

    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)

    # 2. Синхронизация стартовой позы
    print("\n📡 Чтение стартовой позы...")
    start_angles_rad = []
    for i in range(6):
        pos = robot.read_position(cfg.motor_ids[i])
        if pos is not None:
            ang_deg = cfg.pos_to_angle(pos, i)
            print(f"   J{i}: pos={pos:4d} → {ang_deg:6.1f}°")
        else:
            ang_deg = cfg.offset_deg[i]  # Fallback
            print(f"   J{i}: не прочитано → {ang_deg:6.1f}° (default)")
        start_angles_rad.append(np.deg2rad(ang_deg))

    data.qpos[:6] = start_angles_rad
    mujoco.mj_forward(model, data)

    # 3. Инициализация
    torque_on = True
    robot.set_torque(torque_on)

    # EMA фильтр для сглаживания (Torque OFF)
    ema_alpha = 0.25
    ema_pos = start_angles_rad.copy()

    # Переменные для записи траектории
    is_recording = False
    trajectory = []

    # Отдельный рендерер для камеры (чтобы не тормозить viewer)
    renderer = mujoco.Renderer(model, height=480, width=640)

    print("\n💡 Управление:")
    print("   [T] Torque ON/OFF (Синхронизация)")
    print("   [R] Начать запись траектории (Обучение)")
    print("   [S] Стоп запись и сохранить (traj.npy)")
    print("   [C] Снимок с верхней камеры (top.png)")
    print("   [Esc] Выход\n")

    # 4. Главный цикл
    with mujoco.viewer.launch_passive(model, data) as viewer:
        try:
            while viewer.is_running():
                # --- Обработка клавиш ---
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("utf-8", errors="ignore").lower()

                    if key == "t":
                        torque_on = not torque_on
                        robot.set_torque(torque_on)
                        print(
                            f"\r{' ' * 40}\r🔘 TORQUE {'ON' if torque_on else 'OFF'}",
                            end="",
                            flush=True,
                        )

                    elif key == "r":
                        is_recording = True
                        trajectory = []
                        print("\n🔴 Запись траектории...")

                    elif key == "s" and is_recording:
                        is_recording = False
                        np.save("trajectory.npy", np.array(trajectory))
                        print(f"\n✅ Сохранено {len(trajectory)} кадров в trajectory.npy")

                    elif key == "c":
                        renderer.update_scene(data, camera="top_down")
                        img = renderer.render()
                        import cv2

                        cv2.imwrite("top_view.png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                        print("\n📸 Снимок сохранен: top_view.png")

                # --- Логика синхронизации ---
                if torque_on:
                    # MuJoCo -> Robot
                    sim_angles = data.qpos[:6].copy()
                    for i in range(6):
                        pos = cfg.angle_to_pos(np.rad2deg(sim_angles[i]), i)
                        robot.move_to(cfg.motor_ids[i], pos, speed=300)
                    mujoco.mj_step(model, data)
                else:
                    # Robot -> MuJoCo
                    for i in range(6):
                        raw_pos = robot.read_position(cfg.motor_ids[i])
                        if raw_pos is not None:
                            target_ang = np.deg2rad(cfg.pos_to_angle(raw_pos, i))
                            # EMA сглаживание
                            ema_pos[i] = ema_alpha * target_ang + (1 - ema_alpha) * ema_pos[i]
                            data.qpos[i] = ema_pos[i]
                    mujoco.mj_forward(model, data)

                # --- Запись траектории ---
                if is_recording:
                    # Сохраняем углы (в градусах) и время
                    current_state = np.degrees(data.qpos[:6]).tolist()
                    trajectory.append(current_state)

                viewer.sync()
                time.sleep(0.016)  # ~60 FPS

        except KeyboardInterrupt:
            pass
        finally:
            print("\n\n🛑 Остановка...")
            robot.set_torque(False)
            if HAS_APP and robot.ctrl:
                robot.ctrl.disconnect()
            print("✅ Готово")


if __name__ == "__main__":
    main()
