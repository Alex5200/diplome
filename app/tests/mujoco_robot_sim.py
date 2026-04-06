#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MuJoCo Robot Simulation with ST3215 Control

Полная симуляция 6-DOF робота-манипулятора в MuJoCo с:
- Точная MJCF модель по DH-параметрам (L0=19, L1=134, L2=95, L3=34, L4=35 мм)
- Двухпальцевый гриппер
- Объекты для захвата (кубики, цилиндры)
- Стол как рабочая зона
- Камеры: фиксированная сверху + камера на гриппере (eye-in-hand)
- Управление: слайдеры / IK к точке / waypoints
- Рендеринг RGB + Depth для будущего RL-обучения
- Синхронизация с реальными моторами ST3215 (опционально)

Использование:
    python -m app.tests.mujoco_robot_sim
"""

import sys
import math
import time
import threading
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple, Dict

# Добавляем корень проекта
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

try:
    import mujoco
    import mujoco.viewer
except ImportError:
    print("❌ MuJoCo не установлен! Запустите: pip install mujoco")
    sys.exit(1)

from app.models.kinematics import RobotKinematics6DOF, InverseKinematics6DOF
from app.config.constants import (
    MAX_POSITION,
    DEFAULT_SPEED,
    DEFAULT_ACC,
    DEFAULT_MOTOR_MAPPING,
)

# Опциональный импорт ST3215
try:
    from st3215 import ST3215

    ST3215_AVAILABLE = True
except ImportError:
    ST3215_AVAILABLE = False


# ============================================================
# Генерация MJCF модели робота
# ============================================================


def generate_robot_mjcf(
    with_gripper: bool = True,
    with_objects: bool = True,
    with_table: bool = True,
    with_cameras: bool = True,
) -> str:
    """
    Генерация XML-модели робота в формате MJCF.

    Модель строится по DH-параметрам кинематики:
    - J1: База — вращение вокруг Z, высота L0=19мм
    - J2: Плечо 1 — вращение вокруг Y, длина L1=134мм
    - J3: Плечо 2 — вращение вокруг Y, длина L2=95мм
    - J4: Локоть  — вращение вокруг Y + twist, длина L3=34мм
    - J5: Кисть 1 — вращение вокруг Z, длина L4=35мм
    - J6: Кисть 2 — вращение вокруг Y

    Все размеры в метрах (MuJoCo стандарт).
    """
    # Конвертация мм → м
    L0 = 0.019  # База
    L1 = 0.134  # Плечо 1
    L2 = 0.095  # Плечо 2
    L3 = 0.034  # Локоть
    L4 = 0.035  # Кисть 1
    L5 = 0.000  # Инструмент

    # Радиусы звеньев для визуализации (пропорциональны)
    r_base = 0.025
    r_link1 = 0.015
    r_link2 = 0.012
    r_link3 = 0.010
    r_link4 = 0.008
    r_grip = 0.005

    # Высота стола
    table_h = 0.05
    table_size = 0.3

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

    cameras_xml = ""
    if with_cameras:
        cameras_xml = f"""
    <!-- Камеры -->
    <camera name="top_down" pos="0 0 0.6" quat="0 0 0 1"
            fovy="60" mode="fixed"/>
    <camera name="front" pos="0.5 0 0.2" xyaxes="0 1 0 0 0 1"
            fovy="60" mode="fixed"/>
    <camera name="side" pos="0 0.5 0.2" xyaxes="-1 0 0 0 0 1"
            fovy="60" mode="fixed"/>
"""

    eye_in_hand_xml = ""
    if with_cameras:
        eye_in_hand_xml = """
                        <!-- Камера на гриппере (eye-in-hand) -->
                        <camera name="eye_in_hand" pos="0 0 0.03"
                                xyaxes="0 -1 0 1 0 0"
                                fovy="90"/>
"""

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

    table_xml = ""
    if with_table:
        table_xml = f"""
    <!-- Стол / рабочая поверхность -->
    <body name="table" pos="0.15 0 {table_h / 2}">
      <geom name="table_geom" type="box" size="{table_size} {table_size} {table_h / 2}"
            rgba="0.6 0.5 0.4 1" friction="1 0.5 0.01" condim="4"/>
    </body>
