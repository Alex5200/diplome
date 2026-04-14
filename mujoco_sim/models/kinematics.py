#!/usr/bin/env python3

"""
Kinematics Model for 6-DOF Robot Arm

Прямая и обратная кинематика для шестиосевого робота-манипулятора.

Длины звеньев (мм):
    L0 = 19   - от основания до первого сустава (база)
    L1 = 134  - от первого до второго сустава (плечо 1)
    L2 = 95   - от второго до третьего сустава (плечо 2)
    L3 = 34   - от третьего до четвертого сустава (локоть/запястье 1)
    L4 = 35   - от четвертого до пятого сустава (запястье 2)
    L5 = 0    - от пятого до шестого сустава (инструмент)
"""

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class LinkParams:
    """Параметры звена манипулятора."""

    length: float  # Длина звена (мм)
    offset: float = 0.0  # Смещение по оси Z
    twist: float = 0.0  # Угол закручивания (радианы)


@dataclass
class JointState:
    """Состояние сустава."""

    angle_deg: float  # Угол в градусах
    angle_rad: float  # Угол в радианах
    position: int  # Позиция мотора (0-4095)


class RobotKinematics6DOF:
    """
    Кинематическая модель 6-осевого робота-манипулятора.

    Использует модифицированные DH-параметры для расчета прямой кинематики.
    """

    # Длины звеньев в мм (от пользователя)
    L0: float = 19.0  # База
    L1: float = 104.0  # Плечо 1
    L2: float = 95.0  # Плечо 2
    L3: float = 34.0  # Локоть/Запястье 1
    L4: float = 35.0  # Запястье 2
    L5: float = 0.0  # Инструмент (может быть настроен)

    def __init__(self):
        """Инициализация кинематической модели."""
        # DH параметры для 6-осевого робота
        # [d (смещение), a (длина), alpha (закручивание)]
        self.dh_params = [
            (self.L0, 0.0, math.pi / 2),  # Joint 1: база вращается вокруг Z
            (0.0, self.L1, 0.0),  # Joint 2: плечо 1
            (0.0, self.L2, 0.0),  # Joint 3: плечо 2
            (0.0, self.L3, math.pi / 2),  # Joint 4: локоть/запястье 1
            (0.0, self.L4, -math.pi / 2),  # Joint 5: запястье 2
            (self.L5, 0.0, 0.0),  # Joint 6: инструмент
        ]

        # Текущие углы суставов (в градусах)
        self.joint_angles: list[float] = [0.0] * 6

    def set_joint_angles(self, angles_deg: list[float]) -> None:
        """
        Установка углов всех суставов.

        Args:
            angles_deg: Список из 6 углов в градусах
        """
        if len(angles_deg) != 6:
            raise ValueError("Ожидается 6 углов для 6-осевого робота")
        self.joint_angles = list(angles_deg)

    def set_joint_angle(self, joint_idx: int, angle_deg: float) -> None:
        """
        Установка угла конкретного сустава.

        Args:
            joint_idx: Индекс сустава (0-5)
            angle_deg: Угол в градусах
        """
        if not 0 <= joint_idx < 6:
            raise ValueError(f"Индекс сустава должен быть 1-6, получен {joint_idx}")
        self.joint_angles[joint_idx] = angle_deg

    def forward_kinematics(
        self, angles_deg: list[float] | None = None
    ) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float, float]]]:
        """
        Расчет прямой кинематики.

        Вычисляет положение и ориентацию каждого сустава в пространстве.

        Args:
            angles_deg: Опционально, список углов в градусах. Если None, используются self.joint_angles

        Returns:
            (joint_positions, joint_orientations):
                - joint_positions: Список кортежей (x, y, z) для каждого сустава
                - joint_orientations: Список кортежей (roll, pitch, yaw) для каждого сустава
        """
        if angles_deg is not None:
            self.set_joint_angles(angles_deg)

        # Конвертация в радианы
        theta = [math.radians(angle) for angle in self.joint_angles]

        # Матрицы трансформации
        positions = []
        orientations = []

        # Начальная позиция (база)
        current_transform = self._identity_matrix()

        for i in range(6):
            # DH матрица трансформации для сустава i
            T = self._dh_matrix(
                theta[i],
                self.dh_params[i][0],  # d
                self.dh_params[i][1],  # a
                self.dh_params[i][2],  # alpha
            )

            # Накопленная трансформация
            current_transform = self._matrix_multiply(current_transform, T)

            # Извлечение позиции
            x = current_transform[0][3]
            y = current_transform[1][3]
            z = current_transform[2][3]
            positions.append((x, y, z))

            # Извлечение ориентации (Euler angles ZYX)
            roll, pitch, yaw = self._extract_euler_angles(current_transform)
            orientations.append((roll, pitch, yaw))

        return positions, orientations

    def _dh_matrix(self, theta: float, d: float, a: float, alpha: float) -> list[list[float]]:
        """
        Создание DH матрицы трансформации.

        Args:
            theta: Угол сустава (радианы)
            d: Смещение по оси Z
            a: Длина звена по оси X
            alpha: Угол закручивания (радианы)

        Returns:
            Матрица 4x4 трансформации
        """
        ct = math.cos(theta)
        st = math.sin(theta)
        ca = math.cos(alpha)
        sa = math.sin(alpha)

        return [
            [ct, -st * ca, st * sa, a * ct],
            [st, ct * ca, -ct * sa, a * st],
            [0, sa, ca, d],
            [0, 0, 0, 1],
        ]

    def _identity_matrix(self) -> list[list[float]]:
        """Единичная матрица 4x4."""
        return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]

    def _matrix_multiply(self, A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
        """Умножение матриц 4x4."""
        result = [[0.0] * 4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                for k in range(4):
                    result[i][j] += A[i][k] * B[k][j]
        return result

    def _extract_euler_angles(self, T: list[list[float]]) -> tuple[float, float, float]:
        """
        Извлечение Euler углов (ZYX порядок) из матрицы трансформации.

        Returns:
            (roll, pitch, yaw) в радианах
        """
        # Извлечение из матрицы вращения 3x3
        r11, r12, r13 = T[0][0], T[0][1], T[0][2]
        r21, r22, r23 = T[1][0], T[1][1], T[1][2]
        r31, r32, r33 = T[2][0], T[2][1], T[2][2]

        # Pitch (вращение вокруг Y)
        pitch = math.atan2(-r31, math.sqrt(r11**2 + r21**2))

        # Проверка на Gimbal lock
        if abs(pitch - math.pi / 2) < 1e-6:
            # Gimbal lock вверх
            roll = 0.0
            yaw = math.atan2(r12, r22)
        elif abs(pitch + math.pi / 2) < 1e-6:
            # Gimbal lock вниз
            roll = 0.0
            yaw = math.atan2(-r12, -r22)
        else:
            roll = math.atan2(r32, r33)
            yaw = math.atan2(r21, r11)

        return roll, pitch, yaw

    def get_end_effector_position(
        self, angles_deg: list[float] | None = None
    ) -> tuple[float, float, float]:
        """
        Получение позиции конечного эффектора (инструмента).

        Args:
            angles_deg: Опционально, список углов в градусах

        Returns:
            (x, y, z) позиция в мм
        """
        positions, _ = self.forward_kinematics(angles_deg)
        return positions[-1] if positions else (0.0, 0.0, 0.0)

    def get_end_effector_orientation(
        self, angles_deg: list[float] | None = None
    ) -> tuple[float, float, float] | tuple[float, float, float, float]:
        """
        Получение ориентации конечного эффектора.

        Args:
            angles_deg: Опционально, список углов в градусах

        Returns:
            (roll, pitch, yaw) в радианах
        """
        _, orientations = self.forward_kinematics(angles_deg)
        return orientations[-1] if orientations else (0.0, 0.0, 0.0)

    def get_all_joint_positions(
        self, angles_deg: list[float] | None = None
    ) -> list[tuple[float, float, float]]:
        """
        Получение позиций всех суставов.

        Args:
            angles_deg: Опционально, список углов в градусах

        Returns:
            Список (x, y, z) позиций для каждого сустава
        """
        positions, _ = self.forward_kinematics(angles_deg)
        # Добавляем базу (0, 0, 0) в начало
        return [(0.0, 0.0, 0.0)] + positions

    def get_link_vectors(
        self, angles_deg: list[float] | None = None
    ) -> list[tuple[float, float, float]]:
        """
        Получение векторов каждого звена.

        Args:
            angles_deg: Опционально, список углов в градусах

        Returns:
            Список векторов (dx, dy, dz) для каждого звена
        """
        positions = self.get_all_joint_positions(angles_deg)
        vectors = []

        for i in range(1, len(positions)):
            dx = positions[i][0] - positions[i - 1][0]
            dy = positions[i][1] - positions[i - 1][1]
            dz = positions[i][2] - positions[i - 1][2]
            vectors.append((dx, dy, dz))

        return vectors

    def get_total_reach(self) -> float:
        """
        Расчет максимальной досягаемости робота.

        Returns:
            Максимальная длина (мм)
        """
        return self.L0 + self.L1 + self.L2 + self.L3 + self.L4 + self.L5

    def get_workspace_bounds(self) -> tuple[float, float, float, float, float, float]:
        """
        Расчет границ рабочей зоны.

        Returns:
            (x_min, x_max, y_min, y_max, z_min, z_max) в мм
        """
        max_reach = self.get_total_reach()
        return (-max_reach, max_reach, -max_reach, max_reach, 0, max_reach + self.L0)

    @staticmethod
    def position_to_motor_angle(position: int) -> float:
        """
        Конвертация позиции мотора (0-4095) в угол (градусы).

        Args:
            position: Позиция мотора (0-4095)

        Returns:
            Угол в градусах (-180 до +180)
        """
        position = max(0, min(4095, position))
        return (position / 4095.0) * 360.0 - 180.0

    @staticmethod
    def angle_to_motor_position(angle_deg: float) -> int:
        """
        Конвертация угла (градусы) в позицию мотора (0-4095).

        Args:
            angle_deg: Угол в градусах (-180 до +180)

        Returns:
            Позиция мотора (0-4095)
        """
        position = int((angle_deg + 180.0) / 360.0 * 4095.0)
        return max(0, min(4095, position))


class InverseKinematics6DOF:
    """
    Обратная кинематика для 6-осевого робота.

    Использует гибридный метод: аналитическое начальное приближение +
    численная оптимизация (Jacobian-based).
    """

    def __init__(self, kinematics: RobotKinematics6DOF):
        """
        Инициализация обратной кинематики.

        Args:
            kinematics: Объект прямой кинематики
        """
        self.kinematics = kinematics
        # Длины звеньев
        self.L0 = kinematics.L0
        self.L1 = kinematics.L1
        self.L2 = kinematics.L2
        self.L3 = kinematics.L3
        self.L4 = kinematics.L4
        self.L5 = kinematics.L5

    def solve(
        self,
        x: float,
        y: float,
        z: float,
        roll: float = 0.0,
        pitch: float = 0.0,
        yaw: float = 0.0,
        max_iterations: int = 300,
        tolerance: float = 1.0,
    ) -> list[float] | None:
        """
        Решение обратной кинематики с множественными начальными приближениями.

        1. Проверка досягаемости
        2. Множество начальных приближений (сетка по J1, J2)
        3. Численная оптимизация с якобианом для каждого
        4. Возврат лучшего решения

        Args:
            x, y, z: Целевая позиция в мм
            roll, pitch, yaw: Целевая ориентация в радианах
            max_iterations: Максимум итераций
            tolerance: Допуск сходимости (мм)

        Returns:
            Список из 6 углов в градусах или None если не найдено решение
        """
        # Проверка досягаемости
        dist = math.sqrt(x**2 + y**2 + z**2)
        max_reach = self.kinematics.get_total_reach()
        if dist > max_reach * 1.02:
            return None  # Точно недостижимо

        # Генерируем множество начальных приближений
        initial_guesses = self._generate_initial_guesses(x, y, z)

        best_angles = None
        best_score = float("inf")

        for guess in initial_guesses:
            angles = self._numerical_solve(x, y, z, guess, max_iterations, tolerance)
            if angles:
                pos = self.kinematics.get_end_effector_position(angles)
                error = math.sqrt((pos[0] - x) ** 2 + (pos[1] - y) ** 2 + (pos[2] - z) ** 2)

                # Штраф за подход снизу (elbow-down):
                # Elbow-up: J2 > 0, J3 < 0 → робот нависает сверху (предпочтительно)
                # Elbow-down: J2 < 0, J3 > 0 → робот подходит снизу (штраф)
                elbow_penalty = 0.0
                if angles[1] < 0:  # J2 отрицательный = плечо опущено
                    elbow_penalty += abs(angles[1]) * 2.0
                if angles[2] > 0:  # J3 положительный = предплечье поднято снизу
                    elbow_penalty += abs(angles[2]) * 2.0

                # Итоговый score: ошибка позиции + штраф за конфигурацию
                score = error + elbow_penalty

                if error < tolerance:
                    if score < best_score:
                        best_score = score
                        best_angles = angles
                elif best_angles is None or error < (
                    best_score - elbow_penalty if best_score != float("inf") else float("inf")
                ):
                    # Если ещё нет хорошего решения, берём хоть что-то
                    if error + elbow_penalty < best_score:
                        best_score = error + elbow_penalty
                        best_angles = angles

        return best_angles

    def _generate_initial_guesses(self, x: float, y: float, z: float) -> list[list[float]]:
        """
        Генерация начальных приближений для IK.

        Приоритет: подход СВЕРХУ ВНИЗ (elbow-up).
        J2 положительный = плечо поднято вверх.
        J3 отрицательный = предплечье опущено вниз.
        Это даёт конфигурацию, когда робот «нависает» над целью.
        """
        guesses = []

        # J1 — всегда направлен на целевую точку
        if abs(x) > 1 or abs(y) > 1:
            j1_base = math.degrees(math.atan2(y, x))
        else:
            j1_base = 0.0

        # Горизонтальное расстояние и высота для эвристики
        r_horiz = math.sqrt(x**2 + y**2)
        h = z - self.L0  # высота над базой

        # --- Приоритетные конфигурации: подход СВЕРХУ (elbow-up) ---
        # J2>0 поднимает плечо, J3<0 опускает предплечье — робот нависает
        top_down_configs = [
            (60, -90),  # сильно поднят, предплечье вертикально вниз
            (45, -60),  # классический подход сверху
            (30, -45),  # умеренный подход сверху
            (50, -80),  # высокий подход
            (70, -110),  # почти вертикальный
            (40, -50),  # средний
            (20, -30),  # слабый подъём
            (80, -120),  # максимальный подъём
            (35, -70),  # вариация
            (55, -95),  # вариация
        ]

        for j2, j3 in top_down_configs:
            j4 = -(j2 + j3)  # компенсация для горизонтального инструмента
            guesses.append([j1_base, j2, j3, j4, 0, 0])

        # --- Эвристика на основе геометрии цели ---
        # Аналитическое приближение для плоского 2-звенного робота (J2, J3)
        L1 = self.L1
        L2 = self.L2 + self.L3 + self.L4  # эффективная длина руки
        target_r = math.sqrt(r_horiz**2 + h**2)

        if target_r < L1 + L2:
            cos_j3 = (target_r**2 - L1**2 - L2**2) / (2 * L1 * L2)
            cos_j3 = max(-1, min(1, cos_j3))

            # Elbow-up (подход сверху): J3 отрицательный
            j3_up = -math.degrees(math.acos(cos_j3))
            alpha = math.degrees(math.atan2(h, r_horiz))
            beta = math.degrees(
                math.atan2(
                    L2 * math.sin(math.radians(-j3_up)),
                    L1 + L2 * math.cos(math.radians(-j3_up)),
                )
            )
            j2_up = alpha + beta

            j4_up = -(j2_up + j3_up)
            guesses.insert(0, [j1_base, j2_up, j3_up, j4_up, 0, 0])

            # Elbow-down (запасной): J3 положительный
            j3_dn = math.degrees(math.acos(cos_j3))
            beta_dn = math.degrees(
                math.atan2(
                    L2 * math.sin(math.radians(j3_dn)),
                    L1 + L2 * math.cos(math.radians(j3_dn)),
                )
            )
            j2_dn = alpha - beta_dn
            j4_dn = -(j2_dn + j3_dn)
            guesses.append([j1_base, j2_dn, j3_dn, j4_dn, 0, 0])

        # --- Резервные: вытянутые/нулевые ---
        guesses.append([j1_base, 0, 0, 0, 0, 0])
        guesses.append([j1_base, 10, -20, 10, 0, 0])

        return guesses

    def _numerical_solve(
        self,
        x: float,
        y: float,
        z: float,
        initial_angles: list[float],
        max_iterations: int,
        tolerance: float,
    ) -> list[float] | None:
        """
        Численное решение методом Damped Least Squares (Levenberg-Marquardt).

        Якобиан вычисляется в единицах мм/градус, delta_theta получается
        сразу в градусах — дополнительная конвертация НЕ нужна.
        """
        angles = list(initial_angles)
        damping = 1.0  # Демпфирование для устойчивости

        for iteration in range(max_iterations):
            current_pos = self.kinematics.get_end_effector_position(angles)
            error = np.array([x - current_pos[0], y - current_pos[1], z - current_pos[2]])
            error_norm = np.linalg.norm(error)

            if error_norm < tolerance:
                return angles

            # Адаптивный шаг: крупный вдали, мелкий вблизи
            step = min(1.0, 5.0 / max(error_norm, 0.1))

            # Якобиан (мм/градус)
            J = self._compute_jacobian(angles)

            # Damped Least Squares: delta = J^T (J J^T + λ²I)^{-1} error
            JJT = J @ J.T
            damped = JJT + (damping**2) * np.eye(3)
            try:
                delta_theta = J.T @ np.linalg.solve(damped, error)
            except np.linalg.LinAlgError:
                delta_theta = J.T @ error * 0.001

            # Ограничение шага (не больше 10° за итерацию)
            max_step = 10.0
            dt_norm = np.linalg.norm(delta_theta)
            if dt_norm > max_step:
                delta_theta = delta_theta * (max_step / dt_norm)

            # Обновление (delta_theta уже в градусах!)
            for i in range(6):
                angles[i] += delta_theta[i] * step
                angles[i] = max(-179, min(179, angles[i]))

        # Проверка финальной ошибки
        final_pos = self.kinematics.get_end_effector_position(angles)
        final_error = math.sqrt(
            (final_pos[0] - x) ** 2 + (final_pos[1] - y) ** 2 + (final_pos[2] - z) ** 2
        )

        if final_error < tolerance * 3:
            return angles
        return None

    def _compute_jacobian(self, angles: list[float], delta: float = 0.5) -> np.ndarray:
        """
        Численное вычисление якобиана 3x6 (мм/градус).

        delta в градусах → J[i,j] = d(pos_i мм) / d(theta_j градус)
        """
        J = np.zeros((3, 6))

        for j in range(6):
            angles_plus = list(angles)
            angles_minus = list(angles)
            angles_plus[j] += delta
            angles_minus[j] -= delta

            pos_plus = np.array(self.kinematics.get_end_effector_position(angles_plus))
            pos_minus = np.array(self.kinematics.get_end_effector_position(angles_minus))

            J[:, j] = (pos_plus - pos_minus) / (2 * delta)

        return J


def test_kinematics():
    """Тестирование кинематической модели."""
    print("=" * 60)
    print("Тест кинематики 6-осевого робота")
    print("=" * 60)

    kin = RobotKinematics6DOF()

    print("\nДлины звеньев (мм):")
    print(f"  L0 (База) = {kin.L0}")
    print(f"  L1 (Плечо 1) = {kin.L1}")
    print(f"  L2 (Плечо 2) = {kin.L2}")
    print(f"  L3 (Локоть) = {kin.L3}")
    print(f"  L4 (Запястье 1) = {kin.L4}")
    print(f"  L5 (Запястье 2) = {kin.L5}")
    print(f"\nМаксимальная досягаемость: {kin.get_total_reach():.1f} мм")

    # Тест 1: Нулевые углы
    print("\n" + "-" * 40)
    print("Тест 1: Нулевые углы (все суставы = 0°)")
    print("-" * 40)
    positions, orientations = kin.forward_kinematics([0, 0, 0, 0, 0, 0])

    print("\nПозиции суставов:")
    print("  База:     (0.0, 0.0, 0.0)")
    for i, (pos, orient) in enumerate(zip(positions, orientations)):
        print(f"  J{i + 1}:     ({pos[0]:6.1f}, {pos[1]:6.1f}, {pos[2]:6.1f}) мм")

    end_pos = kin.get_end_effector_position()
    print(f"\nПозиция инструмента: ({end_pos[0]:.1f}, {end_pos[1]:.1f}, {end_pos[2]:.1f}) мм")

    # Тест 2: Различные углы
    print("\n" + "-" * 40)
    print("Тест 2: Различные углы")
    print("-" * 40)
    test_angles = [30, -45, 60, -30, 45, 0]
    print(f"Углы: {test_angles}°")

    positions, orientations = kin.forward_kinematics(test_angles)

    print("\nПозиции суставов:")
    print("  База:     (0.0, 0.0, 0.0)")
    for i, (pos, orient) in enumerate(zip(positions, orientations)):
        roll, pitch, yaw = (
            math.degrees(orient[0]),
            math.degrees(orient[1]),
            math.degrees(orient[2]),
        )
        print(
            f"  J{i + 1}:     ({pos[0]:6.1f}, {pos[1]:6.1f}, {pos[2]:6.1f}) мм  [R={roll:5.1f}°, P={pitch:5.1f}°, Y={yaw:5.1f}°]"
        )

    end_pos = kin.get_end_effector_position(test_angles)
    print(f"\nПозиция инструмента: ({end_pos[0]:.1f}, {end_pos[1]:.1f}, {end_pos[2]:.1f}) мм")

    # Тест 3: Конвертация позиций
    print("\n" + "-" * 40)
    print("Тест 3: Конвертация позиция <-> угол")
    print("-" * 40)
    test_positions = [0, 1024, 2048, 3072, 4095]
    for pos in test_positions:
        angle = RobotKinematics6DOF.position_to_motor_angle(pos)
        back_to_pos = RobotKinematics6DOF.angle_to_motor_position(angle)
        print(f"  {pos} -> {angle:6.1f}° -> {back_to_pos}")

    print("\n" + "=" * 60)
    print("Тест завершен успешно!")
    print("=" * 60)


if __name__ == "__main__":
    test_kinematics()
