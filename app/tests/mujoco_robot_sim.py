#!/usr/bin/env python3

"""
MuJoCo Robot Simulation with ST3215 Control

Полная симуляция 6-DOF робота-манипулятора в MuJoCo с:
- Точная MJCF модель по DH-параметрам (L0=19, L1=104, L2=95, L3=34, L4=35 мм)
- Двухпальцевый гриппер
- Объекты для захвата (кубики, цилиндры)
- Стол как рабочая зона
- Камеры: фиксированная сверху + камера на гриппере (eye-in-hand)
- Управление: IK к точке / waypoints / ручные углы
- Рендеринг RGB + Depth для RL-обучения
- Синхронизация с реальными моторами ST3215 (опционально)

Использование:
    python -m app.tests.mujoco_robot_sim
    python -m app.tests.mujoco_robot_sim --headless
"""

from __future__ import annotations

import logging
import math
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

# Добавляем корень проекта в sys.path
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

try:
    import mujoco
    import mujoco.viewer
except ImportError:
    sys.exit("MuJoCo не установлен. Запустите: uv pip install mujoco")

from app.config.constants import (
    DEFAULT_ACC,
    DEFAULT_MOTOR_MAPPING,
    MAX_POSITION,
)
from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF

if TYPE_CHECKING:
    from collections.abc import Sequence

# Опциональный импорт ST3215
try:
    from st3215 import ST3215

    ST3215_AVAILABLE = True
except ImportError:
    ST3215_AVAILABLE = False

# ============================================================
# Logging
# ============================================================

logger = logging.getLogger(__name__)

# ============================================================
# Constants — из kinematics.py (единый источник истины)
# ============================================================

# Длины звеньев в МЕТРАХ (MuJoCo стандарт), синхронизированы с kinematics.py
_LINK_LENGTHS_M = {
    "L0": RobotKinematics6DOF.L0 / 1000.0,  # База
    "L1": RobotKinematics6DOF.L1 / 1000.0,  # Плечо 1
    "L2": RobotKinematics6DOF.L2 / 1000.0,  # Плечо 2
    "L3": RobotKinematics6DOF.L3 / 1000.0,  # Локоть
    "L4": RobotKinematics6DOF.L4 / 1000.0,  # Кисть 1
    "L5": RobotKinematics6DOF.L5 / 1000.0,  # Инструмент
}

# Геометрия окружения
_TABLE_HEIGHT_M = 0.05
_TABLE_SIZE_M = 0.3

# Камеры
_DEFAULT_CAMERA_WIDTH = 640
_DEFAULT_CAMERA_HEIGHT = 480

# Физика
_STEPS_PER_FRAME = 50  # частота обновления viewer

# Имена объектов для наблюдения
_OBJECT_NAMES = ["red_cube", "green_cube", "blue_cylinder", "yellow_cube"]


# ============================================================
# Генерация MJCF модели робота
# ============================================================