"""

    # Целевой маркер (полупрозрачный, не влияет на физику)
    target_marker_xml = f"""
    <body name="target_marker" pos="0.15 0 0.15" mocap="true">
      <geom name="target_geom" type="sphere" size="0.01"
            rgba="1 0 1 0.5" contype="0" conaffinity="0"/>
    </body>
"""

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
               range="{math.radians(-120)} {math.radians(120)}"
               damping="1.0" armature="0.02"/>
        <geom name="link0_geom" type="cylinder" size="{r_base} {L0 / 2}"
              pos="0 0 {L0 / 2}" material="robot_blue" mass="0.05"/>

        <!-- J2: Плечо 1 — вращение вокруг Y, длина L1 -->
        <body name="link1_shoulder" pos="0 0 {L0}">
          <joint name="joint_1" type="hinge" axis="0 1 0"
                 range="{math.radians(-45)} {math.radians(90)}"
                 damping="0.8" armature="0.02"/>
          <geom name="link1_geom" type="capsule" size="{r_link1}"
                fromto="0 0 0 {L1} 0 0" material="robot_orange" mass="0.04"/>

          <!-- J3: Плечо 2 — вращение вокруг Y, длина L2 -->
          <body name="link2_shoulder2" pos="{L1} 0 0">
            <joint name="joint_2" type="hinge" axis="0 1 0"
                   range="{math.radians(-90)} {math.radians(45)}"
                   damping="0.6" armature="0.015"/>
            <geom name="link2_geom" type="capsule" size="{r_link2}"
                  fromto="0 0 0 {L2} 0 0" material="robot_blue" mass="0.03"/>

            <!-- J4: Локоть — вращение вокруг Y, длина L3 -->
            <body name="link3_elbow" pos="{L2} 0 0">
              <joint name="joint_3" type="hinge" axis="0 1 0"
                     range="{math.radians(-120)} {math.radians(0)}"
                     damping="0.4" armature="0.01"/>
              <geom name="link3_geom" type="capsule" size="{r_link3}"
                    fromto="0 0 0 {L3} 0 0" material="robot_orange" mass="0.02"/>

              <!-- J5: Кисть 1 — вращение вокруг Z, длина L4 -->
              <body name="link4_wrist1" pos="{L3} 0 0">
                <joint name="joint_4" type="hinge" axis="0 0 1"
                       range="{math.radians(-90)} {math.radians(90)}"
                       damping="0.3" armature="0.008"/>
                <geom name="link4_geom" type="capsule" size="{r_link4}"
                      fromto="0 0 0 {L4} 0 0" material="robot_light" mass="0.015"/>

                <!-- J6: Кисть 2 — вращение вокруг Y -->
                <body name="link5_wrist2" pos="{L4} 0 0">
                  <joint name="joint_5" type="hinge" axis="0 1 0"
                         range="{math.radians(-90)} {math.radians(90)}"
                         damping="0.2" armature="0.005"/>
                  <geom name="link5_geom" type="sphere" size="{r_link4 + 0.002}"
                        material="robot_dark" mass="0.01"/>

                  <!-- Сайт для end-effector -->
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
    <position name="act_joint_0" joint="joint_0" kp="50" ctrlrange="{math.radians(-120)} {math.radians(120)}"/>
    <position name="act_joint_1" joint="joint_1" kp="80" ctrlrange="{math.radians(-45)} {math.radians(90)}"/>
    <position name="act_joint_2" joint="joint_2" kp="60" ctrlrange="{math.radians(-90)} {math.radians(45)}"/>
    <position name="act_joint_3" joint="joint_3" kp="40" ctrlrange="{math.radians(-120)} {math.radians(0)}"/>
    <position name="act_joint_4" joint="joint_4" kp="30" ctrlrange="{math.radians(-90)} {math.radians(90)}"/>
    <position name="act_joint_5" joint="joint_5" kp="20" ctrlrange="{math.radians(-90)} {math.radians(90)}"/>
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


class MuJoCoRobotController:
    """
    Управление роботом в MuJoCo симуляции.

    Функции:
    - Установка углов суставов (градусы → радианы)
    - IK к целевой точке
    - Управление гриппером (открыть/закрыть)
    - Рендеринг RGB/Depth с камер
    - Чтение сенсоров
    - Синхронизация с реальным ST3215 (опционально)
    """

    # Имена суставов в порядке joint_0..joint_5
    JOINT_NAMES = [f"joint_{i}" for i in range(6)]
    ACTUATOR_NAMES = [f"act_joint_{i}" for i in range(6)]

    SAFE_ANGLE_LIMITS_DEG = [
        (-120, 120),
        (-45, 90),
        (-90, 45),
        (-120, 0),
        (-90, 90),
        (-90, 90),
    ]

    def __init__(self, xml_string: Optional[str] = None):
        """Инициализация симуляции."""
        if xml_string is None:
            xml_string = generate_robot_mjcf()

        self.model = mujoco.MjModel.from_xml_string(xml_string)
        self.data = mujoco.MjData(self.model)

        # Кинематика для IK
        self.kinematics = RobotKinematics6DOF()
        self.ik_solver = InverseKinematics6DOF(self.kinematics)

        # Индексы актуаторов
        self._joint_actuator_ids = []
        for name in self.ACTUATOR_NAMES:
            self._joint_actuator_ids.append(
                mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
            )

        # Гриппер
        self._has_gripper = False
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

        # Камера рендерер
        self._renderer = None
        self._camera_width = 640
        self._camera_height = 480

        # Текущие целевые углы
        self.target_angles_deg = [0.0] * 6
        self.gripper_open = True

        # ST3215 (опционально)
        self.st3215: Optional[ST3215] = None
        self.sync_with_real = False

        # Инициализация
        mujoco.mj_forward(self.model, self.data)
        print("✅ MuJoCo модель загружена")
        print(f"   Суставов: {self.model.njnt}, Актуаторов: {self.model.nu}")
        print(f"   Гриппер: {'✅' if self._has_gripper else '❌'}")

    # ============================
    # Управление суставами
    # ============================

    def set_joint_angles(self, angles_deg: List[float], immediate: bool = False):
        """
        Установка целевых углов суставов.

        Args:
            angles_deg: 6 углов в градусах
            immediate: если True, сразу перемещает (без физики),
                       если False, через актуаторы (плавно)
        """
        assert len(angles_deg) == 6, "Нужно 6 углов"

        self.target_angles_deg = list(angles_deg)

        for i in range(6):
            angle_rad = math.radians(angles_deg[i])
            act_id = self._joint_actuator_ids[i]
            self.data.ctrl[act_id] = angle_rad

            if immediate:
                jnt_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f"joint_{i}")
                qpos_adr = self.model.jnt_qposadr[jnt_id]
                self.data.qpos[qpos_adr] = angle_rad

        if immediate:
            mujoco.mj_forward(self.model, self.data)

        # Синхронизация с реальным роботом
        if self.sync_with_real and self.st3215:
            self._sync_to_real(angles_deg)

    def get_joint_angles(self) -> List[float]:
        """Чтение текущих углов суставов из симуляции (градусы)."""
        angles = []
        for i in range(6):
            jnt_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f"joint_{i}")
            qpos_adr = self.model.jnt_qposadr[jnt_id]
            angles.append(math.degrees(self.data.qpos[qpos_adr]))
        return angles

    def get_ee_position(self) -> Tuple[float, float, float]:
        """Позиция end-effector из симуляции (метры)."""
        site_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")
        pos = self.data.site_xpos[site_id]
        return (pos[0], pos[1], pos[2])

    def get_ee_position_mm(self) -> Tuple[float, float, float]:
        """Позиция end-effector в миллиметрах (относительно базы)."""
        pos = self.get_ee_position()
        # Вычитаем позицию базы (стол + монтаж)
        base_z = 0.05  # высота стола
        return (pos[0] * 1000, pos[1] * 1000, (pos[2] - base_z) * 1000)

    # ============================
    # IK — движение к точке
    # ============================

    def move_to_point(
        self, x_mm: float, y_mm: float, z_mm: float, tolerance: float = 2.0
    ) -> Optional[List[float]]:
        """
        Решение IK и отправка углов в симуляцию.

        Args:
            x_mm, y_mm, z_mm: целевая точка в мм (в системе координат робота)
            tolerance: допуск IK в мм

        Returns:
            Углы в градусах или None
        """
        angles = self.ik_solver.solve(x_mm, y_mm, z_mm, max_iterations=300, tolerance=tolerance)
        if angles is None:
            print(f"❌ IK не решена для ({x_mm:.0f}, {y_mm:.0f}, {z_mm:.0f}) мм")
            return None

        # Обрезка по безопасным лимитам
        for i in range(6):
            lo, hi = self.SAFE_ANGLE_LIMITS_DEG[i]
            angles[i] = max(lo, min(hi, angles[i]))

        self.set_joint_angles(angles)
        return angles

    def set_target_marker(self, x_mm: float, y_mm: float, z_mm: float):
        """Перемещение визуального маркера цели в MuJoCo."""
        try:
            body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "target_marker")
            # mocap тела имеют отдельный массив
            mocap_id = self.model.body_mocapid[body_id]
            if mocap_id >= 0:
                base_z = 0.05
                self.data.mocap_pos[mocap_id] = [
                    x_mm / 1000.0,
                    y_mm / 1000.0,
                    z_mm / 1000.0 + base_z,
                ]
        except Exception:
            pass

    # ============================
    # Гриппер
    # ============================

    def open_gripper(self):
        """Открыть гриппер."""
        if not self._has_gripper:
            return
        self.data.ctrl[self._finger_left_id] = 0.02
        self.data.ctrl[self._finger_right_id] = 0.02
        self.gripper_open = True

    def close_gripper(self):
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
        width: int = 640,
        height: int = 480,
        depth: bool = False,
    ) -> np.ndarray:
        """
        Рендеринг изображения с указанной камеры.

        Args:
            camera_name: имя камеры ("top_down", "front", "side", "eye_in_hand")
            width, height: размеры
            depth: если True, возвращает depth-карту

        Returns:
            RGB array (H, W, 3) uint8 или depth array (H, W) float32
        """
        renderer = mujoco.Renderer(self.model, height=height, width=width)
        renderer.update_scene(self.data, camera=camera_name)

        if depth:
            renderer.enable_depth_rendering()
            img = renderer.render()
            renderer.disable_depth_rendering()
        else:
            img = renderer.render()

        renderer.close()
        return img

    def get_observation(self, camera_name: str = "eye_in_hand") -> Dict:
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

        # Позиции объектов
        obj_positions = {}
        for name in ["red_cube", "green_cube", "blue_cylinder", "yellow_cube"]:
            try:
                body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, name)
                pos = self.data.xpos[body_id].copy()
                obj_positions[name] = pos
            except Exception:
                pass

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

    def step(self, n_steps: int = 1):
        """Шаг физической симуляции."""
        for _ in range(n_steps):
            mujoco.mj_step(self.model, self.data)

    def step_seconds(self, seconds: float):
        """Симулировать указанное количество секунд."""
        n = int(seconds / self.model.opt.timestep)
        self.step(n)

    def reset(self):
        """Сброс симуляции."""
        mujoco.mj_resetData(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)
        self.target_angles_deg = [0.0] * 6
        self.gripper_open = True

    # ============================
    # Синхронизация с ST3215
    # ============================

    def connect_real_robot(self, port: str = "COM3"):
        """Подключение к реальному роботу ST3215."""
        if not ST3215_AVAILABLE:
            print("❌ st3215 не установлен")
            return False
        try:
            self.st3215 = ST3215(device=port)
            self.sync_with_real = True
            print(f"✅ Подключено к {port}")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    def disconnect_real_robot(self):
        """Отключение реального робота."""
        if self.st3215:
            try:
                if hasattr(self.st3215, "portHandler"):
                    self.st3215.portHandler.closePort()
            except Exception:
                pass
        self.st3215 = None
        self.sync_with_real = False

    def _sync_to_real(self, angles_deg: List[float]):
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
                print(f"⚠️ Мотор {motor_id}: {e}")

    def read_real_angles(self) -> Optional[List[float]]:
        """Чтение углов с реального робота и обновление симуляции."""
        if not self.st3215:
            return None
        angles = []
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
        points_mm: List[Tuple[float, float, float]],
        grip_actions: Optional[List[Optional[bool]]] = None,
        settle_time: float = 1.0,
        viewer=None,
    ):
        """
        Последовательное движение по маршрутным точкам.

        Args:
            points_mm: список точек (x, y, z) в мм
            grip_actions: для каждой точки True=открыть, False=закрыть, None=не менять
            settle_time: время ожидания в каждой точке (секунды)
            viewer: MuJoCo viewer для обновления
        """
        if grip_actions is None:
            grip_actions = [None] * len(points_mm)

        for i, (x, y, z) in enumerate(points_mm):
            print(f"📍 Точка {i + 1}/{len(points_mm)}: ({x:.0f}, {y:.0f}, {z:.0f}) мм")

            # Маркер
            self.set_target_marker(x, y, z)

            # IK
            angles = self.move_to_point(x, y, z)
            if angles is None:
                print(f"  ⏭️ Пропуск (IK не решена)")
                continue

            # Ожидание достижения
            steps_per_frame = int(settle_time / self.model.opt.timestep)
            for s in range(steps_per_frame):
                mujoco.mj_step(self.model, self.data)
                if viewer and s % 50 == 0:
                    viewer.sync()

            # Действие гриппера
            if grip_actions[i] is True:
                self.open_gripper()
                print("  🖐️ Гриппер открыт")
            elif grip_actions[i] is False:
                self.close_gripper()
                print("  ✊ Гриппер закрыт")

            # Ещё немного времени для стабилизации гриппера
            if grip_actions[i] is not None:
                for s in range(int(0.3 / self.model.opt.timestep)):
                    mujoco.mj_step(self.model, self.data)
                    if viewer and s % 50 == 0:
                        viewer.sync()

            ee = self.get_ee_position_mm()
            print(f"  ✅ EE: ({ee[0]:.1f}, {ee[1]:.1f}, {ee[2]:.1f}) мм")


# ============================================================
# Интерактивный запуск
# ============================================================


def run_interactive():
    """Запуск MuJoCo с интерактивным управлением через viewer."""
    print("\n" + "=" * 70)
    print("🤖 MuJoCo Robot Simulation — ST3215 6-DOF")
    print("=" * 70)

    xml = generate_robot_mjcf()
    ctrl = MuJoCoRobotController(xml)

    # Начальная поза
    ctrl.set_joint_angles([0, 0, 0, 0, 0, 0], immediate=True)
    ctrl.open_gripper()

    print("\n📋 Команды (вводите в терминал):")
    print("  angles <j0> <j1> <j2> <j3> <j4> <j5>  — установить углы (градусы)")
    print("  goto <x> <y> <z>                       — IK к точке (мм)")
    print("  grip open / grip close                  — управление гриппером")
    print("  obs                                     — получить наблюдение (RL)")
    print("  sync <COM_PORT>                         — синхронизация с ST3215")
    print("  read                                    — прочитать углы с реального робота")
    print("  reset                                   — сброс симуляции")
    print("  demo                                    — демонстрация pick & place")
    print("  q                                       — выход")
    print()

    # Запуск viewer
    viewer = mujoco.viewer.launch_passive(ctrl.model, ctrl.data)

    # Основной цикл
    running = True

    def input_loop():
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
                if command == "q" or command == "quit" or command == "exit":
                    running = False

                elif command == "angles" and len(parts) == 7:
                    angles = [float(p) for p in parts[1:]]
                    ctrl.set_joint_angles(angles)
                    print(f"  ✅ Углы: {[f'{a:.1f}' for a in angles]}")

                elif command == "goto" and len(parts) == 4:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    ctrl.set_target_marker(x, y, z)
                    result = ctrl.move_to_point(x, y, z)
                    if result:
                        print(f"  ✅ IK: {[f'{a:.1f}' for a in result]}")

                elif command == "grip":
                    if len(parts) > 1 and parts[1] == "close":
                        ctrl.close_gripper()
                        print("  ✊ Закрыт")
                    else:
                        ctrl.open_gripper()
                        print("  🖐️ Открыт")

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
                        print(f"  📖 Углы: {[f'{a:.1f}' for a in angles]}")

                elif command == "reset":
                    ctrl.reset()
                    ctrl.open_gripper()
                    print("  🔄 Сброшено")

                elif command == "demo":
                    print("  ▶️ Запуск демонстрации pick & place...")
                    run_pick_place_demo(ctrl, viewer)

                elif command == "ee":
                    pos = ctrl.get_ee_position_mm()
                    print(f"  📍 EE: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) мм")

                else:
                    print(f"  ❓ Неизвестная команда: {cmd}")

            except Exception as e:
                print(f"  ❌ Ошибка: {e}")

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
        print("\n👋 Симуляция завершена")


def run_pick_place_demo(ctrl: MuJoCoRobotController, viewer=None):
    """Демонстрация pick & place: поднять красный кубик и переместить."""
    print("\n🎬 Демонстрация pick & place")
    print("=" * 40)

    waypoints = [
        # (x_mm, y_mm, z_mm)
        (150, 0, 200),  # Подъём над столом
        (150, 50, 100),  # Над красным кубиком
        (150, 50, 60),  # Опуститься к кубику
    ]
    grip_actions = [
        True,  # Открыть
        True,  # Держать открытым
        False,  # Закрыть (схватить)
    ]

    waypoints_2 = [
        (150, 50, 150),  # Поднять
        (150, -80, 150),  # Переместить
        (150, -80, 60),  # Опустить
    ]
    grip_actions_2 = [
        None,  # Не менять
        None,  # Не менять
        True,  # Открыть (отпустить)
    ]

    print("\n📦 Фаза 1: Захват")
    ctrl.execute_waypoints(waypoints, grip_actions, settle_time=1.5, viewer=viewer)

    print("\n📦 Фаза 2: Перенос")
    ctrl.execute_waypoints(waypoints_2, grip_actions_2, settle_time=1.5, viewer=viewer)

    print("\n✅ Демонстрация завершена!")


# ============================================================
# Headless режим для RL-обучения
# ============================================================


class RobotEnv:
    """
    Gym-подобная среда для RL-обучения.

    Наблюдение: RGB изображение + joint angles + ee position
    Действие: 6 углов суставов + 1 гриппер
    Награда: -distance_to_target + grasp_bonus
    """

    def __init__(self):
        xml = generate_robot_mjcf()
        self.ctrl = MuJoCoRobotController(xml)
        self.target_object = "red_cube"
        self.target_place = np.array([0.12, -0.08, 0.065])  # Позиция для размещения

    def reset(self) -> Dict:
        """Сброс среды."""
        self.ctrl.reset()
        self.ctrl.open_gripper()
        # Начальная поза
        self.ctrl.set_joint_angles([0, -30, 60, -30, 0, 0], immediate=True)
        self.ctrl.step(100)
        return self.ctrl.get_observation()

    def step(self, action: np.ndarray) -> Tuple[Dict, float, bool, Dict]:
        """
        Шаг среды.

        Args:
            action: [j0, j1, j2, j3, j4, j5, gripper]
                    углы в градусах, gripper: >0 = открыть, <=0 = закрыть

        Returns:
            (observation, reward, done, info)
        """
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
        dist_to_obj = np.linalg.norm(ee_pos - obj_pos)
        reward = -dist_to_obj

        # Бонус за захват (объект поднят)
        if obj_pos[2] > 0.1:  # Объект выше 10 см
            reward += 1.0

        done = False
        info = {"distance": dist_to_obj}

        return obs, reward, done, info


# ============================================================
# Точка входа
# ============================================================


def main():
    """Запуск симуляции."""
    if len(sys.argv) > 1 and sys.argv[1] == "--headless":
        print("🤖 Headless режим (для RL)")
        env = RobotEnv()
        obs = env.reset()
        print(f"  RGB: {obs['rgb'].shape}")
        print(f"  Angles: {obs['joint_angles']}")
        print(f"  EE: {obs['ee_pos']}")
        print("  Среда готова к обучению!")
    else:
        run_interactive()


if __name__ == "__main__":
    main()
