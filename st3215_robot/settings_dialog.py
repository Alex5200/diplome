#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Settings Dialog for ST3215 Robot
Configure motor limits, kinematics, and visualization
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Dict, Optional
from config_manager import ConfigManager, MotorLimits, KinematicLink


class MotorLimitsFrame(ttk.LabelFrame):
    """Frame for configuring motor limits"""

    def __init__(self, parent, motor_id: int, limits: MotorLimits, **kwargs):
        super().__init__(parent, text=f"Мотор ID: {motor_id}", **kwargs)

        self.motor_id = motor_id
        self.limits = limits

        # Create widgets
        self._create_widgets()

    def _create_widgets(self):
        """Create configuration widgets"""
        # Position limits
        ttk.Label(self, text="Позиция (мин):").grid(
            row=0, column=0, sticky="w", padx=5, pady=2
        )
        self.min_pos = ttk.Spinbox(self, from_=0, to=4095, width=10)
        self.min_pos.set(self.limits.min_position)
        self.min_pos.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(self, text="Позиция (макс):").grid(
            row=1, column=0, sticky="w", padx=5, pady=2
        )
        self.max_pos = ttk.Spinbox(self, from_=0, to=4095, width=10)
        self.max_pos.set(self.limits.max_position)
        self.max_pos.grid(row=1, column=1, padx=5, pady=2)

        # Speed limits
        ttk.Label(self, text="Скорость (мин):").grid(
            row=2, column=0, sticky="w", padx=5, pady=2
        )
        self.min_speed = ttk.Spinbox(self, from_=0, to=3400, width=10)
        self.min_speed.set(self.limits.min_speed)
        self.min_speed.grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(self, text="Скорость (макс):").grid(
            row=3, column=0, sticky="w", padx=5, pady=2
        )
        self.max_speed = ttk.Spinbox(self, from_=0, to=3400, width=10)
        self.max_speed.set(self.limits.max_speed)
        self.max_speed.grid(row=3, column=1, padx=5, pady=2)

        # Temperature
        ttk.Label(self, text="Макс. температура (°C):").grid(
            row=4, column=0, sticky="w", padx=5, pady=2
        )
        self.max_temp = ttk.Spinbox(self, from_=0, to=100, width=10)
        self.max_temp.set(self.limits.max_temperature)
        self.max_temp.grid(row=4, column=1, padx=5, pady=2)

        # Load
        ttk.Label(self, text="Макс. нагрузка (%):").grid(
            row=5, column=0, sticky="w", padx=5, pady=2
        )
        self.max_load = ttk.Spinbox(self, from_=0, to=100, width=10)
        self.max_load.set(self.limits.max_load)
        self.max_load.grid(row=5, column=1, padx=5, pady=2)

        # Current
        ttk.Label(self, text="Макс. ток (mA):").grid(
            row=6, column=0, sticky="w", padx=5, pady=2
        )
        self.max_current = ttk.Spinbox(self, from_=0, to=5000, width=10)
        self.max_current.set(self.limits.max_current)
        self.max_current.grid(row=6, column=1, padx=5, pady=2)

        # Enabled checkbox
        self.enabled_var = tk.BooleanVar(value=self.limits.enabled)
        self.enabled_cb = ttk.Checkbutton(
            self, text="Активен", variable=self.enabled_var
        )
        self.enabled_cb.grid(row=7, column=0, columnspan=2, pady=5)

    def get_limits(self) -> MotorLimits:
        """Get configured limits"""
        return MotorLimits(
            min_position=int(self.min_pos.get()),
            max_position=int(self.max_pos.get()),
            min_speed=int(self.min_speed.get()),
            max_speed=int(self.max_speed.get()),
            max_temperature=float(self.max_temp.get()),
            max_load=float(self.max_load.get()),
            max_current=float(self.max_current.get()),
            enabled=self.enabled_var.get(),
        )