def generate_robot_mjcf(
    *,
    with_gripper: bool = True,
    with_objects: bool = True,
    with_table: bool = True,
    with_cameras: bool = True,
) -> str:
    """
    Генерация XML-модели робота в формате MJCF.

    Модель строится по DH-параметрам кинематики:
    - J1: База — вращение вокруг Z, высота L0=19мм
    - J2: Плечо 1 — вращение вокруг Y, длина L1=104мм (из kinematics.py)
    - J3: Плечо 2 — вращение вокруг Y, длина L2=95мм
    - J4: Локоть  — вращение вокруг Y + twist, длина L3=34мм
    - J5: Кисть 1 — вращение вокруг Z, длина L4=35мм
    - J6: Кисть 2 — вращение вокруг Y

    Все размеры в метрах (MuJoCo стандарт).
    """
    L = _LINK_LENGTHS_M
    table_h = _TABLE_HEIGHT_M
    table_size = _TABLE_SIZE_M

    # Радиусы звеньев для визуализации (пропорциональны)
    r_base = 0.025
    r_link1 = 0.015
    r_link2 = 0.012
    r_link3 = 0.010
    r_link4 = 0.008

    # --- Гриппер ---
    gripper_xml = ""
    if with_gripper:
        gripper_xml = f"""
        <!-- Гриппер (двухпальцевый) -->
        <body name="gripper_base" pos="0 0 0.01">
          <geom name="gripper_mount" type="cylinder" size="{r_link4} 0.005"
                rgba="0.3 0.3 0.3 1" mass="0.005"/>

          <!-- Левый палец -->
          <body name="finger_left" pos="0 0.01 0.005">
            <joint name="finger_left_joint" type="slide" axis="0 1 0"
                   range="0 0.02" damping="0.5" stiffness="5"/>
            <geom name="finger_left_geom" type="box" size="0.005 0.003 0.02"
                  pos="0 0 0.02" rgba="0.8 0.2 0.2 1" mass="0.003"
                  friction="2 0.5 0.01" condim="4"/>
          </body>

          <!-- Правый палец -->
          <body name="finger_right" pos="0 -0.01 0.005">
            <joint name="finger_right_joint" type="slide" axis="0 -1 0"
                   range="0 0.02" damping="0.5" stiffness="5"/>
            <geom name="finger_right_geom" type="box" size="0.005 0.003 0.02"
                  pos="0 0 0.02" rgba="0.8 0.2 0.2 1" mass="0.003"
                  friction="2 0.5 0.01" condim="4"/>
          </body>
        </body>
"""

    # --- Камеры ---
    cameras_xml = ""
    eye_in_hand_xml = ""
    if with_cameras:
        cameras_xml = """
    <!-- Камеры -->
    <camera name="top_down" pos="0 0 0.6" quat="1 0 0 0"
            fovy="60" mode="fixed"/>
    <camera name="front" pos="0.5 0 0.2" xyaxes="0 1 0 0 0 1"
            fovy="60" mode="fixed"/>
    <camera name="side" pos="0 0.5 0.2" xyaxes="-1 0 0 0 0 1"
            fovy="60" mode="fixed"/>
"""
        eye_in_hand_xml = """
        <!-- Камера на гриппере (eye-in-hand) -->
        <camera name="eye_in_hand" pos="0 0 0.03"
                xyaxes="0 -1 0 1 0 0"
                fovy="90"/>
"""

    # --- Объекты ---
    objects_xml = ""
    if with_objects:
        objects_xml = f"""
    <!-- Объекты для захвата -->
    <body name="red_cube" pos="0.15 0.05 {table_h + 0.015}">
      <freejoint name="red_cube_joint"/>
      <geom name="red_cube_geom" type="box" size="0.015 0.015 0.015"
            rgba="1 0.2 0.2 1" mass="0.01"
            friction="1 0.5 0.01" condim="4"/>
    </body>

    <body name="green_cube" pos="0.12 -0.08 {table_h + 0.015}">
      <freejoint name="green_cube_joint"/>
      <geom name="green_cube_geom" type="box" size="0.015 0.015 0.015"
            rgba="0.2 1 0.2 1" mass="0.01"
            friction="1 0.5 0.01" condim="4"/>
    </body>

    <body name="blue_cylinder" pos="0.2 0.0 {table_h + 0.02}">
      <freejoint name="blue_cylinder_joint"/>
      <geom name="blue_cylinder_geom" type="cylinder" size="0.012 0.02"
            rgba="0.2 0.2 1 1" mass="0.008"
            friction="1 0.5 0.01" condim="4"/>
    </body>

    <body name="yellow_cube" pos="0.08 0.1 {table_h + 0.01}">
      <freejoint name="yellow_cube_joint"/>
      <geom name="yellow_cube_geom" type="box" size="0.01 0.01 0.01"
            rgba="1 1 0.2 1" mass="0.005"
            friction="1 0.5 0.01" condim="4"/>
    </body>
"""

    # --- Стол ---
    table_xml = ""
    if with_table:
        table_xml = f"""
    <!-- Стол / рабочая поверхность -->
    <body name="table" pos="0.15 0 {table_h / 2}">
      <geom name="table_geom" type="box" size="{table_size} {table_size} {table_h / 2}"
            rgba="0.6 0.5 0.4 1" friction="1 0.5 0.01" condim="4"/>
    </body>
"""

    # --- Маркер цели ---
    target_marker_xml = """
    <body name="target_marker" pos="0.15 0 0.15" mocap="true">
      <geom name="target_geom" type="sphere" size="0.01"
            rgba="1 0 1 0.5" contype="0" conaffinity="0"/>
    </body>
"""

    # --- Основная MJCF ---
    rad = math.radians
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<mujoco model="st3215_6dof_robot">
  <compiler angle="radian" autolimits="true"/>

  <option gravity="0 0 -9.81" timestep="0.002" integrator="implicitfast">
    <flag contact="enable"/>
  </option>

  <default>
    <joint damping="0.5" armature="0.01"/>
    <geom condim="3" friction="0.8 0.3 0.01"/>
    <motor ctrlrange="-3.14159 3.14159" ctrllimited="true"/>
  </default>

  <asset>
    <texture name="grid" type="2d" builtin="checker"
             rgb1="0.15 0.15 0.2" rgb2="0.2 0.2 0.25"
             width="256" height="256"/>
    <material name="grid_mat" texture="grid" texrepeat="8 8"/>
    <material name="robot_dark" rgba="0.2 0.2 0.25 1"/>
    <material name="robot_blue" rgba="0.2 0.4 0.8 1"/>
    <material name="robot_orange" rgba="0.9 0.5 0.1 1"/>
    <material name="robot_light" rgba="0.7 0.7 0.75 1"/>
  </asset>

  <worldbody>
    <!-- Пол -->
    <geom name="floor" type="plane" size="1 1 0.01" material="grid_mat"
          pos="0 0 0" conaffinity="1" condim="3"/>

    <!-- Освещение -->
    <light name="main_light" pos="0 0 1" dir="0 0 -1" diffuse="0.8 0.8 0.8"/>
    <light name="fill_light" pos="0.5 0.5 0.5" dir="-0.5 -0.5 -0.5" diffuse="0.3 0.3 0.3"/>

    {cameras_xml}
    {table_xml}
    {target_marker_xml}

    <!-- ====== РОБОТ ST3215 6-DOF ====== -->
    <body name="base_mount" pos="0 0 {table_h}">
      <geom name="base_plate" type="cylinder" size="{r_base + 0.01} 0.005"
            material="robot_dark" mass="0.5"/>

      <!-- J1: База — вращение вокруг Z, подъём L0 -->
      <body name="link0_base" pos="0 0 0.005">
        <joint name="joint_0" type="hinge" axis="0 0 1"
               range="{rad(-120)} {rad(120)}"
               damping="1.0" armature="0.02"/>
        <geom name="link0_geom" type="cylinder" size="{r_base} {L["L0"] / 2}"
              pos="0 0 {L["L0"] / 2}" material="robot_blue" mass="0.05"/>

        <!-- J2: Плечо 1 — вращение вокруг Y, длина L1 -->
        <body name="link1_shoulder" pos="0 0 {L["L0"]}">
          <joint name="joint_1" type="hinge" axis="0 1 0"
                 range="{rad(-45)} {rad(90)}"
                 damping="0.8" armature="0.02"/>
          <geom name="link1_geom" type="capsule" size="{r_link1}"
                fromto="0 0 0 {L["L1"]} 0 0" material="robot_orange" mass="0.04"/>

          <!-- J3: Плечо 2 — вращение вокруг Y, длина L2 -->
          <body name="link2_shoulder2" pos="{L["L1"]} 0 0">
            <joint name="joint_2" type="hinge" axis="0 1 0"
                   range="{rad(-90)} {rad(45)}"
                   damping="0.6" armature="0.015"/>
            <geom name="link2_geom" type="capsule" size="{r_link2}"
                  fromto="0 0 0 {L["L2"]} 0 0" material="robot_blue" mass="0.03"/>

            <!-- J4: Локоть — вращение вокруг Y, длина L3 -->
            <body name="link3_elbow" pos="{L["L2"]} 0 0">
              <joint name="joint_3" type="hinge" axis="0 1 0"
                     range="{rad(-120)} {rad(0)}"
                     damping="0.4" armature="0.01"/>
              <geom name="link3_geom" type="capsule" size="{r_link3}"
                    fromto="0 0 0 {L["L3"]} 0 0" material="robot_orange" mass="0.02"/>

              <!-- J5: Кисть 1 — вращение вокруг Z, длина L4 -->
              <body name="link4_wrist1" pos="{L["L3"]} 0 0">
                <joint name="joint_4" type="hinge" axis="0 0 1"
                       range="{rad(-90)} {rad(90)}"
                       damping="0.3" armature="0.008"/>
                <geom name="link4_geom" type="capsule" size="{r_link4}"
                      fromto="0 0 0 {L["L4"]} 0 0" material="robot_light" mass="0.015"/>

                <!-- J6: Кисть 2 — вращение вокруг Y -->
                <body name="link5_wrist2" pos="{L["L4"]} 0 0">
                  <joint name="joint_5" type="hinge" axis="0 1 0"
                         range="{rad(-90)} {rad(90)}"
                         damping="0.2" armature="0.005"/>
                  <geom name="link5_geom" type="sphere" size="{r_link4 + 0.002}"
                        material="robot_dark" mass="0.01"/>

                  <!-- End-effector site -->
                  <site name="end_effector" pos="0 0 0" size="0.005"
                        rgba="1 0 0 1"/>

                  {eye_in_hand_xml}
                  {gripper_xml}
                </body>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>

    {objects_xml}
  </worldbody>

  <!-- Актуаторы -->
  <actuator>
    <position name="act_joint_0" joint="joint_0" kp="50" ctrlrange="{rad(-120)} {rad(120)}"/>
    <position name="act_joint_1" joint="joint_1" kp="80" ctrlrange="{rad(-45)} {rad(90)}"/>
    <position name="act_joint_2" joint="joint_2" kp="60" ctrlrange="{rad(-90)} {rad(45)}"/>
    <position name="act_joint_3" joint="joint_3" kp="40" ctrlrange="{rad(-120)} {rad(0)}"/>
    <position name="act_joint_4" joint="joint_4" kp="30" ctrlrange="{rad(-90)} {rad(90)}"/>
    <position name="act_joint_5" joint="joint_5" kp="20" ctrlrange="{rad(-90)} {rad(90)}"/>
    {"<position name='act_finger_left' joint='finger_left_joint' kp='100' ctrlrange='0 0.02'/>" if with_gripper else ""}
    {"<position name='act_finger_right' joint='finger_right_joint' kp='100' ctrlrange='0 0.02'/>" if with_gripper else ""}
  </actuator>

  <!-- Сенсоры -->
  <sensor>
    <jointpos name="sens_joint_0" joint="joint_0"/>
    <jointpos name="sens_joint_1" joint="joint_1"/>
    <jointpos name="sens_joint_2" joint="joint_2"/>
    <jointpos name="sens_joint_3" joint="joint_3"/>
    <jointpos name="sens_joint_4" joint="joint_4"/>
    <jointpos name="sens_joint_5" joint="joint_5"/>
    <framepos name="sens_ee_pos" objtype="site" objname="end_effector"/>
  </sensor>
