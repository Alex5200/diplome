#!/usr/bin/env python3
"""
Обучение робота брать предметы с использованием камеры top_down.
Использует простой контроллер на основе IK (без RL).
"""

import time

import mujoco
import mujoco.viewer
import numpy as np
from mujoco_robot_sim import MuJoCoRobotController, RobotEnv, generate_robot_mjcf


class PickPlaceTrainer:
    """Тренер для задачи pick & place."""

    def __init__(self, use_camera=True):
        self.use_camera = use_camera
        self.env = RobotEnv(camera_width=640, camera_height=480)
        self.ctrl = self.env.ctrl

        # Параметры задачи
        self.pick_position = np.array([150, 50, 60])  # Где брать (мм)
        self.place_position = np.array([150, -80, 60])  # Где класть (мм)
        self.lift_height = 150  # Высота подъема (мм)

        # Состояние
        self.current_step = 0
        self.success_count = 0
        self.total_attempts = 0

        print("=" * 60)
        print("🤖 Pick & Place Trainer")
        print("=" * 60)
        print(f"\n📍 Pick position:  {self.pick_position} мм")
        print(f"📍 Place position: {self.place_position} мм")
        print(f"📍 Lift height:    {self.lift_height} мм\n")

    def get_object_position(self, object_name="red_cube") -> np.ndarray | None:
        """Получить позицию объекта из симуляции."""
        obs = self.ctrl.get_observation()
        obj_pos = obs["object_positions"].get(object_name)
        if obj_pos is not None:
            # Конвертация из метров в мм
            return np.array([obj_pos[0] * 1000, obj_pos[1] * 1000, obj_pos[2] * 1000])
        return None

    def approach_position(
        self, x_mm: float, y_mm: float, z_mm: float, grip_open: bool = True, steps: int = 50
    ) -> bool:
        """Подойти к позиции с плавным движением."""
        angles = self.ctrl.ik_solver.solve(x_mm, y_mm, z_mm, max_iterations=300, tolerance=2.0)

        if angles is None:
            print(f"  ⚠️  IK не решена для ({x_mm:.0f}, {y_mm:.0f}, {z_mm:.0f})")
            return False

        # Обрезка углов
        for i in range(6):
            lo, hi = self.ctrl.SAFE_ANGLE_LIMITS_DEG[i]
            angles[i] = max(lo, min(hi, angles[i]))

        self.ctrl.set_joint_angles(angles)

        if grip_open:
            self.ctrl.open_gripper()
        else:
            self.ctrl.close_gripper()

        # Плавное движение
        for _ in range(steps):
            mujoco.mj_step(self.ctrl.model, self.ctrl.data)

        return True

    def execute_pick_place(self) -> bool:
        """Выполнить один цикл pick & place."""
        self.total_attempts += 1

        print(f"\n🔄 Попытка #{self.total_attempts}")
        print("-" * 40)

        # 1. Подняться над объектом
        print("1. Подход к объекту...")
        if not self.approach_position(
            self.pick_position[0], self.pick_position[1], self.lift_height, grip_open=True
        ):
            return False

        # 2. Опуститься к объекту
        print("2. Опуститься к объекту...")
        if not self.approach_position(
            self.pick_position[0], self.pick_position[1], self.pick_position[2], grip_open=True
        ):
            return False

        # 3. Захватить объект
        print("3. Захват объекта...")
        self.ctrl.close_gripper()
        for _ in range(30):
            mujoco.mj_step(self.ctrl.model, self.ctrl.data)

        # 4. Поднять объект
        print("4. Подъем...")
        if not self.approach_position(
            self.pick_position[0], self.pick_position[1], self.lift_height, grip_open=False
        ):
            return False

        # 5. Переместить к точке сброса
        print("5. Перемещение к точке сброса...")
        if not self.approach_position(
            self.place_position[0], self.place_position[1], self.lift_height, grip_open=False
        ):
            return False

        # 6. Опуститься
        print("6. Опуститься...")
        if not self.approach_position(
            self.place_position[0], self.place_position[1], self.place_position[2], grip_open=False
        ):
            return False

        # 7. Отпустить объект
        print("7. Отпускание объекта...")
        self.ctrl.open_gripper()
        for _ in range(30):
            mujoco.mj_step(self.ctrl.model, self.ctrl.data)

        # 8. Вернуться в исходную позицию
        print("8. Возврат...")
        self.approach_position(150, 0, self.lift_height, grip_open=True)

        self.success_count += 1
        print(f"✅ Успешно! (Всего: {self.success_count}/{self.total_attempts})")
        return True

    def train(self, num_episodes: int = 10, viewer=None):
        """Запустить обучение."""
        print(f"\n🎯 Начало обучения: {num_episodes} эпизодов")
        print("Нажмите Ctrl+C для остановки\n")

        try:
            for episode in range(num_episodes):
                print(f"\n{'=' * 60}")
                print(f"📊 Эпизод {episode + 1}/{num_episodes}")
                print(f"{'=' * 60}")

                # Сброс
                self.env.reset()

                # Выполнение pick & place
                success = self.execute_pick_place()

                if success:
                    print(f" Эпизод {episode + 1} завершен успешно!")
                else:
                    print(f"❌ Эпизод {episode + 1} не удался")

                # Пауза между эпизодами
                time.sleep(1.0)

        except KeyboardInterrupt:
            print("\n\n⏹  Обучение прервано пользователем")

        finally:
            # Статистика
            print(f"\n{'=' * 60}")
            print("📊 Итоговая статистика:")
            print(f"{'=' * 60}")
            print(f"  Всего попыток:  {self.total_attempts}")
            print(f"  Успешных:       {self.success_count}")
            print(
                f"  Процент успеха: {self.success_count / max(1, self.total_attempts) * 100:.1f}%"
            )
            print(f"{'=' * 60}\n")

    def visualize_camera(self):
        """Показать изображение с камеры."""
        print("\n📹 Визуализация камеры top_down...")
        print("Нажмите Ctrl+C для выхода\n")

        try:
            while True:
                # Рендеринг
                rgb = self.ctrl.render_camera("top_down", depth=False)
                depth = self.ctrl.render_camera("top_down", depth=True)

                # Получение позиции EE
                ee_pos = self.ctrl.get_ee_position_mm()

                print(
                    f"\r📸 EE: ({ee_pos[0]:6.1f}, {ee_pos[1]:6.1f}, {ee_pos[2]:6.1f}) мм | "
                    f"Shape: {rgb.shape}",
                    end="",
                    flush=True,
                )

                # Здесь можно добавить сохранение изображений
                # if save_frames:
                #     from PIL import Image
                #     img = Image.fromarray(rgb)
                #     img.save(f"frame_{self.current_step:04d}.png")

                self.current_step += 1
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n✅ Визуализация завершена")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Pick & Place Trainer")
    parser.add_argument("--episodes", type=int, default=5, help="Количество эпизодов")
    parser.add_argument("--camera", action="store_true", help="Только просмотр камеры")
    parser.add_argument("--save-frames", action="store_true", help="Сохранять кадры")

    args = parser.parse_args()

    trainer = PickPlaceTrainer(use_camera=True)

    if args.camera:
        # Только просмотр камеры
        trainer.visualize_camera()
    else:
        # Обучение с viewer
        xml = generate_robot_mjcf(with_gripper=True, with_objects=True, with_table=True)
        ctrl = MuJoCoRobotController(xml)
        ctrl.set_joint_angles([0, -30, 60, -30, 0, 0], immediate=True)

        with mujoco.viewer.launch_passive(ctrl.model, ctrl.data) as viewer:
            # Запуск обучения в отдельном потоке
            import threading

            train_thread = threading.Thread(
                target=trainer.train, args=(args.episodes, viewer), daemon=True
            )
            train_thread.start()

            # Главный цикл viewer
            try:
                while train_thread.is_alive():
                    mujoco.mj_step(ctrl.model, ctrl.data)
                    viewer.sync()
                    time.sleep(0.016)
            except KeyboardInterrupt:
                pass

            train_thread.join(timeout=2.0)

    print("\n✅ Готово!")


if __name__ == "__main__":
    main()