class KinematicLinkFrame(ttk.LabelFrame):
    """Frame for configuring a kinematic link"""

    def __init__(self, parent, link: KinematicLink, **kwargs):
        super().__init__(parent, text=f"Звено {link.link_id}", **kwargs)

        self.link = link

        self._create_widgets()

    def _create_widgets(self):
        """Create widgets"""
        # Alpha
        ttk.Label(self, text="Alpha (rad):").grid(
            row=0, column=0, sticky="w", padx=5, pady=2
        )
        self.alpha = ttk.Entry(self, width=10)
        self.alpha.insert(0, f"{self.link.alpha:.4f}")
        self.alpha.grid(row=0, column=1, padx=5, pady=2)

        # a
        ttk.Label(self, text="a (mm):").grid(
            row=1, column=0, sticky="w", padx=5, pady=2
        )
        self.a = ttk.Entry(self, width=10)
        self.a.insert(0, f"{self.link.a:.1f}")
        self.a.grid(row=1, column=1, padx=5, pady=2)

        # d
        ttk.Label(self, text="d (mm):").grid(
            row=2, column=0, sticky="w", padx=5, pady=2
        )
        self.d = ttk.Entry(self, width=10)
        self.d.insert(0, f"{self.link.d:.1f}")
        self.d.grid(row=2, column=1, padx=5, pady=2)

        # Theta offset
        ttk.Label(self, text="Theta offset (rad):").grid(
            row=3, column=0, sticky="w", padx=5, pady=2
        )
        self.theta_offset = ttk.Entry(self, width=10)
        self.theta_offset.insert(0, f"{self.link.theta_offset:.4f}")
        self.theta_offset.grid(row=3, column=1, padx=5, pady=2)

        # Motor ID
        ttk.Label(self, text="Motor ID:").grid(
            row=4, column=0, sticky="w", padx=5, pady=2
        )
        self.motor_id = ttk.Spinbox(self, from_=0, to=253, width=10)
        self.motor_id.set(self.link.motor_id if self.link.motor_id else 0)
        self.motor_id.grid(row=4, column=1, padx=5, pady=2)

    def get_link(self) -> KinematicLink:
        """Get configured link"""
        return KinematicLink(
            link_id=self.link.link_id,
            alpha=float(self.alpha.get()),
            a=float(self.a.get()),
            d=float(self.d.get()),
            theta_offset=float(self.theta_offset.get()),
            motor_id=int(self.motor_id.get()),
        )