</mujoco>
"""
    return xml


# ============================================================
# Контроллер робота в MuJoCo
# ============================================================


@dataclass
class _CachedIds:
    """Кэшированные ID для быстрого доступа без mj_name2id."""

    joint_ids: list[int] = field(default_factory=list)
    joint_qpos_adr: list[int] = field(default_factory=list)
    actuator_ids: list[int] = field(default_factory=list)
    ee_site_id: int = -1
    target_mocap_id: int = -1
    object_body_ids: dict[str, int] = field(default_factory=dict)


class MuJoCoRobotController:
    """
    Управление роботом в MuJoCo симуляции.

    Функции:
    - Установка углов суставов (градусы → радианы)
    - IK к целевой точке
    - Управление гриппером (открыть/закрыть)
    - Рендеринг RGB/Depth с камерами
    - Чтение сенсоров
    - Синхронизация с реальным ST3215 (опционально)
    """

    JOINT_NAMES = [f"joint_{i}" for i in range(6)]
    ACTUATOR_NAMES = [f"act_joint_{i}" for i in range(6)]

    SAFE_ANGLE_LIMITS_DEG: list[tuple[float, float]] = [
        (-120, 120),
        (-45, 90),
        (-90, 45),
        (-120, 0),
        (-90, 90),
        (-90, 90),
    ]

    def __init__(
        self,
        xml_string: str | None = None,
        camera_width: int = _DEFAULT_CAMERA_WIDTH,
        camera_height: int = _DEFAULT_CAMERA_HEIGHT,
    ):
        """Инициализация симуляции."""
        if xml_string is None:
            xml_string = generate_robot_mjcf()

        self.model = mujoco.MjModel.from_xml_string(xml_string)
        self.data = mujoco.MjData(self.model)

        # Кинематика для IK
        self.kinematics = RobotKinematics6DOF()
        self.ik_solver = InverseKinematics6DOF(self.kinematics)

        # Кэшируем ВСЕ ID один раз (большая оптимизация)
        self._ids = self._cache_ids()

        # Гриппер
        self._has_gripper = False
        self._finger_left_id = -1
        self._finger_right_id = -1
        self._init_gripper()

        # Переиспользуемый рендерер (ключевая оптимизация для RL)
        self._renderer: mujoco.Renderer | None = None
        self._camera_width = camera_width
        self._camera_height = camera_height
        self._init_renderer()

        # Состояние
        self.target_angles_deg: list[float] = [0.0] * 6
        self.gripper_open: bool = True

        # ST3215 (опционально)
        self.st3215: ST3215 | None = None
        self.sync_with_real: bool = False

        # Инициализация
        mujoco.mj_forward(self.model, self.data)
        logger.info(
            "MuJoCo модель загружена: %d суставов, %d актуаторов, гриппер=%s",
            self.model.njnt,
            self.model.nu,
            self._has_gripper,
        )

    # ---- Инициализация ----

    def _cache_ids(self) -> _CachedIds:
        """Кэширование всех ID для быстрого доступа."""
        ids = _CachedIds()

        for i in range(6):
            jnt_name = f"joint_{i}"
            jnt_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, jnt_name)
            ids.joint_ids.append(jnt_id)
            ids.joint_qpos_adr.append(self.model.jnt_qposadr[jnt_id])

            act_name = f"act_joint_{i}"
            act_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, act_name)
            ids.actuator_ids.append(act_id)

        ids.ee_site_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")

        try:
            body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "target_marker")
            ids.target_mocap_id = self.model.body_mocapid[body_id]
        except Exception:
            ids.target_mocap_id = -1

        for name in _OBJECT_NAMES:
            try:
                body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, name)
                ids.object_body_ids[name] = body_id
            except Exception:
                pass

        return ids

    def _init_gripper(self) -> None:
        """Инициализация гриппера."""
        try:
            self._finger_left_id = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, "act_finger_left"
            )
            self._finger_right_id = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, "act_finger_right"
            )
            self._has_gripper = True
        except Exception:
            pass

    def _init_renderer(self) -> None:
        """Инициализация переиспользуемого рендерера."""
        try:
            self._renderer = mujoco.Renderer(
                self.model, height=self._camera_height, width=self._camera_width
            )
        except Exception as e:
            logger.warning("Не удалось создать рендерер: %s", e)
            self._renderer = None

    # ---- Context manager ----

    def __enter__(self) -> MuJoCoRobotController:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Освобождение ресурсов."""
        self.disconnect_real_robot()
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None

    # ============================
    # Управление суставами
    # ============================

    def set_joint_angles(self, angles_deg: Sequence[float], immediate: bool = False) -> None:
        """
        Установка целевых углов суставов.

        Args:
            angles_deg: 6 углов в градусах
            immediate: если True, сразу перемещает (без физики),
                       если False, через актуаторы (плавно)
        """
        if len(angles_deg) != 6:
            raise ValueError(f"Ожидается 6 углов, получено {len(angles_deg)}")

        self.target_angles_deg = list(angles_deg)

        for i in range(6):
            angle_rad = math.radians(angles_deg[i])
            self.data.ctrl[self._ids.actuator_ids[i]] = angle_rad

            if immediate:
                self.data.qpos[self._ids.joint_qpos_adr[i]] = angle_rad

        if immediate:
            mujoco.mj_forward(self.model, self.data)

        # Синхронизация с реальным роботом
        if self.sync_with_real and self.st3215:
            self._sync_to_real(list(angles_deg))

    def get_joint_angles(self) -> list[float]:
        """Чтение текущих углов суставов из симуляции (градусы)."""
        return [math.degrees(self.data.qpos[adr]) for adr in self._ids.joint_qpos_adr]

    def get_ee_position(self) -> tuple[float, float, float]:
        """Позиция end-effector из симуляции (метры)."""
        pos = self.data.site_xpos[self._ids.ee_site_id]
        return (pos[0], pos[1], pos[2])

    def get_ee_position_mm(self) -> tuple[float, float, float]:
        """Позиция end-effector в миллиметрах (относительно базы)."""
        pos = self.get_ee_position()
        return (
            pos[0] * 1000,
            pos[1] * 1000,
            (pos[2] - _TABLE_HEIGHT_M) * 1000,
        )

    # ============================
    # IK — движение к точке
    # ============================

    def move_to_point(
        self, x_mm: float, y_mm: float, z_mm: float, tolerance: float = 2.0
    ) -> list[float] | None:
        """
        Решение IK и отправка углов в симуляцию.

        Args:
            x_mm, y_mm, z_mm: целевая точка в мм
            tolerance: допуск IK в мм

        Returns:
            Углы в градусах или None
        """
        angles = self.ik_solver.solve(x_mm, y_mm, z_mm, max_iterations=300, tolerance=tolerance)
        if angles is None:
            logger.warning("IK не решена для (%.0f, %.0f, %.0f) мм", x_mm, y_mm, z_mm)
            return None

        # Обрезка по безопасным лимитам
        for i in range(6):
            lo, hi = self.SAFE_ANGLE_LIMITS_DEG[i]
            angles[i] = max(lo, min(hi, angles[i]))

        self.set_joint_angles(angles)
        return angles

    def set_target_marker(self, x_mm: float, y_mm: float, z_mm: float) -> None:
        """Перемещение визуального маркера цели в MuJoCo."""
        mocap_id = self._ids.target_mocap_id
        if mocap_id < 0:
            return
        self.data.mocap_pos[mocap_id] = [
            x_mm / 1000.0,
            y_mm / 1000.0,
            z_mm / 1000.0 + _TABLE_HEIGHT_M,
        ]

    # ============================
    # Гриппер
    # ============================

    def open_gripper(self) -> None:
        """Открыть гриппер."""
        if not self._has_gripper:
            return
        self.data.ctrl[self._finger_left_id] = 0.02
        self.data.ctrl[self._finger_right_id] = 0.02
        self.gripper_open = True

    def close_gripper(self) -> None:
        """Закрыть гриппер."""
        if not self._has_gripper:
            return
        self.data.ctrl[self._finger_left_id] = 0.0
        self.data.ctrl[self._finger_right_id] = 0.0
        self.gripper_open = False

    # ============================
    # Камеры и рендеринг
    # ============================

    def render_camera(
        self,
        camera_name: str = "top_down",
        width: int | None = None,
        height: int | None = None,
        depth: bool = False,
    ) -> np.ndarray:
        """
        Рендеринг изображения с указанной камеры.

        Переиспользует инициализированный рендерер (без аллокаций на каждый вызов).

        Args:
            camera_name: имя камеры
            width, height: размеры (по умолчанию из __init__)
            depth: если True, возвращает depth-карту

        Returns:
            RGB array (H, W, 3) uint8 или depth array (H, W) float32
        """
        if self._renderer is None:
            self._init_renderer()
        if self._renderer is None:
            raise RuntimeError("Рендерер не инициализирован")

        w = width or self._camera_width
        h = height or self._camera_height

        # Если запрошен другой размер — пересоздаём рендерер
        if w != self._camera_width or h != self._camera_height:
            self._renderer.close()
            self._renderer = mujoco.Renderer(self.model, height=h, width=w)
            self._camera_width = w
            self._camera_height = h

        self._renderer.update_scene(self.data, camera=camera_name)

        if depth:
            self._renderer.enable_depth_rendering()
            try:
                return self._renderer.render()
            finally:
                self._renderer.disable_depth_rendering()

        return self._renderer.render()

    def get_observation(self, camera_name: str = "eye_in_hand") -> dict[str, Any]:
        """
        Полное наблюдение для RL-агента.

        Returns:
            {
                'rgb': np.ndarray (H, W, 3),
                'depth': np.ndarray (H, W),
                'joint_angles': np.ndarray (6,),
                'ee_pos': np.ndarray (3,),
                'gripper_open': bool,
                'object_positions': dict
            }
        """
        rgb = self.render_camera(camera_name, depth=False)
        depth = self.render_camera(camera_name, depth=True)
        angles = np.array(self.get_joint_angles())
        ee = np.array(self.get_ee_position())

        # Позиции объектов (кэшированные ID)
        obj_positions = {}
        for name in _OBJECT_NAMES:
            body_id = self._ids.object_body_ids.get(name)
            if body_id is not None:
                obj_positions[name] = self.data.xpos[body_id].copy()

        return {
            "rgb": rgb,
            "depth": depth,
            "joint_angles": angles,
            "ee_pos": ee,
            "gripper_open": self.gripper_open,
            "object_positions": obj_positions,
        }

    # ============================
    # Физическая симуляция
    # ============================

    def step(self, n_steps: int = 1) -> None:
        """Шаг физической симуляции."""
        for _ in range(n_steps):
            mujoco.mj_step(self.model, self.data)

    def step_seconds(self, seconds: float) -> None:
        """Симулировать указанное количество секунд."""
        n = max(1, int(seconds / self.model.opt.timestep))
        self.step(n)

    def reset(self) -> None:
        """Сброс симуляции."""
        mujoco.mj_resetData(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)
        self.target_angles_deg = [0.0] * 6
        self.gripper_open = True

    # ============================
    # Синхронизация с ST3215
    # ============================

    def connect_real_robot(self, port: str = "COM3") -> bool:
        """Подключение к реальному роботу ST3215."""
        if not ST3215_AVAILABLE:
            logger.error("st3215 не установлен")
            return False
        try:
            self.st3215 = ST3215(device=port)
            self.sync_with_real = True
            logger.info("Подключено к %s", port)
            return True
        except Exception as e:
            logger.error("Ошибка подключения: %s", e)
            return False

    def disconnect_real_robot(self) -> None:
        """Отключение реального робота."""
        if self.st3215:
            try:
                if hasattr(self.st3215, "portHandler"):
                    self.st3215.portHandler.closePort()
            except Exception:
                pass
        self.st3215 = None
        self.sync_with_real = False

    def _sync_to_real(self, angles_deg: list[float]) -> None:
        """Отправка углов из симуляции на реальный робот."""
        if not self.st3215:
            return
        for i in range(6):
            motor_id = self._get_motor_id(i)
            position = RobotKinematics6DOF.angle_to_motor_position(angles_deg[i])
            position = self._apply_inversion(position, i)
            try:
                self.st3215.MoveTo(motor_id, position, speed=100, acc=DEFAULT_ACC)
            except Exception as e:
                logger.warning("Мотор %d: %s", motor_id, e)

    def read_real_angles(self) -> list[float] | None:
        """Чтение углов с реального робота и обновление симуляции."""
        if not self.st3215:
            return None
        angles: list[float] = []
        for i in range(6):
            motor_id = self._get_motor_id(i)
            try:
                pos = self.st3215.ReadPosition(motor_id)
                pos = self._apply_inversion(pos, i)
                angle = RobotKinematics6DOF.position_to_motor_angle(pos)
                angles.append(angle)
            except Exception:
                angles.append(0.0)
        self.set_joint_angles(angles, immediate=True)
        return angles

    def _get_motor_id(self, joint_index: int) -> int:
        key = f"joint_{joint_index}"
        if key in DEFAULT_MOTOR_MAPPING:
            return DEFAULT_MOTOR_MAPPING[key]["motor_id"]
        return joint_index + 1

    def _apply_inversion(self, position: int, joint_index: int) -> int:
        key = f"joint_{joint_index}"
        if key in DEFAULT_MOTOR_MAPPING:
            if DEFAULT_MOTOR_MAPPING[key].get("inverted", False):
                return MAX_POSITION - position
        return position

    # ============================
    # Маршрутные точки (Waypoints)
    # ============================

    def execute_waypoints(
        self,
        points_mm: Sequence[tuple[float, float, float]],
        grip_actions: Sequence[bool | None] | None = None,
        settle_time: float = 1.0,
        viewer: Any = None,
    ) -> None:
        """
        Последовательное движение по маршрутным точкам.

        Args:
            points_mm: список точек (x, y, z) в мм
            grip_actions: True=открыть, False=закрыть, None=не менять
            settle_time: время ожидания в каждой точке (секунды)
            viewer: MuJoCo viewer для обновления
        """
        if grip_actions is None:
            grip_actions = [None] * len(points_mm)

        n_points = len(points_mm)
        for i, (x, y, z) in enumerate(points_mm):
            logger.info("Точка %d/%d: (%.0f, %.0f, %.0f) мм", i + 1, n_points, x, y, z)

            self.set_target_marker(x, y, z)

            angles = self.move_to_point(x, y, z)
            if angles is None:
                logger.warning("Пропуск точки (IK не решена)")
                continue

            # Ожидание достижения
            steps_per_frame = int(settle_time / self.model.opt.timestep)
            for s in range(steps_per_frame):
                mujoco.mj_step(self.model, self.data)
                if viewer and s % _STEPS_PER_FRAME == 0:
                    viewer.sync()

            # Действие гриппера
            action = grip_actions[i]
            if action is True:
                self.open_gripper()
                logger.info("Гриппер открыт")
            elif action is False:
                self.close_gripper()
                logger.info("Гриппер закрыт")

            # Стабилизация гриппера
            if action is not None:
                grip_steps = int(0.3 / self.model.opt.timestep)
                for s in range(grip_steps):
                    mujoco.mj_step(self.model, self.data)
                    if viewer and s % _STEPS_PER_FRAME == 0:
                        viewer.sync()

            ee = self.get_ee_position_mm()
            logger.info("EE: (%.1f, %.1f, %.1f) мм", *ee)


