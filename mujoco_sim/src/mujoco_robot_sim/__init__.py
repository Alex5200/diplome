#!/usr/bin/env python3

"""
mujoco_robot_sim — симуляция 6-DOF робота-манипулятора ST3215 в MuJoCo.

Модуль реализует полный цикл работы с роботом внутри физического движка
MuJoCo: от программной генерации MJCF-модели до интерактивного управления,
рендеринга изображений для RL-обучения и двустороннего зеркалирования
состояния с реальным оборудованием.

Ключевые компоненты
───────────────────
generate_robot_mjcf(**flags) -> str
    Строит MJCF XML-строку по DH-параметрам кинематики (из app/models/kinematics.py).
    Принимает флаги с_gripper, with_objects, with_table, with_cameras.

MuJoCoRobotController
    Основной класс управления: загружает модель, управляет суставами,
    вызывает IK-решатель, рендерит камеры, синхронизируется с ST3215.

RobotEnv
    Gymnasium-совместимая среда для обучения RL-агентов.
    Пространство действий: [j0..j5, gripper] — 7-мерный вектор.

SimToRealMirror (mujoco_robot_sim.sim_to_real)
    Фоновый поток, зеркалирующий состояние симуляции ↔ реального робота.

DH-параметры (мм, синхронизированы с app/models/kinematics.py)
───────────────────────────────────────────────────────────────
    L0 = 19  — высота базы
    L1 = 104 — длина звена «плечо 1»
    L2 = 95  — длина звена «плечо 2»
    L3 = 34  — длина звена «локоть»
    L4 = 35  — длина звена «кисть 1»

Быстрый старт
─────────────
    # Интерактивный viewer
    python main.py

    # Режим зеркалирования: sim → реальный робот
    python main.py --mirror --port COM3

    # Headless (для RL)
    python main.py --headless

    # Из кода
    from mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf

    ctrl = MuJoCoRobotController(generate_robot_mjcf(with_gripper=True))
    ctrl.set_joint_angles([0, -30, 60, -30, 0, 0])
    ctrl.step_seconds(1.0)
    angles = ctrl.get_joint_angles()   # → list[float], градусы
    ee     = ctrl.get_ee_position_mm() # → (x, y, z), мм
    ctrl.close()

Зависимости
───────────
    Обязательные: mujoco>=3.0, numpy>=1.24
    Опциональные: st3215 (для синхронизации с железом), rclpy (ROS2 транспорт)
"""

from __future__ import annotations

import logging
import math
import sys
import threading
from contextlib import contextmanager
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

DEFAULT_ACC = 50
MAX_POSITION = 4095

DEFAULT_MOTOR_MAPPING = {
    "joint_0": {
        "motor_id": 1,
        "name": "База",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": True,
    },
    "joint_1": {
        "motor_id": 2,
        "name": "Плечо 1",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": False,
    },
    "joint_2": {
        "motor_id": 4,
        "name": "Плечо 2",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": True,
    },
    "joint_3": {
        "motor_id": 5,
        "name": "Локоть",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": False,
    },
    "joint_4": {
        "motor_id": 3,
        "name": "Кисть 1",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": False,
    },
    "joint_5": {
        "motor_id": 6,
        "name": "Кисть 2",
        "min_pos": 0,
        "max_pos": MAX_POSITION,
        "inverted": False,
    },
}

