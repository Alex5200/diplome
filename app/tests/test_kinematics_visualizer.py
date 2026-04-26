#!/usr/bin/env python3

"""
Interactive Kinematics Visualizer for Testing
Тестовая визуализация для проверки правильности кинематики с ползунками ST3215
"""

import math
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

# Добавляем родительскую директорию в path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from app.config.constants import (
    FANUC_BG,
    FANUC_GREEN,
    FANUC_PANEL,
    KINEMA_COLORS,
)
from app.models.kinematics import RobotKinematics6DOF


class KinematicsVisualizer:
    """Интерактивная визуализация кинематики с ползунками."""

    JOINT_NAMES = [
        "🏗️ База (J1)",
        "💪 Плечо 1 (J2)",
        "💪 Плечо 2 (J3)",
        "🦾 Локоть (J4)",
        "🖐️ Кисть 1 (J5)",
        "🖐️ Кисть 2 (J6)",
    ]

    def __init__(self):
        """Инициализация визуализатора."""
        self.kinematics = RobotKinematics6DOF()
        self.joint_angles = [0.0] * 6
        self.slider_vars = []

        self._create_window()
        self._create_sliders()
        self._create_display()
        self._create_buttons()
        self._draw_robot()

    def _create_window(self):
        """Создание главного окна."""
        self.root = tk.Tk()
        self.root.title("🤖 ST3215 Kinematics Visualizer")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1a1a2e")

        # Главный контейнер
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def _create_sliders(self):
        """Создание ползунков для каждого сустава."""
        slider_frame = ttk.LabelFrame(
            self.main_frame,
            text="📐 Углы суставов (градусы) - ST3215 (0-4095)",
            padding=10,
        )
        slider_frame.pack(fill="x", padx=10, pady=10)

        for i in range(6):
            frame = ttk.Frame(slider_frame)
            frame.pack(fill="x", pady=5)

            # Название сустава
            name_label = ttk.Label(frame, text=self.JOINT_NAMES[i], width=25, font=("Consolas", 10))
            name_label.pack(side="left", padx=5)

            # Переменная для угла
            var = tk.DoubleVar(value=0.0)
            self.slider_vars.append(var)

            # Ползунок
            slider = ttk.Scale(
                frame,
                from_=-180,
                to=180,
                variable=var,
                orient="horizontal",
                length=400,
                command=lambda v, idx=i: self._on_slider_change(idx),
            )
            slider.pack(side="left", padx=10)

            # Поле ввода угла
            angle_entry = ttk.Spinbox(
                frame,
                from_=-180,
                to=180,
                textvariable=var,
                width=8,
                command=lambda idx=i: self._on_entry_change(idx),
            )
            angle_entry.pack(side="left", padx=5)
            angle_entry.bind("<Return>", lambda e, idx=i: self._on_entry_change(idx))

            # Поле позиции мотора
            pos_label = ttk.Label(
                frame,
                text="POS: 2048",
                width=12,
                font=("Consolas", 9),
                foreground="#00ff88",
            )
            pos_label.pack(side="left", padx=10)
            setattr(self, f"pos_label_{i}", pos_label)

    def _create_display(self):
        """Создание 3D визуализации и дисплея координат."""
        display_frame = ttk.Frame(self.main_frame)
        display_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 3D график
        viz_frame = ttk.LabelFrame(display_frame, text="🔬 3D Визуализация")
        viz_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.figure = plt.Figure(figsize=(8, 6), dpi=100, facecolor=FANUC_BG)
        self.ax = self.figure.add_subplot(111, projection="3d")
        self.ax.set_facecolor(FANUC_PANEL)

        self.canvas = FigureCanvasTkAgg(self.figure, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Панель информации
        info_frame = ttk.LabelFrame(display_frame, text="📊 Координаты суставов")
        info_frame.pack(side="right", fill="y", padx=10, pady=10)

        # Текстовая информация
        self.info_text = tk.Text(
            info_frame,
            width=35,
            height=25,
            bg="#16213e",
            fg="#ffffff",
            font=("Consolas", 9),
        )
        self.info_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Скроллбар
        scrollbar = ttk.Scrollbar(info_frame, orient="vertical", command=self.info_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.info_text.configure(yscrollcommand=scrollbar.set)

    def _create_buttons(self):
        """Создание кнопок управления."""
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(btn_frame, text="🔄 Обновить", command=self._update_visualization).pack(
            side="left", padx=5
        )

        ttk.Button(btn_frame, text="🏠 Сброс (0°)", command=self._reset_angles).pack(
            side="left", padx=5
        )

        ttk.Button(btn_frame, text="🎯 Центр (2048)", command=self._center_positions).pack(
            side="left", padx=5
        )

        ttk.Button(btn_frame, text="📋 Копировать координаты", command=self._copy_coordinates).pack(
            side="left", padx=5
        )

        ttk.Button(btn_frame, text="❌ Выход", command=self.root.quit).pack(side="right", padx=5)

    def _on_slider_change(self, idx):
        """Обработка изменения ползунка."""
        try:
            angle = self.slider_vars[idx].get()
            self.joint_angles[idx] = angle
            self._update_position_display(idx)
            self._draw_robot()
            self._update_info()
        except Exception as e:
            print(f"Error in slider change: {e}")

    def _on_entry_change(self, idx):
        """Обработка ввода в поле угла."""
        try:
            angle = self.slider_vars[idx].get()
            # Ограничение диапазона
            angle = max(-180, min(180, angle))
            self.slider_vars[idx].set(angle)
            self.joint_angles[idx] = angle
            self._update_position_display(idx)
            self._draw_robot()
            self._update_info()
        except Exception as e:
            print(f"Error in entry change: {e}")

    def _update_position_display(self, idx):
        """Обновление отображения позиции мотора."""
        angle = self.joint_angles[idx]
        position = RobotKinematics6DOF.angle_to_motor_position(angle)
        label = getattr(self, f"pos_label_{idx}")
        label.configure(text=f"POS: {position}")

    def _update_visualization(self):
        """Обновление визуализации из ползунков."""
        for i in range(6):
            self.joint_angles[i] = self.slider_vars[i].get()
            self._update_position_display(i)
        self._draw_robot()
        self._update_info()

    def _reset_angles(self):
        """Сброс всех углов к нулю."""
        for i in range(6):
            self.slider_vars[i].set(0.0)
            self.joint_angles[i] = 0.0
            self._update_position_display(i)
        self._draw_robot()
        self._update_info()

    def _center_positions(self):
        """Установка всех позиций в центр (2048)."""
        for i in range(6):
            self.slider_vars[i].set(0.0)
            self.joint_angles[i] = 0.0
            self._update_position_display(i)
        self._draw_robot()
        self._update_info()

    def _copy_coordinates(self):
        """Копирование координат в буфер обмена."""
        positions = self.kinematics.get_all_joint_positions(self.joint_angles)
        end_pos = self.kinematics.get_end_effector_position(self.joint_angles)

        text = "Координаты суставов (мм):\n"
        text += "База:     (0.0, 0.0, 0.0)\n"
        for i, pos in enumerate(positions[1:], 1):
            text += f"J{i}:       ({pos[0]:7.1f}, {pos[1]:7.1f}, {pos[2]:7.1f})\n"
        text += f"\nИнструмент: ({end_pos[0]:7.1f}, {end_pos[1]:7.1f}, {end_pos[2]:7.1f})\n"
        text += f"\nУглы: {self.joint_angles}"

        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _draw_robot(self):
        """Отрисовка 3D модели робота."""
        if not hasattr(self, "ax") or not hasattr(self, "figure") or not hasattr(self, "canvas"):
            return

        self.ax.clear()
        self.ax.set_facecolor(FANUC_PANEL)

        # Расчет позиций через кинематическую модель
        joint_positions = self.kinematics.get_all_joint_positions(self.joint_angles)

        x_points = [p[0] for p in joint_positions]
        y_points = [p[1] for p in joint_positions]
        z_points = [p[2] for p in joint_positions]

        # Настройка осей
        max_reach = self.kinematics.get_total_reach()
        self.ax.set_xlim(-max_reach, max_reach)
        self.ax.set_ylim(-max_reach, max_reach)
        self.ax.set_zlim(-max_reach / 2, max_reach + 50)
        self.ax.set_xlabel("X (мм)", color="white")
        self.ax.set_ylabel("Y (мм)", color="white")
        self.ax.set_zlabel("Z (мм)", color="white")
        self.ax.set_title(f"Робот ST3215 (Reach={max_reach}мм)", color="white", fontsize=12)

        # Стиль осей
        self.ax.xaxis.pane.fill = False
        self.ax.yaxis.pane.fill = False
        self.ax.zaxis.pane.fill = False
        self.ax.xaxis.pane.set_edgecolor("#666666")
        self.ax.yaxis.pane.set_edgecolor("#666666")
        self.ax.zaxis.pane.set_edgecolor("#666666")
        self.ax.tick_params(colors="white")

        # Отрисовка линий робота
        self.ax.plot(
            x_points,
            y_points,
            z_points,
            color=FANUC_GREEN,
            linewidth=3,
            marker="o",
            markersize=8,
        )

        # Отрисовка суставов
        for i, (x, y, z) in enumerate(zip(x_points, y_points, z_points)):
            color = KINEMA_COLORS[i % len(KINEMA_COLORS)]
            self.ax.scatter([x], [y], [z], color=color, s=150, edgecolors="white", linewidth=1)

            # Подпись сустава
            label = f"J{i}" if i > 0 else "Base"
            self.ax.text(x, y, z + 5, label, color="white", fontsize=8)

        # Позиция инструмента
        end_pos = self.kinematics.get_end_effector_position(self.joint_angles)
        self.ax.scatter(
            [end_pos[0]],
            [end_pos[1]],
            [end_pos[2]],
            color="red",
            s=200,
            marker="x",
            linewidth=3,
        )

        # Линия от последнего сустава к инструменту
        if joint_positions:
            last_pos = joint_positions[-1]
            self.ax.plot(
                [last_pos[0], end_pos[0]],
                [last_pos[1], end_pos[1]],
                [last_pos[2], end_pos[2]],
                color="red",
                linewidth=2,
                linestyle="--",
            )

        self.figure.tight_layout()
        self.canvas.draw()

    def _update_info(self):
        """Обновление информационной панели."""
        positions = self.kinematics.get_all_joint_positions(self.joint_angles)
        end_pos = self.kinematics.get_end_effector_position(self.joint_angles)
        orientation = self.kinematics.get_end_effector_orientation(self.joint_angles)

        self.info_text.delete("1.0", tk.END)

        # Углы и позиции моторов
        self.info_text.insert(tk.END, "=== УГЛЫ И ПОЗИЦИИ ===\n\n")
        for i in range(6):
            angle = self.joint_angles[i]
            pos = RobotKinematics6DOF.angle_to_motor_position(angle)
            name = self.JOINT_NAMES[i].split("(")[0].strip()
            self.info_text.insert(tk.END, f"{name}: {angle:+6.1f}° | POS: {pos:4d}\n", f"joint{i}")

        # Координаты суставов
        self.info_text.insert(tk.END, "\n=== КООРДИНАТЫ (мм) ===\n\n")
        self.info_text.insert(tk.END, f"{'База':<10} (  0.0,   0.0,   0.0)\n")
        for i, pos in enumerate(positions[1:], 1):
            self.info_text.insert(
                tk.END,
                f"{'J' + str(i):<10} ({pos[0]:6.1f}, {pos[1]:6.1f}, {pos[2]:6.1f})\n",
            )

        # Позиция инструмента
        self.info_text.insert(tk.END, "\n=== ИНСТРУМЕНТ ===\n\n")
        self.info_text.insert(
            tk.END,
            f"Position: ({end_pos[0]:6.1f}, {end_pos[1]:6.1f}, {end_pos[2]:6.1f}) мм\n",
        )

        # Ориентация (Euler углы)
        roll, pitch, yaw = orientation
        self.info_text.insert(
            tk.END,
            f"Orientation:\n"
            f"  Roll:  {math.degrees(roll):6.1f}°\n"
            f"  Pitch: {math.degrees(pitch):6.1f}°\n"
            f"  Yaw:   {math.degrees(yaw):6.1f}°\n",
        )

        # Расстояние от базы
        distance = math.sqrt(end_pos[0] ** 2 + end_pos[1] ** 2 + end_pos[2] ** 2)
        self.info_text.insert(
            tk.END,
            f"\nDistance from base: {distance:.1f} мм\n"
            f"Max reach: {self.kinematics.get_total_reach():.1f} мм\n",
        )

    def run(self):
        """Запуск приложения."""
        print("🚀 Запуск Kinematics Visualizer...")
        print(
            f"Длины звеньев: L0={self.kinematics.L0}, L1={self.kinematics.L1}, "
            f"L2={self.kinematics.L2}, L3={self.kinematics.L3}, "
            f"L4={self.kinematics.L4}, L5={self.kinematics.L5} мм"
        )
        print(f"Максимальная досягаемость: {self.kinematics.get_total_reach()} мм")
        self.root.mainloop()


def main():
    """Точка входа."""
    print("\n" + "=" * 70)
    print("🤖 ST3215 Kinematics Visualizer")
    print("=" * 70)
    print("\nДлины звеньев (мм):")
    print("  L0 (База)       = 19")
    print("  L1 (Плечо 1)    = 134")
    print("  L2 (Плечо 2)    = 95")
    print("  L3 (Локоть)     = 34")
    print("  L4 (Запястье 1) = 35")
    print("  L5 (Запястье 2) = 0")
    print("\nМаксимальная досягаемость: 317 мм")
    print("\n" + "=" * 70)
    print("\nИнструкция:")
    print("  • Двигайте ползунки для изменения углов суставов")
    print("  • Диапазон: -180° до +180° (позиции 0-4095)")
    print("  • Наблюдайте за изменением координат в реальном времени")
    print("  • Кнопка 'Копировать координаты' для экспорта данных")
    print("=" * 70 + "\n")

    app = KinematicsVisualizer()
    app.run()


if __name__ == "__main__":
    main()