# ============================================================
# Интерактивный запуск
# ============================================================


def run_interactive() -> None:
    """Запуск MuJoCo с интерактивным управлением через viewer."""
    print("\n" + "=" * 70)
    print("MuJoCo Robot Simulation — ST3215 6-DOF")
    print("=" * 70)

    xml = generate_robot_mjcf()
    ctrl = MuJoCoRobotController(xml)

    # Начальная поза
    ctrl.set_joint_angles([0, 0, 0, 0, 0, 0], immediate=True)
    ctrl.open_gripper()

    print("\nКоманды (вводите в терминал):")
    print("  angles <j0> <j1> <j2> <j3> <j4> <j5>  — установить углы (градусы)")
    print("  goto <x> <y> <z>                       — IK к точке (мм)")
    print("  grip open / grip close                  — управление гриппером")
    print("  obs                                     — получить наблюдение (RL)")
    print("  sync <COM_PORT>                         — синхронизация с ST3215")
    print("  read                                    — прочитать углы с реального робота")
    print("  reset                                   — сброс симуляции")
    print("  demo                                    — демонстрация pick & place")
    print("  ee                                      — позиция end-effector")
    print("  q                                       — выход")
    print()

    # Запуск viewer
    viewer = mujoco.viewer.launch_passive(ctrl.model, ctrl.data)

    # Основной цикл
    running = True

    def input_loop() -> None:
        nonlocal running
        while running:
            try:
                cmd = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                running = False
                break

            if not cmd:
                continue

            parts = cmd.split()
            command = parts[0].lower()

            try:
                if command in ("q", "quit", "exit"):
                    running = False

                elif command == "angles" and len(parts) == 7:
                    angles = [float(p) for p in parts[1:]]
                    ctrl.set_joint_angles(angles)
                    print(f"  Углы: {[f'{a:.1f}' for a in angles]}")

                elif command == "goto" and len(parts) == 4:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    ctrl.set_target_marker(x, y, z)
                    result = ctrl.move_to_point(x, y, z)
                    if result:
                        print(f"  IK: {[f'{a:.1f}' for a in result]}")

                elif command == "grip":
                    if len(parts) > 1 and parts[1] == "close":
                        ctrl.close_gripper()
                        print("  Закрыт")
                    else:
                        ctrl.open_gripper()
                        print("  Открыт")

                elif command == "obs":
                    obs = ctrl.get_observation()
                    print(f"  RGB: {obs['rgb'].shape}")
                    print(f"  Depth: {obs['depth'].shape}")
                    print(f"  Angles: {obs['joint_angles']}")
                    print(f"  EE: {obs['ee_pos']}")
                    print(f"  Objects: {list(obs['object_positions'].keys())}")

                elif command == "sync" and len(parts) > 1:
                    ctrl.connect_real_robot(parts[1])

                elif command == "read":
                    angles = ctrl.read_real_angles()
                    if angles:
                        print(f"  Углы: {[f'{a:.1f}' for a in angles]}")

                elif command == "reset":
                    ctrl.reset()
                    ctrl.open_gripper()
                    print("  Сброшено")

                elif command == "demo":
                    print("  Запуск демонстрации pick & place...")
                    run_pick_place_demo(ctrl, viewer)

                elif command == "ee":
                    pos = ctrl.get_ee_position_mm()
                    print(f"  EE: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) мм")

                else:
                    print(f"  Неизвестная команда: {cmd}")

            except Exception as e:
                print(f"  Ошибка: {e}")

    # Поток ввода
    input_thread = threading.Thread(target=input_loop, daemon=True)
    input_thread.start()

    # Основной цикл симуляции
    try:
        while running and viewer.is_running():
            mujoco.mj_step(ctrl.model, ctrl.data)
            viewer.sync()
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        ctrl.disconnect_real_robot()
        viewer.close()
        print("\nСимуляция завершена")