class SettingsDialog(tk.Toplevel):
    """Main settings dialog"""

    def __init__(self, parent, config_manager: ConfigManager):
        super().__init__(parent)

        self.config_mgr = config_manager
        self.title("⚙️ Настройки робота")
        self.geometry("900x700")
        self.minsize(800, 600)

        self.result = False

        self._create_widgets()

        # Modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.wait_window()

    def _create_widgets(self):
        """Create dialog widgets"""
        # Notebook for tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1: Motor Limits
        self.motor_tab = ttk.Frame(notebook)
        notebook.add(self.motor_tab, text="🔧 Пределы моторов")
        self._create_motor_tab()

        # Tab 2: Kinematics
        self.kinematics_tab = ttk.Frame(notebook)
        notebook.add(self.kinematics_tab, text="🦴 Кинематика")
        self._create_kinematics_tab()

        # Tab 3: Visualization
        self.vis_tab = ttk.Frame(notebook)
        notebook.add(self.vis_tab, text="📊 3D Визуализация")
        self._create_visualization_tab()

        # Tab 4: General
        self.general_tab = ttk.Frame(notebook)
        notebook.add(self.general_tab, text="⚙️ Общие")
        self._create_general_tab()

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(btn_frame, text="💾 Сохранить", command=self._save).pack(
            side="right", padx=5
        )
        ttk.Button(btn_frame, text="❌ Отмена", command=self._cancel).pack(
            side="right", padx=5
        )
        ttk.Button(btn_frame, text="🔄 Сбросить", command=self._reset).pack(
            side="right", padx=5
        )

    def _create_motor_tab(self):
        """Create motor limits tab"""
        # Scrollable canvas
        canvas = tk.Canvas(self.motor_tab)
        scrollbar = ttk.Scrollbar(
            self.motor_tab, orient="vertical", command=canvas.yview
        )
        self.motor_scrollable = ttk.Frame(canvas)

        self.motor_scrollable.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.motor_scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Motor limit frames
        self.motor_frames = {}
        motor_limits = self.config_mgr.get_all_motor_limits()

        for mid, limits in sorted(motor_limits.items()):
            frame = MotorLimitsFrame(self.motor_scrollable, mid, limits)
            frame.pack(fill="x", padx=10, pady=5)
            self.motor_frames[mid] = frame

    def _create_kinematics_tab(self):
        """Create kinematics tab"""
        # Scrollable canvas
        canvas = tk.Canvas(self.kinematics_tab)
        scrollbar = ttk.Scrollbar(
            self.kinematics_tab, orient="vertical", command=canvas.yview
        )
        self.kin_scrollable = ttk.Frame(canvas)

        self.kin_scrollable.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.kin_scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Kinematic link frames
        self.kin_frames = {}
        links = self.config_mgr.get_kinematic_links()

        for link in links:
            frame = KinematicLinkFrame(self.kin_scrollable, link)
            frame.pack(fill="x", padx=10, pady=5)
            self.kin_frames[link.link_id] = frame

    def _create_visualization_tab(self):
        """Create visualization settings tab"""
        vis_settings = self.config_mgr.get_visualization_settings()

        # Grid size
        ttk.Label(self.vis_tab, text="Размер сетки (mm):").grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        self.vis_grid_size = ttk.Spinbox(self.vis_tab, from_=100, to=2000, width=15)
        self.vis_grid_size.set(vis_settings["grid_size"])
        self.vis_grid_size.grid(row=0, column=1, padx=10, pady=5)

        # Update interval
        ttk.Label(self.vis_tab, text="Интервал обновления (с):").grid(
            row=1, column=0, sticky="w", padx=10, pady=5
        )
        self.vis_interval = ttk.Spinbox(
            self.vis_tab, from_=0.01, to=1.0, increment=0.01, width=15
        )
        self.vis_interval.set(vis_settings["update_interval"])
        self.vis_interval.grid(row=1, column=1, padx=10, pady=5)

        # Trail length
        ttk.Label(self.vis_tab, text="Длина следа:").grid(
            row=2, column=0, sticky="w", padx=10, pady=5
        )
        self.vis_trail_len = ttk.Spinbox(self.vis_tab, from_=10, to=500, width=15)
        self.vis_trail_len.set(vis_settings["trail_length"])
        self.vis_trail_len.grid(row=2, column=1, padx=10, pady=5)

        # Point size
        ttk.Label(self.vis_tab, text="Размер точек:").grid(
            row=3, column=0, sticky="w", padx=10, pady=5
        )
        self.vis_point_size = ttk.Spinbox(self.vis_tab, from_=10, to=200, width=15)
        self.vis_point_size.set(vis_settings["point_size"])
        self.vis_point_size.grid(row=3, column=1, padx=10, pady=5)

        # Link width
        ttk.Label(self.vis_tab, text="Ширина звеньев:").grid(
            row=4, column=0, sticky="w", padx=10, pady=5
        )
        self.vis_link_width = ttk.Spinbox(self.vis_tab, from_=1, to=20, width=15)
        self.vis_link_width.set(vis_settings["link_width"])
        self.vis_link_width.grid(row=4, column=1, padx=10, pady=5)

        # Show trail
        self.vis_show_trail = tk.BooleanVar(value=vis_settings["show_trail"])
        ttk.Checkbutton(
            self.vis_tab, text="Показывать след", variable=self.vis_show_trail
        ).grid(row=5, column=0, columnspan=2, padx=10, pady=5)

        # Base position
        ttk.Label(self.vis_tab, text="Позиция базы X:").grid(
            row=6, column=0, sticky="w", padx=10, pady=5
        )
        self.base_x = ttk.Entry(self.vis_tab, width=15)
        self.base_x.insert(0, str(vis_settings["base_position"][0]))
        self.base_x.grid(row=6, column=1, padx=10, pady=5)

        ttk.Label(self.vis_tab, text="Позиция базы Y:").grid(
            row=7, column=0, sticky="w", padx=10, pady=5
        )
        self.base_y = ttk.Entry(self.vis_tab, width=15)
        self.base_y.insert(0, str(vis_settings["base_position"][1]))
        self.base_y.grid(row=7, column=1, padx=10, pady=5)

        ttk.Label(self.vis_tab, text="Позиция базы Z:").grid(
            row=8, column=0, sticky="w", padx=10, pady=5
        )
        self.base_z = ttk.Entry(self.vis_tab, width=15)
        self.base_z.insert(0, str(vis_settings["base_position"][2]))
        self.base_z.grid(row=8, column=1, padx=10, pady=5)

    def _create_general_tab(self):
        """Create general settings tab"""
        row = 0

        # Robot name
        ttk.Label(self.general_tab, text="Имя робота:").grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.robot_name = ttk.Entry(self.general_tab, width=40)
        self.robot_name.insert(0, self.config_mgr.config.robot_name)
        self.robot_name.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        # Serial port
        ttk.Label(self.general_tab, text="Порт:").grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.serial_port = ttk.Entry(self.general_tab, width=40)
        self.serial_port.insert(0, self.config_mgr.config.serial_port)
        self.serial_port.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        # Baudrate
        ttk.Label(self.general_tab, text="Baudrate:").grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.baudrate = ttk.Combobox(
            self.general_tab,
            values=[
                "9600",
                "19200",
                "38400",
                "57600",
                "115200",
                "250000",
                "500000",
                "1000000",
            ],
            width=37,
            state="readonly",
        )
        self.baudrate.set(str(self.config_mgr.config.baudrate))
        self.baudrate.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        # Timeout
        ttk.Label(self.general_tab, text="Timeout (с):").grid(
            row=row, column=0, sticky="w", padx=10, pady=5
        )
        self.timeout = ttk.Spinbox(
            self.general_tab, from_=0.1, to=10.0, increment=0.1, width=37
        )
        self.timeout.set(str(self.config_mgr.config.timeout))
        self.timeout.grid(row=row, column=1, padx=10, pady=5)
        row += 1

    def _save(self):
        """Save settings"""
        try:
            # Save motor limits
            for mid, frame in self.motor_frames.items():
                limits = frame.get_limits()
                self.config_mgr.update_motor_limits(mid, limits)

            # Save kinematic links
            for lid, frame in self.kin_frames.items():
                link = frame.get_link()
                self.config_mgr.update_kinematic_link(
                    lid,
                    **{
                        "alpha": link.alpha,
                        "a": link.a,
                        "d": link.d,
                        "theta_offset": link.theta_offset,
                        "motor_id": link.motor_id,
                    },
                )

            # Save visualization settings
            self.config_mgr.config.vis_grid_size = float(self.vis_grid_size.get())
            self.config_mgr.config.vis_update_interval = float(self.vis_interval.get())
            self.config_mgr.config.vis_trail_length = int(self.vis_trail_len.get())
            self.config_mgr.config.vis_point_size = int(self.vis_point_size.get())
            self.config_mgr.config.vis_link_width = int(self.vis_link_width.get())
            self.config_mgr.config.vis_show_trail = self.vis_show_trail.get()
            self.config_mgr.config.base_x = float(self.base_x.get())
            self.config_mgr.config.base_y = float(self.base_y.get())
            self.config_mgr.config.base_z = float(self.base_z.get())

            # Save general settings
            self.config_mgr.config.robot_name = self.robot_name.get()
            self.config_mgr.config.serial_port = self.serial_port.get()
            self.config_mgr.config.baudrate = int(self.baudrate.get())
            self.config_mgr.config.timeout = float(self.timeout.get())

            # Save to file
            if self.config_mgr.save():
                messagebox.showinfo("Успех", "Настройки сохранены!")
                self.result = True
                self.destroy()
            else:
                messagebox.showerror("Ошибка", "Не удалось сохранить настройки")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при сохранении:\n{e}")

    def _cancel(self):
        """Cancel and close"""
        self.result = False
        self.destroy()

    def _reset(self):
        """Reset to defaults"""
        if messagebox.askyesno(
            "Подтверждение", "Сбросить все настройки к значениям по умолчанию?"
        ):
            self.config_mgr.config = None
            self.config_mgr.load()
            self.destroy()
            messagebox.showinfo("Сброс", "Настройки сброшены. Откройте диалог снова.")


def open_settings(parent, config_manager: ConfigManager) -> bool:
    """Open settings dialog"""
    dialog = SettingsDialog(parent, config_manager)
    return dialog.result


if __name__ == "__main__":
    # Test
    root = tk.Tk()
    root.withdraw()

    config_mgr = ConfigManager()
    open_settings(root, config_mgr)

    root.destroy()