from models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF

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
    """Генерирует MJCF XML-строку модели робота ST3215 6-DOF.

    Модель строится программно по DH-параметрам из ``RobotKinematics6DOF``,
    обеспечивая автоматическую синхронизацию геометрии симуляции с кинематическим
    расчётом при любом изменении длин звеньев.

    Кинематическая цепочка суставов
    ────────────────────────────────
    joint_0  — база, вращение вокруг Z, диапазон ±120°, высота L0=19 мм
    joint_1  — плечо 1, вращение вокруг Y, диапазон −45°…+90°, длина L1=104 мм
    joint_2  — плечо 2, вращение вокруг Y, диапазон −90°…+45°, длина L2=95 мм
    joint_3  — локоть,  вращение вокруг Y, диапазон −120°…0°,  длина L3=34 мм
    joint_4  — кисть 1, вращение вокруг Z, диапазон ±90°,      длина L4=35 мм
    joint_5  — кисть 2, вращение вокруг Y, диапазон ±90°

    Параметры физики
    ────────────────
    timestep = 0.002 с (500 Гц), integrator = implicitfast
    Демпфирование суставов: 1.0→0.2 (убывает от основания к инструменту)
    Актуаторы: позиционные (position), kp = 50→20 (N·m/rad)

    Args:
        with_gripper: Включить двухпальцевый гриппер (суставы finger_left/right,
            актуаторы act_finger_left/right, диапазон 0–20 мм).
        with_objects: Добавить объекты для захвата на стол:
            red_cube (20×20×20 мм), green_cube, yellow_cube (10×10×10 мм),
            blue_cylinder (⌀12×20 мм). Все — свободные тела (freejoint).
        with_table: Добавить рабочий стол (300×300×50 мм, pos=0.15 м от базы).
        with_cameras: Добавить камеры:
            top_down (фиксированная, сверху, fov=60°),
            front (спереди), side (сбоку),
            eye_in_hand (на гриппере, fov=90°) — только если with_gripper=True.

    Returns:
        Корректная MJCF XML-строка, пригодная для передачи в
        ``mujoco.MjModel.from_xml_string()``.

    Note:
        Все координаты в возвращаемом XML — в метрах (стандарт MuJoCo).
        Маркер цели ``target_marker`` всегда включён (mocap-тело, полупрозрачная
        сфера ⌀10 мм, magenta); перемещается через ``set_target_marker()``.

    Example:
        xml = generate_robot_mjcf(with_gripper=True, with_objects=False)
        model = mujoco.MjModel.from_xml_string(xml)
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
    """Кэш целочисленных ID сущностей MuJoCo для быстрого доступа.

    MuJoCo предоставляет ``mj_name2id()`` для поиска сущностей по имени, однако
    вызов этой функции на каждом шаге симуляции нецелесообразен. Все ID
    вычисляются один раз в ``_cache_ids()`` при инициализации контроллера
    и хранятся в этом объекте.

    Attributes:
        joint_ids: Индексы суставов joint_0…joint_5 в массиве ``model.jnt_*``.
        joint_qpos_adr: Адреса обобщённых координат в ``data.qpos``
            для каждого сустава (результат ``model.jnt_qposadr[jnt_id]``).
        actuator_ids: Индексы актуаторов act_joint_0…act_joint_5
            в массиве ``data.ctrl``.
        ee_site_id: Индекс сайта ``end_effector`` для чтения ``data.site_xpos``.
        target_mocap_id: Индекс mocap-тела ``target_marker`` в ``data.mocap_pos``;
            -1 если маркер отсутствует в модели.
        object_body_ids: Словарь {имя_тела: body_id} для объектов захвата
            (red_cube, green_cube, blue_cylinder, yellow_cube).
    """

    joint_ids: list[int] = field(default_factory=list)
    joint_qpos_adr: list[int] = field(default_factory=list)
    actuator_ids: list[int] = field(default_factory=list)
    ee_site_id: int = -1
    target_mocap_id: int = -1
    object_body_ids: dict[str, int] = field(default_factory=dict)


class MuJoCoRobotController:
    """Контроллер робота ST3215 6-DOF в симуляции MuJoCo.

    Инкапсулирует ``mujoco.MjModel`` и ``mujoco.MjData``, предоставляя
    высокоуровневый API для управления суставами, вычисления кинематики,
    рендеринга изображений и опциональной синхронизации с реальным железом.

    Типичный сценарий использования
    ────────────────────────────────
    1. Создать экземпляр (загружает MJCF модель).
    2. Управлять суставами через ``set_joint_angles()`` / ``move_to_point()``.
    3. Продвигать физику через ``step()`` / ``step_seconds()``.
    4. Читать состояние через ``get_joint_angles()`` / ``get_ee_position_mm()``.
    5. Рендерить изображения через ``render_camera()`` / ``get_observation()``.
    6. При необходимости — подключить реального робота ``connect_real_robot()``.
    7. Освободить ресурсы через ``close()`` или контекстным менеджером.

    Attributes:
        model (mujoco.MjModel): Загруженная физическая модель (read-only после init).
        data  (mujoco.MjData):  Текущее состояние симуляции (позиции, скорости,
            управляющие сигналы, сенсоры).
        kinematics (RobotKinematics6DOF): Кинематическая модель для прямой кинематики.
        ik_solver  (InverseKinematics6DOF): IK-решатель (метод DLS, до 300 итераций).
        target_angles_deg (list[float]): Последние заданные целевые углы (°).
        gripper_open (bool): Текущее состояние гриппера.
        st3215 (ST3215 | None): Объект связи с реальным роботом; None если не подключён.
        sync_with_real (bool): Флаг автосинхронизации: если True, каждый вызов
            ``set_joint_angles()`` дополнительно отправляет команды в ST3215.

    Class Attributes:
        JOINT_NAMES (list[str]): ``["joint_0", …, "joint_5"]``
        ACTUATOR_NAMES (list[str]): ``["act_joint_0", …, "act_joint_5"]``
        SAFE_ANGLE_LIMITS_DEG (list[tuple]): Безопасные пределы в градусах для
            каждого сустава: [(−120,120), (−45,90), (−90,45), (−120,0), (±90), (±90)].

    Example:
        with MuJoCoRobotController() as ctrl:
            ctrl.set_joint_angles([0, -30, 60, -30, 0, 0], immediate=True)
            ctrl.step_seconds(2.0)
            print(ctrl.get_ee_position_mm())
    """

    JOINT_NAMES = [f"joint_{i}" for i in range(6)]
    ACTUATOR_NAMES = [f"act_joint_{i}" for i in range(6)]

    SAFE_ANGLE_LIMITS_DEG: list[tuple[float, float]] = [
        (-360, 360),
        (-360, 360),
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
        """Инициализирует MuJoCo модель и все вспомогательные структуры.

        Загружает MJCF-строку, кэширует ID сущностей, инициализирует рендерер
        и кинематический модуль. Вызов ``mj_forward()`` синхронизирует начальное
        состояние физики.

        Args:
            xml_string: MJCF XML-строка модели. Если None — вызывается
                ``generate_robot_mjcf()`` с параметрами по умолчанию
                (with_gripper=True, with_objects=True, with_table=True).
            camera_width: Ширина кадра рендерера в пикселях (default: 640).
            camera_height: Высота кадра рендерера в пикселях (default: 480).

        Raises:
            SystemExit: Если пакет ``mujoco`` не установлен.
            ValueError: Если XML-строка содержит некорректную MJCF-модель
                (пробрасывается из ``mujoco.MjModel.from_xml_string``).
        """
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
        """Освобождает ресурсы: рендерер и соединение с реальным роботом.

        Безопасно вызывать повторно. Эквивалентен выходу из контекстного
        менеджера ``with MuJoCoRobotController() as ctrl``.
        """
        self.disconnect_real_robot()
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None

    # ============================
    # Управление суставами
    # ============================

    def set_joint_angles(self, angles_deg: Sequence[float], immediate: bool = False) -> None:
        """Устанавливает целевые углы всех шести суставов.

        Записывает значения в ``data.ctrl`` (для позиционных актуаторов).
        При ``immediate=True`` также мгновенно обновляет ``data.qpos``
        и вызывает ``mj_forward()`` — полезно для инициализации начальной позы
        без ожидания сходимости физики.

        Если ``sync_with_real=True`` (флаг устанавливается после успешного
        ``connect_real_robot()``), дополнительно вызывает ``_sync_to_real()``
        для отправки команд на ST3215 по UART.

        Args:
            angles_deg: Последовательность из ровно 6 углов в градусах.
                Порядок: [joint_0, joint_1, joint_2, joint_3, joint_4, joint_5].
                Значения не обрезаются — передавать в пределах ``SAFE_ANGLE_LIMITS_DEG``.
            immediate: Если True — мгновенное позиционирование (телепортация),
                минуя физику; если False — плавное движение через PD-регуляторы
                актуаторов (требует последующих вызовов ``step()``).

        Raises:
            ValueError: Если длина ``angles_deg`` не равна 6.

        Example:
            # Плавный переход в позу «готов»
            ctrl.set_joint_angles([0, -30, 60, -30, 0, 0])
            ctrl.step_seconds(1.5)

            # Мгновенная инициализация начального состояния
            ctrl.set_joint_angles([0, 0, 0, 0, 0, 0], immediate=True)
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
        """Возвращает текущие углы суставов из состояния симуляции.

        Читает обобщённые координаты ``data.qpos`` по заранее кэшированным
        адресам ``_ids.joint_qpos_adr`` и конвертирует радианы в градусы.

        Returns:
            Список из 6 углов в градусах: [joint_0, …, joint_5].
            Значения отражают фактическое физическое состояние (не целевое).

        Note:
            Для получения целевых углов (заданных актуаторам) используйте
            ``target_angles_deg``.
        """
        return [math.degrees(self.data.qpos[adr]) for adr in self._ids.joint_qpos_adr]

    def get_ee_position(self) -> tuple[float, float, float]:
        """Возвращает абсолютную позицию конечного эффектора в мировых координатах.

        Читает позицию сайта ``end_effector`` из ``data.site_xpos``.
        Начало координат — центр пола MuJoCo (не основание робота).

        Returns:
            Кортеж (x, y, z) в метрах в системе координат MuJoCo.

        See Also:
            ``get_ee_position_mm()`` — позиция относительно основания в мм.
        """
        pos = self.data.site_xpos[self._ids.ee_site_id]
        return (pos[0], pos[1], pos[2])

    def get_ee_position_mm(self) -> tuple[float, float, float]:
        """Возвращает позицию конечного эффектора в миллиметрах относительно основания.

        Конвертирует метры в мм и вычитает высоту стола ``_TABLE_HEIGHT_M`` из Z,
        приводя начало координат к верхней плоскости рабочего стола.

        Returns:
            Кортеж (x_mm, y_mm, z_mm) в миллиметрах:
            x — вперёд от основания, y — вправо, z — вверх от стола.

        Example:
            x, y, z = ctrl.get_ee_position_mm()
            print(f"EE position: ({x:.1f}, {y:.1f}, {z:.1f}) мм")
        """
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
        """Перемещает конечный эффектор в заданную декартову точку через IK.

        Вызывает ``InverseKinematics6DOF.solve()`` (метод DLS, до 300 итераций),
        обрезает полученные углы по ``SAFE_ANGLE_LIMITS_DEG`` и передаёт в
        ``set_joint_angles()``. Визуальный маркер обновляется отдельно через
        ``set_target_marker()``.

        Args:
            x_mm: Целевая координата X в мм (вперёд от основания).
            y_mm: Целевая координата Y в мм (вправо от основания).
            z_mm: Целевая координата Z в мм (вверх от стола).
            tolerance: Допуск IK-решателя в мм (default: 2.0).
                Уменьшение ускоряет расчёт, но снижает точность.

        Returns:
            Список из 6 углов в градусах при успехе, None если точка
            недостижима или IK не сошлась за 300 итераций.

        Note:
            Для фактического движения необходимо вызвать ``step()`` после
            этого метода — функция только устанавливает управляющий сигнал.

        Example:
            angles = ctrl.move_to_point(120, 0, 80)
            if angles:
                ctrl.step_seconds(1.5)
            else:
                print("Точка недостижима")
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
        """Перемещает визуальный маркер цели (полупрозрачная сфера) в viewer.

        Маркер — mocap-тело ``target_marker``: не участвует в физике (contype=0),
        отображается только визуально. Удобен для отладки IK и демонстрации.

        Args:
            x_mm: Целевая X в мм (мировая система, вперёд от основания).
            y_mm: Целевая Y в мм.
            z_mm: Целевая Z в мм (высота над столом, прибавляется ``_TABLE_HEIGHT_M``).

        Note:
            Не влияет на физику и не вызывает движения робота.
            Если модель сгенерирована без маркера, вызов игнорируется.
        """
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
        """Разжимает гриппер до максимального раскрытия (20 мм).

        Устанавливает целевые позиции актуаторов ``act_finger_left`` и
        ``act_finger_right`` в 0.02 м. Гриппер физически раскрывается
        в течение нескольких шагов симуляции.

        Note:
            Не выполняет ``step()`` — для анимации движения необходим
            последующий вызов ``step_seconds(0.3)``.
            Безопасно вызывать на моделях без гриппера (игнорируется).
        """
        if not self._has_gripper:
            return
        self.data.ctrl[self._finger_left_id] = 0.02
        self.data.ctrl[self._finger_right_id] = 0.02
        self.gripper_open = True

    def close_gripper(self) -> None:
        """Сжимает гриппер до полного закрытия (0 мм).

        Устанавливает целевые позиции актуаторов ``act_finger_left`` и
        ``act_finger_right`` в 0.0 м. При наличии объекта между пальцами
        физика MuJoCo генерирует контактные силы, удерживающие объект.

        Note:
            Не выполняет ``step()`` — для физического захвата необходим
            последующий вызов ``step_seconds(0.3)``.
            Безопасно вызывать на моделях без гриппера (игнорируется).
        """
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
        """Рендерит кадр с указанной камеры через переиспользуемый рендерер.

        Использует единственный ``mujoco.Renderer``, созданный при инициализации,
        избегая аллокаций на каждый вызов. Если запрошены иные размеры кадра —
        рендерер пересоздаётся один раз и кэшируется.

        Доступные камеры (при ``with_cameras=True``)
        ─────────────────────────────────────────────
        ``top_down``   — вид сверху, высота 0.6 м, fov=60°
        ``front``      — вид спереди (0.5, 0, 0.2), fov=60°
        ``side``       — вид сбоку (0, 0.5, 0.2), fov=60°
        ``eye_in_hand``— камера на гриппере, fov=90° (только при with_gripper=True)

        Args:
            camera_name: Имя камеры в MJCF-модели (default: ``"top_down"``).
            width:  Ширина выходного изображения в пикселях; None = из __init__.
            height: Высота выходного изображения в пикселях; None = из __init__.
            depth:  Если True — возвращает карту глубины вместо RGB.

        Returns:
            RGB: ``np.ndarray`` формы (H, W, 3), dtype uint8, значения 0–255.
            Depth: ``np.ndarray`` формы (H, W), dtype float32, значения в метрах.

        Raises:
            RuntimeError: Если рендерер не удалось инициализировать
                (отсутствует OpenGL/EGL).

        Example:
            rgb   = ctrl.render_camera("eye_in_hand")           # (480, 640, 3)
            depth = ctrl.render_camera("top_down", depth=True)  # (480, 640)
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
        """Формирует полное наблюдение текущего состояния для RL-агента.

        Собирает проприоцептивные данные (углы суставов, позиция EE) и
        экстероцептивные (RGB + Depth изображения, позиции объектов) в один словарь.

        Args:
            camera_name: Имя камеры для RGB/Depth рендеринга (default: ``"eye_in_hand"``).

        Returns:
            Словарь со следующими ключами:

            ======================= ========================= ===================
            Ключ                    Тип                       Описание
            ======================= ========================= ===================
            ``"rgb"``               ndarray (H, W, 3) uint8   RGB с камеры
            ``"depth"``             ndarray (H, W) float32    Глубина в метрах
            ``"joint_angles"``      ndarray (6,) float64      Текущие углы (°)
            ``"ee_pos"``            ndarray (3,) float64      EE позиция (м)
            ``"gripper_open"``      bool                      Состояние гриппера
            ``"object_positions"``  dict[str, ndarray(3)]     Позиции объектов (м)
            ======================= ========================= ===================

        Note:
            ``object_positions`` содержит только те объекты, которые присутствуют
            в модели (зависит от флага ``with_objects`` при генерации MJCF).
            Ключи: ``"red_cube"``, ``"green_cube"``, ``"blue_cylinder"``, ``"yellow_cube"``.
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
        """Выполняет N шагов физической симуляции.

        Каждый шаг продвигает время на ``model.opt.timestep`` (2 мс).
        Актуаторы PD-регуляторов стремятся к целевым углам, установленным
        через ``set_joint_angles()``.

        Args:
            n_steps: Количество шагов (default: 1). Например, 500 шагов = 1 секунда
                при timestep=0.002.

        Note:
            Для отображения анимации в viewer необходимо периодически вызывать
            ``viewer.sync()`` между шагами. Используйте ``step_seconds()`` +
            собственный цикл с viewer.sync() для интерактивных сценариев.
        """
        for _ in range(n_steps):
            mujoco.mj_step(self.model, self.data)

    def step_seconds(self, seconds: float) -> None:
        """Симулирует заданное количество секунд реального времени.

        Вычисляет необходимое количество шагов как ``ceil(seconds / timestep)``
        и вызывает ``step(n)``. Удобно для задания времени ожидания в секундах
        без ручного расчёта числа шагов.

        Args:
            seconds: Длительность симуляции в секундах (вещественное число).

        Example:
            ctrl.set_joint_angles([0, -45, 90, -45, 0, 0])
            ctrl.step_seconds(2.0)  # дать роботу 2 с на достижение позы
        """
        n = max(1, int(seconds / self.model.opt.timestep))
        self.step(n)

    def reset(self) -> None:
        """Сбрасывает симуляцию в начальное состояние.

        Вызывает ``mj_resetData()`` (обнуляет qpos, qvel, ctrl) и
        ``mj_forward()`` (пересчитывает кинематику). Состояние гриппера
        сбрасывается до ``gripper_open=True``, целевые углы — до нулевых.

        Note:
            Не переинициализирует модель — все ID и кэши остаются валидны.
            Для применения нестандартной начальной позы вызовите
            ``set_joint_angles(..., immediate=True)`` сразу после ``reset()``.
        """
        mujoco.mj_resetData(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)
        self.target_angles_deg = [0.0] * 6
        self.gripper_open = True

    # ============================
    # Синхронизация с ST3215
    # ============================

    def connect_real_robot(self, port: str = "COM3") -> bool:
        """Подключается к физическому роботу ST3215 по UART.

        Создаёт экземпляр ``ST3215(device=port)`` и устанавливает
        флаг ``sync_with_real=True``, после чего каждый вызов
        ``set_joint_angles()`` будет дополнительно отправлять команды на
        реальные серводвигатели.

        Args:
            port: Серийный порт устройства (default: ``"COM3"``).
                Linux/Mac: ``"/dev/ttyUSB0"``, ``"/dev/cu.usbserial-0001"``.

        Returns:
            True если соединение установлено успешно, False при ошибке
            (порт недоступен, устройство не отвечает, библиотека st3215
            не установлена).

        Note:
            Требует установленного пакета ``st3215`` (``pip install st3215``).
            При отсутствии пакета всегда возвращает False.
            Скорость порта фиксирована: 1 000 000 бод (RS-485).

        See Also:
            ``disconnect_real_robot()`` — явное отключение.
            ``SimToRealMirror`` — для непрерывного зеркалирования с контролем
            частоты и статистикой.
        """
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
        """Закрывает соединение с реальным роботом и сбрасывает флаг синхронизации.

        Безопасно вызывать даже если соединение не было установлено.
        Автоматически вызывается в ``close()``.
        """
        if self.st3215:
            try:
                if hasattr(self.st3215, "portHandler"):
                    self.st3215.portHandler.closePort()
            except Exception:
                pass
        self.st3215 = None
        self.sync_with_real = False

    def _sync_to_real(self, angles_deg: list[float]) -> None:
        """Отправляет углы симуляции на реальные серводвигатели ST3215.

        Для каждого сустава: конвертирует градусы → позицию 0–4095,
        применяет инверсию (для суставов с inverted=True в маппинге),
        отправляет команду ``ST3215.MoveTo(motor_id, position, speed=100, acc)``.
        Скорость зафиксирована на 100 (медленно, безопасно).

        Для зеркалирования с настраиваемой скоростью используйте
        ``SimToRealMirror`` (mujoco_robot_sim/sim_to_real.py).

        Args:
            angles_deg: Список из 6 углов в градусах (joint_0…joint_5).
        """
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
        """Читает текущие углы с реальных серводвигателей и применяет их в симуляции.

        Для каждого мотора вызывает ``ST3215.ReadPosition(motor_id)``,
        применяет инверсию и конвертирует позицию 0–4095 → градусы.
        Затем вызывает ``set_joint_angles(angles, immediate=True)``, синхронно
        телепортируя симуляцию в текущую позу реального робота.

        Returns:
            Список из 6 углов в градусах при успехе,
            None если реальный робот не подключён.

        Note:
            При ошибке чтения отдельного мотора его угол принимается равным 0°.
            Использование в цикле: см. режим ``real_to_sim`` в ``SimToRealMirror``.
        """
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
        """Выполняет последовательное движение конечного эффектора по маршрутным точкам.

        Для каждой точки: решает IK, задаёт углы, симулирует ``settle_time`` секунд
        для достижения позы, затем выполняет действие гриппера (если задано) и
        добавляет 0.3 с стабилизации гриппера.
        Точки с нерешаемой IK пропускаются с предупреждением в лог.

        Args:
            points_mm: Последовательность точек (x, y, z) в мм. Порядок —
                это порядок выполнения.
            grip_actions: Действия гриппера для каждой точки:
                ``True`` — открыть, ``False`` — закрыть, ``None`` — не менять.
                Если None — гриппер не трогается ни в одной точке.
                Длина должна совпадать с ``points_mm``.
            settle_time: Время симуляции (сек) для достижения каждой точки
                (default: 1.0). Увеличьте для более плавного движения.
            viewer: Экземпляр MuJoCo viewer для обновления отображения.
                Если None — симуляция выполняется в headless режиме.

        Example:
            # Демонстрация pick & place
            ctrl.execute_waypoints(
                points_mm=[(150, 0, 80), (150, 0, 40), (150, 0, 80), (80, 120, 80)],
                grip_actions=[True, False, None, True],
                settle_time=1.5,
                viewer=viewer,
            )
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
    """Gymnasium-совместимая среда обучения с подкреплением для робота ST3215.

    Реализует стандартный интерфейс Gymnasium (ранее OpenAI Gym): ``reset()``,
    ``step()``, ``close()``. Пространство действий — непрерывный вектор из 7
    значений: 6 углов суставов и команда гриппера.

    Пространство действий
    ─────────────────────
    ``action: ndarray(7)``
        ``action[:6]`` — целевые углы суставов в градусах
        ``action[6]``  — гриппер: >0 открыть, ≤0 закрыть

    Пространство наблюдений
    ────────────────────────
    Словарь (см. ``MuJoCoRobotController.get_observation()``):
        ``rgb``              — (H, W, 3) uint8, камера eye_in_hand
        ``depth``            — (H, W) float32, карта глубины
        ``joint_angles``     — (6,) float64, текущие углы (°)
        ``ee_pos``           — (3,) float64, позиция EE (м)
        ``gripper_open``     — bool
        ``object_positions`` — dict с позициями объектов захвата

    Функция награды
    ───────────────
    ``reward = -dist(ee, target_object) + 1.0``  (бонус если объект поднят > 10 см)

    Условие завершения
    ──────────────────
    ``truncated = True`` при достижении ``max_steps=1000`` шагов.
    ``terminated`` всегда False (задача непрерывная).

    Attributes:
        ctrl (MuJoCoRobotController): Внутренний контроллер симуляции.
        target_object (str): Имя целевого объекта (default: ``"red_cube"``).
        target_place (ndarray): Место назначения объекта [x, y, z] в метрах.

    Example:
        env = RobotEnv()
        obs, info = env.reset()
        for _ in range(100):
            action = np.zeros(7)   # нулевые действия
            obs, reward, terminated, truncated, info = env.step(action)
        env.close()
    """

    def __init__(
        self,
        camera_width: int = _DEFAULT_CAMERA_WIDTH,
        camera_height: int = _DEFAULT_CAMERA_HEIGHT,
    ):
        """Инициализирует среду.

        Args:
            camera_width:  Ширина кадра наблюдения (default: 640).
            camera_height: Высота кадра наблюдения (default: 480).
        """
        xml = generate_robot_mjcf()
        self.ctrl = MuJoCoRobotController(
            xml, camera_width=camera_width, camera_height=camera_height
        )
        self.target_object = "red_cube"
        self.target_place = np.array([0.12, -0.08, 0.065])
        self._step_count = 0
        self._max_steps = 1000

    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[dict, dict]:
        """Сбрасывает среду в начальное состояние.

        Вызывает ``ctrl.reset()``, открывает гриппер и устанавливает
        начальную позу ``[0, −30, 60, −30, 0, 0]°``, симулирует 100 шагов
        для стабилизации физики.

        Args:
            seed:    Игнорируется (детерминированная среда). Зарезервирован
                     для совместимости с Gymnasium API.
            options: Игнорируется. Зарезервирован для расширений.

        Returns:
            Кортеж ``(observation, info)`` — словарь наблюдения и пустой info.
        """
        self.ctrl.reset()
        self.ctrl.open_gripper()
        self.ctrl.set_joint_angles([0, -30, 60, -30, 0, 0], immediate=True)
        self.ctrl.step(100)
        self._step_count = 0
        return self.ctrl.get_observation(), {}

    def step(self, action: np.ndarray) -> tuple[dict, float, bool, bool, dict]:
        """Выполняет один шаг среды по заданному действию.

        Применяет угловые команды к суставам и команду гриппера, симулирует
        100 шагов физики (0.2 с), собирает наблюдение и вычисляет награду.

        Args:
            action: ``ndarray`` формы (7,):
                ``action[:6]`` — целевые углы суставов в градусах.
                ``action[6]``  — гриппер: ``>0`` открыть, ``≤0`` закрыть.

        Returns:
            Кортеж ``(observation, reward, terminated, truncated, info)``:

            - ``observation`` — словарь (см. ``get_observation()``).
            - ``reward`` — вещественное число: ``-dist(EE, target) + 1.0`` (бонус).
            - ``terminated`` — всегда False (задача непрерывная).
            - ``truncated`` — True при достижении ``_max_steps=1000`` шагов.
            - ``info`` — ``{"distance": float, "step": int}``.
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
        """Освобождает ресурсы: рендерер и соединение с реальным роботом.

        Эквивалентен выходу из контекстного менеджера.
        """
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