def run_pick_place_demo(ctrl: MuJoCoRobotController, viewer: Any = None) -> None:
    """Демонстрация pick & place: поднять красный кубик и переместить."""
    print("\nДемонстрация pick & place")
    print("=" * 40)

    waypoints: list[tuple[float, float, float]] = [
        (150, 0, 200),  # Подъём над столом
        (150, 50, 100),  # Над красным кубиком
        (150, 50, 60),  # Опуститься к кубику
    ]
    grip_actions: list[bool | None] = [
        True,  # Открыть
        True,  # Держать открытым
        False,  # Закрыть (схватить)
    ]

    waypoints_2: list[tuple[float, float, float]] = [
        (150, 50, 150),  # Поднять
        (150, -80, 150),  # Переместить
        (150, -80, 60),  # Опустить
    ]
    grip_actions_2: list[bool | None] = [
        None,  # Не менять
        None,  # Не менять
        True,  # Открыть (отпустить)
    ]

    print("\nФаза 1: Захват")
    ctrl.execute_waypoints(waypoints, grip_actions, settle_time=1.5, viewer=viewer)

    print("\nФаза 2: Перенос")
    ctrl.execute_waypoints(waypoints_2, grip_actions_2, settle_time=1.5, viewer=viewer)

    print("\nДемонстрация завершена!")


# ============================================================
# Headless режим для RL-обучения
# ============================================================


class RobotEnv:
    """
    Gymnasium-совместимая среда для RL-обучения.

    Наблюдение: RGB изображение + joint angles + ee position
    Действие: 6 углов суставов + 1 гриппер
    Награда: -distance_to_target + grasp_bonus

    Возвращает 5-кортеж (obs, reward, terminated, truncated, info)
    по стандарту Gymnasium API.
    """

    def __init__(
        self,
        camera_width: int = _DEFAULT_CAMERA_WIDTH,
        camera_height: int = _DEFAULT_CAMERA_HEIGHT,
    ):
        xml = generate_robot_mjcf()
        self.ctrl = MuJoCoRobotController(
            xml, camera_width=camera_width, camera_height=camera_height
        )
        self.target_object = "red_cube"
        self.target_place = np.array([0.12, -0.08, 0.065])
        self._step_count = 0
        self._max_steps = 1000

    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[dict, dict]:
        """Сброс среды (Gymnasium API)."""
        self.ctrl.reset()
        self.ctrl.open_gripper()
        self.ctrl.set_joint_angles([0, -30, 60, -30, 0, 0], immediate=True)
        self.ctrl.step(100)
        self._step_count = 0
        return self.ctrl.get_observation(), {}

    def step(self, action: np.ndarray) -> tuple[dict, float, bool, bool, dict]:
        """
        Шаг среды (Gymnasium API).

        Args:
            action: [j0, j1, j2, j3, j4, j5, gripper]
                    углы в градусах, gripper: >0 = открыть, <=0 = закрыть

        Returns:
            (observation, reward, terminated, truncated, info)
        """
        self._step_count += 1

        # Установка углов
        angles = action[:6].tolist()
        self.ctrl.set_joint_angles(angles)

        # Гриппер
        if action[6] > 0:
            self.ctrl.open_gripper()
        else:
            self.ctrl.close_gripper()

        # Шаг физики
        self.ctrl.step(100)

        # Наблюдение
        obs = self.ctrl.get_observation()

        # Награда
        ee_pos = obs["ee_pos"]
        obj_pos = obs["object_positions"].get(self.target_object, np.zeros(3))
        dist_to_obj = float(np.linalg.norm(ee_pos - obj_pos))
        reward = -dist_to_obj

        # Бонус за захват (объект поднят)
        if obj_pos[2] > 0.1:
            reward += 1.0

        terminated = False
        truncated = self._step_count >= self._max_steps
        info = {"distance": dist_to_obj, "step": self._step_count}

        return obs, reward, terminated, truncated, info

    def close(self) -> None:
        """Освобождение ресурсов среды."""
        self.ctrl.close()

    def __enter__(self) -> RobotEnv:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ============================================================
# Точка входа
# ============================================================


def main() -> None:
    """Запуск симуляции."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if len(sys.argv) > 1 and sys.argv[1] == "--headless":
        logger.info("Headless режим (для RL)")
        with RobotEnv() as env:
            obs, _ = env.reset()
            logger.info("RGB: %s", obs["rgb"].shape)
            logger.info("Angles: %s", obs["joint_angles"])
            logger.info("EE: %s", obs["ee_pos"])
            logger.info("Среда готова к обучению!")
    else:
        run_interactive()


if __name__ == "__main__":
    main()
