#!/usr/bin/env python3
"""
Main Window — CustomTkinter edition.
Robot Control GUI — ST3215 / FANUC-style logic, modern CTk appearance.
"""

import json
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
import matplotlib.pyplot as plt

from app.config.constants import (
    BASE_WINDOW_HEIGHT,
    BASE_WINDOW_WIDTH,
    DEFAULT_SPEED,
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    FANUC_TEXT2,
    JOG_MODE_CARTESIAN,
    JOG_MODE_JOINT,
    MAX_POSITION,
    MAX_SCALE_PERCENT,
    MIN_SCALE_PERCENT,
    MONITOR_INTERVAL,
    SPEED_OVERRIDE_DEFAULT,
    SPEED_OVERRIDE_MAX,
    SPEED_OVERRIDE_MIN,
    TEXT_COLOR,
    WINDOW_SCALE_PERCENT,
)
from app.controllers import MotorController, MotorMonitor
from app.models.kinematics import InverseKinematics6DOF, RobotKinematics6DOF
from app.utils.config_manager import ConfigManager
from app.utils.logger import AppLogger
from app.utils.program_executor import ProgramExecutor
from app.views.ai_control_panel import AIControlPanel
from app.views.block_programming import BlockPalette, ProgramCanvas
from app.views.bottom_monitor_panel import BottomMonitorPanel
from app.views.kinematics_3d_panel import Kinematics3DPanel
from app.views.manual_control_panel import ManualControlPanel
from app.views.motor_mapping_panel import MotorMappingPanel
from app.views.vision_tracker_panel import VisionTrackerPanel

# ── Palette ──────────────────────────────────────────────────────────────────
_ACCENT = "#7dd3c0"
_ACCENT_H = "#5bb8a4"
_BORDER = "#e8e4e0"
_CARD_BG = FANUC_PANEL


def _card(parent, title: str = "", title_color: str = _ACCENT, **kw) -> ctk.CTkFrame:
    """Titled card frame helper."""
    card = ctk.CTkFrame(
        parent, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER, **kw
    )
    if title:
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=title_color,
            anchor="w",
        ).pack(anchor="w", padx=12, pady=(8, 2))
    return card


def _sep_h(parent):
    ctk.CTkFrame(parent, fg_color=_BORDER, height=1, corner_radius=0).pack(fill="x")


# ─────────────────────────────────────────────────────────────────────────────
#  Status Bar
# ─────────────────────────────────────────────────────────────────────────────
class FANUCStatusBar(ctk.CTkFrame):
    """Top status strip — mode | speed% | coord | program status | clock."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=FANUC_BG, height=36, corner_radius=0, **kwargs)
        self.pack_propagate(False)
        _F = ctk.CTkFont

        self.mode_label = ctk.CTkLabel(
            self,
            text="JOINT",
            font=_F("Segoe UI", 11, "bold"),
            text_color=_ACCENT,
            fg_color=FANUC_BG,
        )
        self.mode_label.pack(side="left", padx=(12, 4))
        self._sep()

        self.speed_pct_label = ctk.CTkLabel(
            self,
            text="50%",
            font=_F("Consolas", 11, "bold"),
            text_color=FANUC_ORANGE,
            fg_color=FANUC_BG,
        )
        self.speed_pct_label.pack(side="left", padx=6)
        self._sep()

        self.coord_label = ctk.CTkLabel(
            self,
            text="WORLD",
            font=_F("Consolas", 10),
            text_color=FANUC_BLUE,
            fg_color=FANUC_BG,
        )
        self.coord_label.pack(side="left", padx=6)
        self._sep()

        self.prog_status_label = ctk.CTkLabel(
            self,
            text="IDLE",
            font=_F("Consolas", 10),
            text_color=FANUC_GRAY,
            fg_color=FANUC_BG,
        )
        self.prog_status_label.pack(side="left", padx=6)

        # Right side
        self.clock_label = ctk.CTkLabel(
            self,
            text="00:00:00",
            font=_F("Consolas", 10),
            text_color=FANUC_GRAY,
            fg_color=FANUC_BG,
        )
        self.clock_label.pack(side="right", padx=12)

        self.cycle_label = ctk.CTkLabel(
            self,
            text="CYCLE: 0",
            font=_F("Consolas", 10),
            text_color=FANUC_GRAY,
            fg_color=FANUC_BG,
        )
        self.cycle_label.pack(side="right", padx=6)

        # Connection dot (tiny canvas — pixel-perfect circle)
        self.conn_canvas = tk.Canvas(
            self,
            width=12,
            height=12,
            bg=FANUC_BG,
            highlightthickness=0,
        )
        self.conn_canvas.pack(side="right", padx=6)
        self.set_connected(False)
        self._update_clock()

    def _sep(self):
        ctk.CTkFrame(self, fg_color=FANUC_GRAY, width=1, corner_radius=0).pack(
            side="left",
            fill="y",
            padx=4,
            pady=6,
        )

    def _update_clock(self):
        self.clock_label.configure(text=time.strftime("%H:%M:%S"))
        self.after(1000, self._update_clock)

    def set_mode(self, mode: str):
        self.mode_label.configure(text=mode.upper())

    def set_speed_pct(self, pct: int):
        color = _ACCENT if pct >= 50 else FANUC_ORANGE if pct >= 20 else FANUC_RED
        self.speed_pct_label.configure(text=f"{pct}%", text_color=color)

    def set_prog_status(self, status: str):
        colors = {
            "IDLE": FANUC_GRAY,
            "RUN": _ACCENT,
            "PAUSE": FANUC_ORANGE,
            "ABORT": FANUC_RED,
            "DONE": FANUC_BLUE,
        }
        self.prog_status_label.configure(text=status, text_color=colors.get(status, FANUC_TEXT))

    def set_connected(self, connected: bool):
        self.conn_canvas.delete("all")
        self.conn_canvas.create_oval(
            1,
            1,
            11,
            11,
            fill=_ACCENT if connected else FANUC_RED,
            outline="",
        )

    def set_cycle(self, count: int):
        self.cycle_label.configure(text=f"CYCLE: {count}")


# ─────────────────────────────────────────────────────────────────────────────
#  Position Register Panel
# ─────────────────────────────────────────────────────────────────────────────
class PositionRegisterPanel(ctk.CTkFrame):
    def __init__(self, parent, controller, kinematics, log_callback):
        super().__init__(parent, fg_color=FANUC_BG, corner_radius=0)
        self.controller = controller
        self.kinematics = kinematics
        self.ik_solver = InverseKinematics6DOF(kinematics)
        self.log = log_callback
        self.registers: dict[int, dict] = {}
        self._create_widgets()

    def _create_widgets(self):
        main = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # Header + buttons
        hdr = ctk.CTkFrame(
            main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER
        )
        hdr.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            hdr,
            text="POSITION REGISTERS (PR)",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=_ACCENT,
        ).pack(side="left", padx=14, pady=10)

        for txt, cmd, fg, hov in [
            ("RECORD", self._record_current, _ACCENT, _ACCENT_H),
            ("MOVE TO", self._move_to_selected, FANUC_BLUE, "#6a94d8"),
            ("DELETE", self._delete_selected, FANUC_RED, "#c07065"),
            ("CLEAR ALL", self._clear_all, FANUC_ORANGE, "#d4995a"),
        ]:
            ctk.CTkButton(
                hdr,
                text=txt,
                fg_color=fg,
                hover_color=hov,
                text_color=FANUC_TEXT,
                width=90,
                height=30,
                corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 9, "bold"),
                command=cmd,
            ).pack(side="right", padx=3, pady=8)

        # Manual XYZ input
        xyz_card = _card(main, "MANUAL INPUT (XYZ mm)")
        xyz_card.pack(fill="x", pady=(0, 10))

        xyz_row = ctk.CTkFrame(xyz_card, fg_color=_CARD_BG, corner_radius=0)
        xyz_row.pack(fill="x", padx=12, pady=8)

        self.xyz_vars = {}
        for i, (label, color) in enumerate([("X", FANUC_RED), ("Y", _ACCENT), ("Z", FANUC_BLUE)]):
            ctk.CTkLabel(
                xyz_row,
                text=f"{label}:",
                font=ctk.CTkFont("Consolas", 12, "bold"),
                text_color=color,
            ).grid(row=0, column=i * 2, padx=(10, 2))
            var = tk.DoubleVar(value=0.0)
            self.xyz_vars[label.lower()] = var
            ttk.Spinbox(
                xyz_row,
                from_=-400,
                to=400,
                textvariable=var,
                width=8,
                increment=5.0,
                font=("Consolas", 11),
            ).grid(row=0, column=i * 2 + 1, padx=(2, 10))

        ctk.CTkButton(
            xyz_row,
            text="CALC IK + RECORD",
            fg_color="#b8a8f8",
            hover_color="#8878d8",
            text_color=FANUC_TEXT,
            width=140,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            command=self._record_from_xyz,
        ).grid(row=0, column=6, padx=10)

        # Treeview
        tree_frame = ctk.CTkFrame(
            main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER
        )
        tree_frame.pack(fill="both", expand=True, pady=(0, 6))

        columns = ("pr", "j1", "j2", "j3", "j4", "j5", "j6", "x", "y", "z", "comment")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=14)
        widths = {
            "pr": 50,
            "j1": 65,
            "j2": 65,
            "j3": 65,
            "j4": 65,
            "j5": 65,
            "j6": 65,
            "x": 70,
            "y": 70,
            "z": 70,
            "comment": 150,
        }
        titles = {
            "pr": "PR#",
            "j1": "J1",
            "j2": "J2",
            "j3": "J3",
            "j4": "J4",
            "j5": "J5",
            "j6": "J6",
            "x": "X mm",
            "y": "Y mm",
            "z": "Z mm",
            "comment": "Comment",
        }
        for col in columns:
            self.tree.heading(col, text=titles[col])
            self.tree.column(col, width=widths[col], anchor="center")

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))

        self.status_label = ctk.CTkLabel(
            main,
            text="0 registers",
            font=ctk.CTkFont("Segoe UI", 9),
            text_color=FANUC_GRAY,
            anchor="w",
        )
        self.status_label.pack(fill="x")

    # ── Logic (unchanged from original) ──────────────────────────────────────
    def _get_current_angles(self) -> list[float]:
        angles = []
        for j in range(6):
            mid = self.controller.get_motor_id_for_joint(j)
            pos = self.controller.joint_positions.get(mid, 2048)
            angles.append(round((pos / MAX_POSITION) * 360 - 180, 1))
        return angles

    def _next_pr_index(self) -> int:
        return (max(self.registers.keys()) + 1) if self.registers else 1

    def _record_current(self):
        angles = self._get_current_angles()
        pos = self.kinematics.get_end_effector_position(angles)
        pr_idx = self._next_pr_index()
        self.registers[pr_idx] = {
            "angles": angles,
            "xyz": [round(pos[0], 1), round(pos[1], 1), round(pos[2], 1)],
            "comment": f"Recorded {time.strftime('%H:%M:%S')}",
        }
        self._refresh_table()
        self.log(f"PR[{pr_idx}] recorded: {angles}", "success")

    def _record_from_xyz(self):
        x, y, z = self.xyz_vars["x"].get(), self.xyz_vars["y"].get(), self.xyz_vars["z"].get()
        result = self.ik_solver.solve(x, y, z)
        if result is None:
            self.log(f"IK failed for ({x}, {y}, {z})", "error")
            messagebox.showerror("IK Error", f"Point ({x}, {y}, {z}) is unreachable!")
            return
        angles = [round(a, 1) for a in result]
        pr_idx = self._next_pr_index()
        self.registers[pr_idx] = {
            "angles": angles,
            "xyz": [round(x, 1), round(y, 1), round(z, 1)],
            "comment": f"IK ({x:.0f},{y:.0f},{z:.0f})",
        }
        self._refresh_table()
        self.log(f"PR[{pr_idx}] from IK: ({x},{y},{z}) -> {angles}", "success")

    def _move_to_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a register first!")
            return
        pr_idx = int(self.tree.item(sel[0])["values"][0])
        if pr_idx not in self.registers:
            return
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return
        for i, angle in enumerate(self.registers[pr_idx]["angles"]):
            position = max(0, min(MAX_POSITION, int((angle + 180) / 360 * MAX_POSITION)))
            motor_id = self.controller.get_motor_id_for_joint(i)
            self.controller.move_to_position(motor_id, position)
        self.log(f"Moving to PR[{pr_idx}]", "info")

    def _delete_selected(self):
        sel = self.tree.selection()
        if sel:
            self.registers.pop(int(self.tree.item(sel[0])["values"][0]), None)
            self._refresh_table()

    def _clear_all(self):
        if messagebox.askyesno("Confirm", "Clear all position registers?"):
            self.registers.clear()
            self._refresh_table()
            self.log("All registers cleared", "warning")

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for pr_idx in sorted(self.registers):
            reg = self.registers[pr_idx]
            a = reg["angles"]
            xyz = reg.get("xyz", [0, 0, 0])
            self.tree.insert(
                "",
                "end",
                values=(
                    pr_idx,
                    f"{a[0]:.1f}",
                    f"{a[1]:.1f}",
                    f"{a[2]:.1f}",
                    f"{a[3]:.1f}",
                    f"{a[4]:.1f}",
                    f"{a[5]:.1f}",
                    f"{xyz[0]:.1f}",
                    f"{xyz[1]:.1f}",
                    f"{xyz[2]:.1f}",
                    reg.get("comment", ""),
                ),
            )
        self.status_label.configure(text=f"{len(self.registers)} registers")

    def save_registers(self, filename: str):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in self.registers.items()}, f, indent=2)

    def load_registers(self, filename: str):
        with open(filename, encoding="utf-8") as f:
            self.registers = {int(k): v for k, v in json.load(f).items()}
        self._refresh_table()


# ─────────────────────────────────────────────────────────────────────────────
#  Teach Pendant Panel
# ─────────────────────────────────────────────────────────────────────────────
class TeachPendantPanel(ctk.CTkFrame):
    def __init__(self, parent, controller, kinematics, log_callback):
        super().__init__(parent, fg_color=FANUC_BG, corner_radius=0)
        self.controller = controller
        self.kinematics = kinematics
        self.log = log_callback
        self.teach_points: list[dict] = []
        self.is_playing = False
        self._stop_flag = False
        self._create_widgets()

    def _create_widgets(self):
        main = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # Header
        hdr = ctk.CTkFrame(
            main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER
        )
        hdr.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            hdr, text="TEACH PENDANT", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=_ACCENT
        ).pack(side="left", padx=14, pady=10)

        # Controls card
        ctrl_card = _card(main, "CONTROLS")
        ctrl_card.pack(fill="x", pady=(0, 10))

        btn_row = ctk.CTkFrame(ctrl_card, fg_color=_CARD_BG, corner_radius=0)
        btn_row.pack(fill="x", padx=10, pady=(4, 0))

        for txt, cmd, fg, hov in [
            ("TEACH POINT", self._teach_point, _ACCENT, _ACCENT_H),
            ("PLAY ALL", self._play_all, FANUC_BLUE, "#6a94d8"),
            ("PLAY ONCE", self._play_once, "#b8a8f8", "#8878d8"),
            ("STOP", self._stop_play, FANUC_RED, "#c07065"),
            ("CLEAR ALL", self._clear_all, FANUC_ORANGE, "#d4995a"),
        ]:
            ctk.CTkButton(
                btn_row,
                text=txt,
                fg_color=fg,
                hover_color=hov,
                text_color=FANUC_TEXT,
                height=34,
                corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                command=cmd,
            ).pack(side="left", padx=3, pady=8)

        # Settings row
        settings_row = ctk.CTkFrame(ctrl_card, fg_color=_CARD_BG, corner_radius=0)
        settings_row.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            settings_row,
            text="Delay (s):",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=FANUC_TEXT2,
        ).pack(side="left", padx=5)
        self.delay_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(
            settings_row,
            from_=0.1,
            to=10.0,
            textvariable=self.delay_var,
            width=6,
            increment=0.1,
            font=("Consolas", 10),
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            settings_row, text="Loops:", font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2
        ).pack(side="left", padx=(20, 5))
        self.loop_var = tk.IntVar(value=1)
        ttk.Spinbox(
            settings_row,
            from_=1,
            to=100,
            textvariable=self.loop_var,
            width=5,
            font=("Consolas", 10),
        ).pack(side="left", padx=5)

        self.play_status = ctk.CTkLabel(
            settings_row,
            text="IDLE",
            font=ctk.CTkFont("Consolas", 10, "bold"),
            text_color=FANUC_GRAY,
        )
        self.play_status.pack(side="right", padx=10)

        # Treeview
        tree_card = ctk.CTkFrame(
            main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER
        )
        tree_card.pack(fill="both", expand=True, pady=(0, 8))

        columns = ("idx", "j1", "j2", "j3", "j4", "j5", "j6", "x", "y", "z")
        self.tree = ttk.Treeview(tree_card, columns=columns, show="headings", height=12)
        for col in columns:
            title = "#" if col == "idx" else col.upper()
            self.tree.heading(col, text=title)
            self.tree.column(col, width=50 if col == "idx" else 75, anchor="center")
        self.tree.tag_configure("active", background=_ACCENT, foreground=FANUC_TEXT)

        sb = ttk.Scrollbar(tree_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))

        # Bottom row
        bot = ctk.CTkFrame(main, fg_color=FANUC_BG, corner_radius=0)
        bot.pack(fill="x", pady=4)
        ctk.CTkButton(
            bot,
            text="DELETE SELECTED",
            fg_color=FANUC_RED,
            hover_color="#c07065",
            text_color=FANUC_TEXT,
            height=30,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            command=self._delete_selected,
        ).pack(side="left")
        self.count_label = ctk.CTkLabel(
            bot, text="0 points", font=ctk.CTkFont("Segoe UI", 9), text_color=FANUC_GRAY
        )
        self.count_label.pack(side="right")

    # ── Logic ─────────────────────────────────────────────────────────────────
    def _get_current_state(self) -> dict:
        angles = []
        for j in range(6):
            mid = self.controller.get_motor_id_for_joint(j)
            pos = self.controller.joint_positions.get(mid, 2048)
            angles.append(round((pos / MAX_POSITION) * 360 - 180, 1))
        xyz = self.kinematics.get_end_effector_position(angles)
        return {"angles": angles, "xyz": [round(v, 1) for v in xyz]}

    def _teach_point(self):
        state = self._get_current_state()
        self.teach_points.append(state)
        self._refresh_table()
        self.log(f"Taught point #{len(self.teach_points)}: {state['angles']}", "success")

    def _play_all(self):
        if not self.teach_points:
            messagebox.showwarning("Warning", "No taught points!")
            return
        self._stop_flag = False
        self.is_playing = True
        threading.Thread(target=self._play_thread, args=(self.loop_var.get(),), daemon=True).start()

    def _play_once(self):
        if not self.teach_points:
            messagebox.showwarning("Warning", "No taught points!")
            return
        self._stop_flag = False
        self.is_playing = True
        threading.Thread(target=self._play_thread, args=(1,), daemon=True).start()

    def _play_thread(self, loops: int):
        self.after(0, lambda: self.play_status.configure(text="RUNNING", text_color=_ACCENT))
        delay = self.delay_var.get()
        for _ in range(loops):
            if self._stop_flag:
                break
            for i, point in enumerate(self.teach_points):
                if self._stop_flag:
                    break
                self.after(0, lambda idx=i: self._highlight_row(idx))
                for j, angle in enumerate(point["angles"]):
                    position = max(0, min(MAX_POSITION, int((angle + 180) / 360 * MAX_POSITION)))
                    self.controller.move_to_position(
                        self.controller.get_motor_id_for_joint(j), position
                    )
                time.sleep(delay)
        self.is_playing = False
        self.after(0, lambda: self.play_status.configure(text="DONE", text_color=FANUC_BLUE))

    def _stop_play(self):
        self._stop_flag = True
        self.is_playing = False
        self.play_status.configure(text="STOPPED", text_color=FANUC_RED)

    def _highlight_row(self, idx: int):
        for item in self.tree.get_children():
            self.tree.item(item, tags=())
        items = self.tree.get_children()
        if idx < len(items):
            self.tree.item(items[idx], tags=("active",))
            self.tree.see(items[idx])

    def _delete_selected(self):
        sel = self.tree.selection()
        if sel:
            idx = int(self.tree.item(sel[0])["values"][0]) - 1
            if 0 <= idx < len(self.teach_points):
                self.teach_points.pop(idx)
                self._refresh_table()

    def _clear_all(self):
        if messagebox.askyesno("Confirm", "Clear all taught points?"):
            self.teach_points.clear()
            self._refresh_table()

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for i, pt in enumerate(self.teach_points):
            a = pt["angles"]
            xyz = pt.get("xyz", [0, 0, 0])
            self.tree.insert(
                "",
                "end",
                values=(
                    i + 1,
                    f"{a[0]:.1f}",
                    f"{a[1]:.1f}",
                    f"{a[2]:.1f}",
                    f"{a[3]:.1f}",
                    f"{a[4]:.1f}",
                    f"{a[5]:.1f}",
                    f"{xyz[0]:.1f}",
                    f"{xyz[1]:.1f}",
                    f"{xyz[2]:.1f}",
                ),
            )
        self.count_label.configure(text=f"{len(self.teach_points)} points")


# ─────────────────────────────────────────────────────────────────────────────
#  Alarm History Panel
# ─────────────────────────────────────────────────────────────────────────────
class AlarmHistoryPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=FANUC_BG, corner_radius=0)
        self.alarms: list[dict] = []
        self._create_widgets()

    def _create_widgets(self):
        hdr = ctk.CTkFrame(self, fg_color=_CARD_BG, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(
            hdr,
            text="ALARM HISTORY",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=FANUC_RED,
        ).pack(side="left", padx=12, pady=8)
        ctk.CTkButton(
            hdr,
            text="CLEAR",
            fg_color=FANUC_ORANGE,
            hover_color="#d4995a",
            text_color=FANUC_TEXT,
            width=70,
            height=28,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            command=self._clear,
        ).pack(side="right", padx=10, pady=8)

        columns = ("time", "level", "message")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        self.tree.heading("time", text="Time")
        self.tree.heading("level", text="Level")
        self.tree.heading("message", text="Message")
        self.tree.column("time", width=100)
        self.tree.column("level", width=80)
        self.tree.column("message", width=500)
        self.tree.tag_configure("error", foreground=FANUC_RED)
        self.tree.tag_configure("warning", foreground=FANUC_ORANGE)
        self.tree.tag_configure("info", foreground=FANUC_TEXT)

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        sb.pack(side="right", fill="y", pady=10, padx=(0, 6))

    def add_alarm(self, level: str, message: str):
        ts = time.strftime("%H:%M:%S")
        self.alarms.insert(0, {"time": ts, "level": level, "message": message})
        if len(self.alarms) > 500:
            self.alarms = self.alarms[:500]
        tag = "error" if level == "ERROR" else "warning" if level == "WARNING" else "info"
        self.tree.insert("", 0, values=(ts, level, message), tags=(tag,))

    def _clear(self):
        self.alarms.clear()
        self.tree.delete(*self.tree.get_children())


# ─────────────────────────────────────────────────────────────────────────────
#  Main Window
# ─────────────────────────────────────────────────────────────────────────────
class RobotControlGUI(ctk.CTk):
    """Main application window — CustomTkinter."""

    def __init__(self):
        super().__init__()
        self.title("ST3215 Robot Control v8.0 — CustomTkinter")

        # ── Window sizing ─────────────────────────────────────────────────────
        sw = self.winfo_screenwidth()
        scale_pct = max(MIN_SCALE_PERCENT, min(MAX_SCALE_PERCENT, (sw / BASE_WINDOW_WIDTH) * 100))
        final_scale = (scale_pct / 100) * (WINDOW_SCALE_PERCENT / 100)
        w = int(BASE_WINDOW_WIDTH * final_scale)
        h = int(BASE_WINDOW_HEIGHT * final_scale)
        self.geometry(f"{w}x{h}")
        self.minsize(
            int(BASE_WINDOW_WIDTH * MIN_SCALE_PERCENT / 100),
            int(BASE_WINDOW_HEIGHT * MIN_SCALE_PERCENT / 100),
        )

        self.configure(fg_color=FANUC_BG)

        # ── Core components ───────────────────────────────────────────────────
        self.controller = MotorController()
        self.monitor: MotorMonitor | None = None
        self.logger = AppLogger("robot_gui")
        self.config_manager = ConfigManager()
        self.program_executor: ProgramExecutor | None = None
        self.kinematics = RobotKinematics6DOF()

        # ── Panel references ──────────────────────────────────────────────────
        self.motor_mapping_panel: MotorMappingPanel | None = None
        self.manual_panel: ManualControlPanel | None = None
        self.bottom_monitor: BottomMonitorPanel | None = None
        self.kinematics_panel: Kinematics3DPanel | None = None
        self.program_canvas: ProgramCanvas | None = None
        self.block_palette: BlockPalette | None = None
        self.position_register_panel: PositionRegisterPanel | None = None
        self.teach_panel: TeachPendantPanel | None = None
        self.alarm_panel: AlarmHistoryPanel | None = None
        self.fanuc_status_bar: FANUCStatusBar | None = None

        # ── State ─────────────────────────────────────────────────────────────
        self._monitor_update_pending = False
        self.speed_override = SPEED_OVERRIDE_DEFAULT
        self.jog_mode = JOG_MODE_JOINT
        self.cycle_count = 0

        self.tool_x_var = tk.StringVar(value="0.00")
        self.tool_y_var = tk.StringVar(value="0.00")
        self.tool_z_var = tk.StringVar(value="0.00")
        self.tool_rx_var = tk.StringVar(value="0.00")
        self.tool_ry_var = tk.StringVar(value="0.00")
        self.tool_rz_var = tk.StringVar(value="0.00")

        self._setup_ttk_styles()
        self._create_widgets()
        self._create_menu()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._bind_keyboard_shortcuts()

        self._log("ST3215 Robot Control v8.0 started", "success")
        self.controller.load_config()

    # ── TTK styles (Treeview / Spinbox — CTk doesn't cover these) ─────────────
    def _setup_ttk_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(
            "Treeview",
            background=_CARD_BG,
            foreground=FANUC_TEXT,
            rowheight=26,
            fieldbackground=_CARD_BG,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        s.configure(
            "Treeview.Heading",
            background=FANUC_BG,
            foreground=FANUC_TEXT,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )
        s.map("Treeview", background=[("selected", _ACCENT)], foreground=[("selected", FANUC_TEXT)])
        s.configure(
            "TSpinbox",
            fieldbackground=_CARD_BG,
            foreground=FANUC_TEXT,
            bordercolor=_BORDER,
            arrowcolor=FANUC_TEXT2,
        )
        s.configure(
            "TScrollbar",
            background="#e8e4e0",
            troughcolor=FANUC_BG,
            arrowcolor=FANUC_TEXT2,
            relief="flat",
            width=10,
        )
        s.map("TScrollbar", background=[("active", _ACCENT)])
        s.configure("TPanedwindow", background=FANUC_BG)

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _create_menu(self):
        menubar = tk.Menu(self, bg=_CARD_BG, fg=FANUC_TEXT, relief="flat")
        self.configure(menu=menubar)  # CTk supports standard tk.Menu

        def _m(label, items):
            m = tk.Menu(menubar, tearoff=0, bg=_CARD_BG, fg=FANUC_TEXT)
            menubar.add_cascade(label=label, menu=m)
            for item in items:
                if item is None:
                    m.add_separator()
                else:
                    m.add_command(**item)
            return m

        _m(
            "File",
            [
                dict(label="Save Config", command=self._save_config, accelerator="Ctrl+S"),
                dict(label="Load Config", command=self._load_config),
                None,
                dict(label="Export Registers…", command=self._export_registers),
                dict(label="Import Registers…", command=self._import_registers),
                None,
                dict(label="Exit", command=self._on_closing),
            ],
        )
        _m(
            "Robot",
            [
                dict(label="Connect", command=self._toggle_connection),
                dict(label="Scan Servos", command=self._scan_servos),
                None,
                dict(label="All Home (0)", command=self._go_all_home),
                dict(label="All Center (2048)", command=self._go_all_center),
                None,
                dict(label="E-STOP", command=self._emergency_stop, accelerator="Escape"),
            ],
        )
        _m(
            "Program",
            [
                dict(label="Run", command=self._run_program, accelerator="F5"),
                dict(label="Stop", command=self._stop_program),
                None,
                dict(label="Save Program", command=self._save_program),
                dict(label="Load Program", command=self._load_program),
                dict(label="Clear Program", command=self._clear_program),
            ],
        )
        _m(
            "View",
            [
                dict(label="Jog Mode: Joint", command=lambda: self._set_jog_mode(JOG_MODE_JOINT)),
                dict(
                    label="Jog Mode: Cartesian",
                    command=lambda: self._set_jog_mode(JOG_MODE_CARTESIAN),
                ),
            ],
        )
        _m(
            "Help",
            [
                dict(label="Keyboard Shortcuts", command=self._show_shortcuts),
                dict(label="About", command=self._show_about),
            ],
        )

    # ── Main layout ───────────────────────────────────────────────────────────
    def _create_widgets(self):
        # Top status bar
        self.fanuc_status_bar = FANUCStatusBar(self)
        self.fanuc_status_bar.pack(fill="x")
        ctk.CTkFrame(self, fg_color=_BORDER, height=1, corner_radius=0).pack(fill="x")

        # Bottom fixed area: motor monitor + log
        bottom = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        bottom.pack(side="bottom", fill="x", padx=4, pady=(0, 4))

        self.bottom_monitor = BottomMonitorPanel(bottom, self.controller)
        self.bottom_monitor.pack(fill="x", pady=(0, 2))

        ctk.CTkFrame(bottom, fg_color=_BORDER, height=1, corner_radius=0).pack(fill="x")

        log_card = _card(bottom, "LOG")
        log_card.pack(fill="x", pady=(2, 0))
        self._create_log_panel(log_card)

        # Main content
        content = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        content.pack(fill="both", expand=True)

        self.sidebar = self._create_sidebar(content)
        self.sidebar.pack(side="left", fill="y", padx=(4, 0), pady=4)

        right = ctk.CTkFrame(content, fg_color=FANUC_BG, corner_radius=0)
        right.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        # CTkTabview (replaces ttk.Notebook)
        self.tabview = ctk.CTkTabview(
            right,
            fg_color=_CARD_BG,
            segmented_button_fg_color="#e8e4e0",
            segmented_button_selected_color=_ACCENT,
            segmented_button_selected_hover_color=_ACCENT_H,
            segmented_button_unselected_color="#e8e4e0",
            segmented_button_unselected_hover_color="#d0ccc8",
            text_color=FANUC_TEXT,
            text_color_disabled=FANUC_GRAY,
            corner_radius=10,
            border_width=1,
            border_color=_BORDER,
        )
        self.tabview.pack(fill="both", expand=True)

        self.main_tab = self.tabview.add("Dashboard")
        self.manual_tab = self.tabview.add("Jog")
        self.kinematics_tab = self.tabview.add("3D View")
        self.pr_tab = self.tabview.add("Registers")
        self.teach_tab = self.tabview.add("Teach")
        self.block_tab = self.tabview.add("Program")
        self.mapping_tab = self.tabview.add("Setup")
        self.coord_tab = self.tabview.add("XYZ")
        self.alarm_tab = self.tabview.add("Alarms")
        self.vision_tab = self.tabview.add("AI Vision")
        self.ai_control_tab = self.tabview.add("AI Control")

        self._create_dashboard_tab()

        self.manual_panel = ManualControlPanel(
            self.manual_tab, self.controller, self._log, self._on_manual_update
        )
        self.manual_panel.pack(fill="both", expand=True)

        self.kinematics_panel = Kinematics3DPanel(self.kinematics_tab, self.controller, self._log)
        self.kinematics_panel.pack(fill="both", expand=True)

        self.position_register_panel = PositionRegisterPanel(
            self.pr_tab, self.controller, self.kinematics, self._log
        )
        self.position_register_panel.pack(fill="both", expand=True)

        self.teach_panel = TeachPendantPanel(
            self.teach_tab, self.controller, self.kinematics, self._log
        )
        self.teach_panel.pack(fill="both", expand=True)

        self._create_block_tab()

        self.motor_mapping_panel = MotorMappingPanel(self.mapping_tab, self.controller, self._log)
        self.motor_mapping_panel.pack(fill="both", expand=True)

        self._create_coordinates_tab()

        self.alarm_panel = AlarmHistoryPanel(self.alarm_tab)
        self.alarm_panel.pack(fill="both", expand=True)

        self.vision_panel = VisionTrackerPanel(
            self.vision_tab,
            robot_service=self.controller,
            kinematics_service=self.kinematics,
            log_callback=self._log,
        )
        self.vision_panel.pack(fill="both", expand=True)

        self.ai_control_panel = AIControlPanel(
            self.ai_control_tab,
            robot_service=self.controller,
            kinematics_service=self.kinematics,
            log_callback=self._log,
        )
        self.ai_control_panel.pack(fill="both", expand=True)

        self._refresh_ports()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _create_sidebar(self, parent) -> ctk.CTkFrame:
        sidebar = ctk.CTkFrame(
            parent,
            fg_color=_CARD_BG,
            width=64,
            corner_radius=10,
            border_width=1,
            border_color=_BORDER,
        )
        sidebar.pack_propagate(False)

        _BTN = dict(width=48, height=32, corner_radius=8, font=ctk.CTkFont("Segoe UI", 8, "bold"))

        for txt, fg, hov, cmd, tip in [
            ("CON", FANUC_BLUE, "#6a94d8", self._toggle_connection, "Connect / Disconnect"),
            ("SCN", FANUC_ORANGE, "#d4995a", self._scan_servos, "Scan servos"),
            ("HOM", _ACCENT, _ACCENT_H, self._go_all_home, "All joints → 0"),
            ("CTR", "#b8a8f8", "#8878d8", self._go_all_center, "All joints → 2048"),
            ("TRQ", _ACCENT, _ACCENT_H, self._torque_all_on, "Torque ON"),
            ("FRE", FANUC_ORANGE, "#d4995a", self._torque_all_off, "Torque OFF"),
        ]:
            b = ctk.CTkButton(
                sidebar,
                text=txt,
                fg_color=fg,
                hover_color=hov,
                text_color=FANUC_TEXT,
                command=cmd,
                **_BTN,
            )
            b.pack(pady=3, padx=8)
            self._add_tooltip(b, tip)

        ctk.CTkFrame(sidebar, fg_color=_BORDER, height=1, corner_radius=0).pack(
            fill="x", pady=8, padx=8
        )

        estop = ctk.CTkButton(
            sidebar,
            text="STOP",
            fg_color="#cc0000",
            hover_color="#ff0000",
            text_color="white",
            command=self._emergency_stop,
            **_BTN,
        )
        estop.pack(pady=3, padx=8)
        self._add_tooltip(estop, "EMERGENCY STOP  (Esc)")

        ctk.CTkFrame(sidebar, fg_color=_BORDER, height=1, corner_radius=0).pack(
            fill="x", pady=8, padx=8
        )

        ctk.CTkLabel(
            sidebar, text="SPD", font=ctk.CTkFont("Segoe UI", 7, "bold"), text_color=FANUC_ORANGE
        ).pack()

        self.speed_override_var = tk.IntVar(value=SPEED_OVERRIDE_DEFAULT)
        ctk.CTkSlider(
            sidebar,
            from_=SPEED_OVERRIDE_MIN,
            to=SPEED_OVERRIDE_MAX,
            variable=self.speed_override_var,
            orientation="vertical",
            height=110,
            width=16,
            button_color=FANUC_ORANGE,
            button_hover_color="#d4995a",
            progress_color=FANUC_ORANGE,
            fg_color="#e8e4e0",
            command=self._on_speed_override_change,
        ).pack(padx=8, pady=2)

        self.speed_pct_sidebar = ctk.CTkLabel(
            sidebar,
            text="50%",
            font=ctk.CTkFont("Consolas", 8, "bold"),
            text_color=FANUC_ORANGE,
        )
        self.speed_pct_sidebar.pack()

        return sidebar

    @staticmethod
    def _add_tooltip(widget, text: str):
        tip = None

        def show(e):
            nonlocal tip
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{e.x_root + 15}+{e.y_root + 10}")
            tk.Label(
                tip,
                text=text,
                bg="#ffffcc",
                fg=FANUC_TEXT,
                font=("Segoe UI", 9),
                relief="solid",
                bd=1,
                padx=4,
                pady=2,
            ).pack()

        def hide(e):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    # ── Dashboard Tab ─────────────────────────────────────────────────────────
    def _create_dashboard_tab(self):
        main = ctk.CTkScrollableFrame(
            self.main_tab,
            fg_color=FANUC_BG,
            corner_radius=0,
            scrollbar_button_color=_ACCENT,
            scrollbar_button_hover_color=_ACCENT_H,
        )
        main.pack(fill="both", expand=True, padx=12, pady=8)

        # Status card
        status_card = _card(main)
        status_card.pack(fill="x", pady=(0, 10))

        status_inner = ctk.CTkFrame(status_card, fg_color=_CARD_BG, corner_radius=0)
        status_inner.pack(fill="x", padx=10, pady=8)

        # Connection dot
        self.connection_indicator = tk.Canvas(
            status_inner, width=22, height=22, bg=_CARD_BG, highlightthickness=0
        )
        self.connection_indicator.pack(side="left", padx=10)
        self._draw_connection_indicator("disconnected")

        self.status_label = ctk.CTkLabel(
            status_inner,
            text="DISCONNECTED",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=FANUC_ORANGE,
        )
        self.status_label.pack(side="left", padx=6)

        # Axis indicators
        self.axis_indicators = {}
        ax_frame = ctk.CTkFrame(status_inner, fg_color=_CARD_BG, corner_radius=0)
        ax_frame.pack(side="left", padx=20)
        for i in range(6):
            ind = tk.Canvas(ax_frame, width=26, height=26, bg=_CARD_BG, highlightthickness=0)
            ind.pack(side="left", padx=3)
            self._draw_axis_indicator(ind, i, "inactive")
            self.axis_indicators[i] = ind

        # Connection settings
        conn_card = _card(main, "CONNECTION")
        conn_card.pack(fill="x", pady=(0, 10))

        port_row = ctk.CTkFrame(conn_card, fg_color=_CARD_BG, corner_radius=0)
        port_row.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            port_row, text="COM Port:", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=_ACCENT
        ).pack(side="left", padx=5)

        self.port_combo = ttk.Combobox(port_row, width=22, font=("Segoe UI", 11))
        self.port_combo.pack(side="left", padx=5)

        ctk.CTkButton(
            port_row,
            text="REFRESH",
            fg_color=FANUC_GRAY,
            hover_color="#6a6560",
            text_color=FANUC_TEXT,
            width=80,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            command=self._refresh_ports,
        ).pack(side="left", padx=5)

        self.connect_btn = ctk.CTkButton(
            port_row,
            text="CONNECT",
            fg_color=FANUC_BLUE,
            hover_color="#6a94d8",
            text_color=FANUC_TEXT,
            width=110,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._toggle_connection,
        )
        self.connect_btn.pack(side="left", padx=10)

        self.scan_btn = ctk.CTkButton(
            port_row,
            text="SCAN SERVOS",
            fg_color=FANUC_ORANGE,
            hover_color="#d4995a",
            text_color=FANUC_TEXT,
            width=120,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            state="disabled",
            command=self._scan_servos,
        )
        self.scan_btn.pack(side="left", padx=5)

        # Quick actions
        quick_card = _card(main, "QUICK ACTIONS")
        quick_card.pack(fill="x", pady=(0, 10))

        qa_row = ctk.CTkFrame(quick_card, fg_color=_CARD_BG, corner_radius=0)
        qa_row.pack(fill="x", padx=10, pady=10)

        for txt, cmd, fg, hov in [
            ("ALL HOME (0)", self._go_all_home, FANUC_BLUE, "#6a94d8"),
            ("ALL CENTER (2048)", self._go_all_center, _ACCENT, _ACCENT_H),
            ("TORQUE ON", self._torque_all_on, _ACCENT, _ACCENT_H),
            ("TORQUE OFF", self._torque_all_off, FANUC_ORANGE, "#d4995a"),
            ("E-STOP", self._emergency_stop, "#cc0000", "#ff0000"),
        ]:
            ctk.CTkButton(
                qa_row,
                text=txt,
                fg_color=fg,
                hover_color=hov,
                text_color=FANUC_TEXT,
                height=36,
                corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                command=cmd,
            ).pack(side="left", padx=4)

        # Tool position
        pos_card = _card(main, "TOOL POSITION (mm)")
        pos_card.pack(fill="x", pady=(0, 10))

        pos_inner = ctk.CTkFrame(pos_card, fg_color=_CARD_BG, corner_radius=0)
        pos_inner.pack(fill="x", padx=10, pady=8)

        self.dash_coord_labels: dict[str, ctk.CTkLabel] = {}
        for label, var_name, color in [
            ("X", "tool_x_var", FANUC_RED),
            ("Y", "tool_y_var", _ACCENT),
            ("Z", "tool_z_var", FANUC_BLUE),
            ("Rx", "tool_rx_var", FANUC_ORANGE),
            ("Ry", "tool_ry_var", "#E040FB"),
            ("Rz", "tool_rz_var", "#FFD600"),
        ]:
            ctk.CTkLabel(
                pos_inner,
                text=f"{label}:",
                font=ctk.CTkFont("Consolas", 12, "bold"),
                text_color=color,
            ).pack(side="left", padx=(12, 2))
            lbl = ctk.CTkLabel(
                pos_inner,
                text="0.00",
                font=ctk.CTkFont("Consolas", 13, "bold"),
                text_color=FANUC_TEXT,
                fg_color="#f0ece8",
                corner_radius=4,
                width=70,
                height=28,
            )
            lbl.pack(side="left", padx=(0, 8))
            self.dash_coord_labels[label] = lbl

        # Joint positions
        joints_card = _card(main, "JOINT POSITIONS")
        joints_card.pack(fill="x")

        jt_inner = ctk.CTkFrame(joints_card, fg_color=_CARD_BG, corner_radius=0)
        jt_inner.pack(fill="x", padx=10, pady=8)

        self.dash_joint_labels: dict[int, ctk.CTkLabel] = {}
        for i in range(6):
            ctk.CTkLabel(
                jt_inner,
                text=f"J{i + 1}:",
                font=ctk.CTkFont("Consolas", 11, "bold"),
                text_color=_ACCENT,
            ).pack(side="left", padx=(12, 2))
            lbl = ctk.CTkLabel(
                jt_inner,
                text="0.0",
                font=ctk.CTkFont("Consolas", 12),
                text_color=FANUC_TEXT,
                fg_color="#f0ece8",
                corner_radius=4,
                width=70,
                height=26,
            )
            lbl.pack(side="left", padx=(0, 6))
            self.dash_joint_labels[i] = lbl

    # ── Block Programming Tab ─────────────────────────────────────────────────
    def _create_block_tab(self):
        paned = ttk.PanedWindow(self.block_tab, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        canvas_frame = ctk.CTkFrame(paned, fg_color=FANUC_BG, corner_radius=0)
        paned.add(canvas_frame, weight=3)

        self.program_canvas = ProgramCanvas(canvas_frame)
        sb = ctk.CTkScrollbar(
            canvas_frame,
            command=self.program_canvas.yview,
            button_color=_ACCENT,
            button_hover_color=_ACCENT_H,
        )
        self.program_canvas.configure(yscrollcommand=sb.set)
        self.program_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        palette_frame = ctk.CTkFrame(paned, fg_color=FANUC_BG, corner_radius=0, width=210)
        paned.add(palette_frame, weight=1)
        self.block_palette = BlockPalette(palette_frame, self.program_canvas)
        self.block_palette.pack(fill="both", expand=True)

        # Action bar
        btn_bar = ctk.CTkFrame(self.block_tab, fg_color=FANUC_BG, corner_radius=0)
        btn_bar.pack(fill="x", padx=5, pady=(0, 5))

        for txt, cmd, fg, hov in [
            ("RUN", self._run_program, _ACCENT, _ACCENT_H),
            ("STOP", self._stop_program, FANUC_RED, "#c07065"),
            ("CLEAR", self._clear_program, FANUC_ORANGE, "#d4995a"),
            ("SAVE", self._save_program, FANUC_BLUE, "#6a94d8"),
            ("LOAD", self._load_program, FANUC_GRAY, "#6a6560"),
        ]:
            ctk.CTkButton(
                btn_bar,
                text=txt,
                fg_color=fg,
                hover_color=hov,
                text_color=FANUC_TEXT,
                width=72,
                height=32,
                corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                command=cmd,
            ).pack(side="left", padx=3)

    # ── Coordinates Tab ───────────────────────────────────────────────────────
    def _create_coordinates_tab(self):
        frame = ctk.CTkFrame(self.coord_tab, fg_color=FANUC_BG, corner_radius=0)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        linear_card = _card(frame, "LINEAR COORDINATES (mm)")
        linear_card.pack(fill="x", padx=10, pady=10)
        for lbl, var, color in [
            ("X:", self.tool_x_var, FANUC_RED),
            ("Y:", self.tool_y_var, _ACCENT),
            ("Z:", self.tool_z_var, FANUC_BLUE),
        ]:
            self._coord_row(linear_card, lbl, var, color)

        angular_card = _card(frame, "ORIENTATION (deg)")
        angular_card.pack(fill="x", padx=10, pady=10)
        for lbl, var, color in [
            ("Rx:", self.tool_rx_var, FANUC_ORANGE),
            ("Ry:", self.tool_ry_var, "#E040FB"),
            ("Rz:", self.tool_rz_var, "#FFD600"),
        ]:
            self._coord_row(angular_card, lbl, var, color)

        btn_row = ctk.CTkFrame(frame, fg_color=FANUC_BG, corner_radius=0)
        btn_row.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(
            btn_row,
            text="REFRESH",
            fg_color=FANUC_BLUE,
            hover_color="#6a94d8",
            text_color=FANUC_TEXT,
            width=90,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._update_tool_coordinates,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            btn_row,
            text="ZERO",
            fg_color=FANUC_ORANGE,
            hover_color="#d4995a",
            text_color=FANUC_TEXT,
            width=90,
            height=34,
            corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._reset_tool_coordinates,
        ).pack(side="left", padx=5)

    @staticmethod
    def _coord_row(parent, label: str, variable: tk.StringVar, color: str):
        row = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=0)
        row.pack(fill="x", padx=12, pady=5)
        ctk.CTkLabel(
            row, text=label, font=ctk.CTkFont("Consolas", 13, "bold"), text_color=color, width=40
        ).pack(side="left", padx=10)
        ctk.CTkLabel(
            row,
            textvariable=variable,
            font=ctk.CTkFont("Consolas", 17, "bold"),
            text_color=FANUC_TEXT,
            fg_color="#f0ece8",
            corner_radius=6,
            width=160,
            height=34,
        ).pack(side="left", padx=10, fill="x", expand=True)

    # ── Log Panel ─────────────────────────────────────────────────────────────
    def _create_log_panel(self, parent):
        self.log_text = ctk.CTkTextbox(
            parent,
            height=60,
            font=ctk.CTkFont("Consolas", 9),
            fg_color="#0e0e18",
            text_color=FANUC_TEXT,
            corner_radius=6,
            state="disabled",
        )
        self.log_text.pack(fill="x", padx=8, pady=(2, 4))

        # Tag colours via underlying tk.Text
        inner = self.log_text._textbox
        inner.tag_configure("info", foreground="#c8c8d8")
        inner.tag_configure("warning", foreground=FANUC_ORANGE)
        inner.tag_configure("error", foreground=FANUC_RED)
        inner.tag_configure("success", foreground=_ACCENT)

        btn_row = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=0)
        btn_row.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkButton(
            btn_row,
            text="CLEAR LOG",
            fg_color="#6a6560",
            hover_color="#4a4540",
            text_color="white",
            width=80,
            height=24,
            corner_radius=6,
            font=ctk.CTkFont("Segoe UI", 8, "bold"),
            command=self._clear_log,
        ).pack(side="right")

    # ── Logging ───────────────────────────────────────────────────────────────
    def _log(self, message: str, level: str = "info"):
        if not hasattr(self, "log_text"):
            return
        ts = time.strftime("%H:%M:%S")
        tag = level if level in ("info", "warning", "error", "success") else "info"
        self.log_text.configure(state="normal")
        self.log_text._textbox.insert("end", f"[{ts}] {message}\n", (tag,))
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
        if level in ("error", "warning") and self.alarm_panel:
            self.alarm_panel.add_alarm("ERROR" if level == "error" else "WARNING", message)
        getattr(self.logger, level, self.logger.info)(message)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ── Connection ────────────────────────────────────────────────────────────
    def _refresh_ports(self):
        try:
            import serial.tools.list_ports

            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.port_combo["values"] = ports
            if ports:
                self.port_combo.current(0)
        except Exception:
            pass

    def _toggle_connection(self):
        if self.controller.connected:
            self._disconnect()
        else:
            port = self.port_combo.get()
            if not port:
                messagebox.showwarning("Warning", "Select a COM port!")
                return
            self._connect(port)

    def _connect(self, port: str):
        self.controller.device = port
        if self.controller.connect():
            self._log(f"Connected to {port}", "success")
            self.status_label.configure(text="CONNECTED", text_color=_ACCENT)
            self.connect_btn.configure(text="DISCONNECT", fg_color=FANUC_RED, hover_color="#c07065")
            self.scan_btn.configure(state="normal")
            self._draw_connection_indicator("connected")
            self.fanuc_status_bar.set_connected(True)
        else:
            self._log(f"Failed to connect to {port}", "error")

    def _disconnect(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
        self.controller.disconnect()
        self._log("Disconnected", "info")
        self.status_label.configure(text="DISCONNECTED", text_color=FANUC_ORANGE)
        self.connect_btn.configure(text="CONNECT", fg_color=FANUC_BLUE, hover_color="#6a94d8")
        self.scan_btn.configure(state="disabled")
        self._draw_connection_indicator("disconnected")
        self.fanuc_status_bar.set_connected(False)
        for j in range(6):
            if j in self.axis_indicators:
                self._draw_axis_indicator(self.axis_indicators[j], j, "inactive")

    def _draw_connection_indicator(self, state: str):
        self.connection_indicator.delete("all")
        color = _ACCENT if state == "connected" else FANUC_GRAY
        self.connection_indicator.create_oval(2, 2, 20, 20, fill=color, outline="white", width=1)

    def _draw_axis_indicator(self, canvas: tk.Canvas, axis: int, state: str):
        canvas.delete("all")
        colors = {"active": _ACCENT, "inactive": FANUC_GRAY, "warning": FANUC_ORANGE}
        color = colors.get(state, FANUC_GRAY)
        canvas.create_oval(2, 2, 24, 24, fill=color, outline="white", width=1)
        canvas.create_text(13, 13, text=f"J{axis + 1}", fill="white", font=("Consolas", 7, "bold"))

    def _update_axis_indicators(self, motor_data_dict):
        for j in range(6):
            mid = self.controller.get_motor_id_for_joint(j)
            state = "inactive"
            if mid in motor_data_dict:
                d = motor_data_dict[mid]
                if d.position is not None:
                    state = (
                        "warning" if (d.is_overheating() or (d.load and d.load > 80)) else "active"
                    )
            if j in self.axis_indicators:
                self._draw_axis_indicator(self.axis_indicators[j], j, state)

    # ── Scanning & Monitoring ─────────────────────────────────────────────────
    def _scan_servos(self):
        self._log("Scanning servos…", "info")
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        servos = self.controller.scan_servos()
        self.after(0, lambda: self._on_scan_complete(servos))

    def _on_scan_complete(self, servos):
        if servos:
            self._log(f"Found servos: {servos}", "success")
            self._start_monitoring(servos)
        else:
            self._log("No servos found", "warning")

    def _start_monitoring(self, motor_ids):
        self.monitor = MotorMonitor(self.controller, None)
        self.monitor.start(motor_ids)
        self._schedule_monitor_update()

    def _schedule_monitor_update(self):
        if self.monitor and self.monitor.running:
            try:
                self._on_monitor_update(self.monitor.get_all_data())
            except Exception as e:
                self._log(f"Monitor error: {e}", "warning")
            self.after(int(MONITOR_INTERVAL * 1000), self._schedule_monitor_update)

    def _on_monitor_update(self, motor_data_dict):
        if self._monitor_update_pending:
            return
        self._monitor_update_pending = True
        try:
            if self.bottom_monitor:
                self.bottom_monitor.update_data(motor_data_dict)
            self._update_axis_indicators(motor_data_dict)
            if self.manual_panel:
                self.manual_panel.update_from_monitor(motor_data_dict)
            if self.motor_mapping_panel:
                self.motor_mapping_panel.update_positions(motor_data_dict)
            if self.kinematics_panel:
                self.kinematics_panel.update_from_monitor(motor_data_dict)
            self._update_tool_coordinates()
            self._update_dashboard_joints()
        except Exception as e:
            self._log(f"GUI update error: {e}", "warning")
        finally:
            self._monitor_update_pending = False

    def _on_manual_update(self):
        pass

    # ── Speed Override ────────────────────────────────────────────────────────
    def _on_speed_override_change(self, value):
        pct = int(float(value))
        speed = int(DEFAULT_SPEED * pct / 100)
        self.speed_override = pct
        self.controller.set_manual_speed(speed)
        self.speed_pct_sidebar.configure(text=f"{pct}%")
        self.fanuc_status_bar.set_speed_pct(pct)

    def _set_jog_mode(self, mode: str):
        self.jog_mode = mode
        self.fanuc_status_bar.set_mode(mode.upper())
        self._log(f"Jog mode: {mode}", "info")

    # ── Quick Actions ─────────────────────────────────────────────────────────
    def _emergency_stop(self):
        if self.controller.connected:
            self.controller.emergency_stop_all()
        self._log("EMERGENCY STOP ACTIVATED", "error")
        self.fanuc_status_bar.set_prog_status("ABORT")

    def _go_all_home(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return
        if messagebox.askyesno("Confirm", "Move all joints to 0?"):
            threading.Thread(
                target=lambda: [
                    self.controller.move_to_position(self.controller.get_motor_id_for_joint(j), 0)
                    for j in range(6)
                ],
                daemon=True,
            ).start()
            self._log("All joints → 0", "info")

    def _go_all_center(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return
        if messagebox.askyesno("Confirm", "Move all joints to center (2048)?"):
            threading.Thread(
                target=lambda: [
                    self.controller.move_to_position(
                        self.controller.get_motor_id_for_joint(j), 2048
                    )
                    for j in range(6)
                ],
                daemon=True,
            ).start()
            self._log("All joints → 2048", "info")

    def _torque_all_on(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return
        for j in range(6):
            self.controller.toggle_torque(self.controller.get_motor_id_for_joint(j), True)
        self._log("All torque ON", "success")

    def _torque_all_off(self):
        if not self.controller.connected:
            messagebox.showwarning("Warning", "Connect first!")
            return
        for j in range(6):
            self.controller.toggle_torque(self.controller.get_motor_id_for_joint(j), False)
        self._log("All torque OFF", "warning")

    # ── Program Execution ─────────────────────────────────────────────────────
    def _run_program(self):
        program = self.program_canvas.get_program() if self.program_canvas else []
        if not program:
            messagebox.showwarning("Warning", "Program is empty!")
            return
        self._log(f"Running program ({len(program)} blocks)", "success")
        self.fanuc_status_bar.set_prog_status("RUN")
        threading.Thread(target=self._execute_program, args=(program,), daemon=True).start()

    def _execute_program(self, program):
        for block in program:
            params = block.get("params", {})
            block_type = params.get("type", "")
            if block_type == "move_to":
                self.controller.move_joint(params.get("joint", 0), params.get("position", 2048))
            elif block_type == "home":
                for i in range(6):
                    self.controller.move_joint(i, 0)
            elif block_type == "wait_time":
                time.sleep(params.get("seconds", 1.0))
            elif block_type == "torque_on":
                self.controller.toggle_torque(
                    self.controller.get_motor_id_for_joint(params.get("joint", 0)), True
                )
            elif block_type == "torque_off":
                self.controller.toggle_torque(
                    self.controller.get_motor_id_for_joint(params.get("joint", 0)), False
                )
        self.cycle_count += 1
        self.after(0, lambda: self.fanuc_status_bar.set_cycle(self.cycle_count))
        self.after(0, lambda: self.fanuc_status_bar.set_prog_status("DONE"))
        self._log("Program completed", "success")

    def _stop_program(self):
        if self.program_executor:
            self.program_executor.stop()
        self.fanuc_status_bar.set_prog_status("ABORT")
        self._log("Program stopped", "warning")

    def _clear_program(self):
        if self.program_canvas:
            self.program_canvas.clear_all()
        self._log("Program cleared", "info")

    # ── Config & File ─────────────────────────────────────────────────────────
    def _save_config(self):
        if self.controller.save_config():
            self._log("Config saved", "success")

    def _load_config(self):
        if self.controller.load_config():
            self._log("Config loaded", "success")
            if self.motor_mapping_panel:
                self.motor_mapping_panel._load_current_mapping()

    def _save_program(self):
        if self.program_canvas:
            with open("robot_program.json", "w") as f:
                json.dump(self.program_canvas.get_program(), f, indent=2)
            self._log("Program saved", "success")

    def _load_program(self):
        try:
            with open("robot_program.json") as f:
                program = json.load(f)
            self._log(f"Program loaded ({len(program)} blocks)", "success")
        except FileNotFoundError:
            messagebox.showwarning("Warning", "Program file not found!")

    def _export_registers(self):
        if self.position_register_panel:
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                title="Export Position Registers",
            )
            if path:
                self.position_register_panel.save_registers(path)
                self._log(f"Registers exported: {path}", "success")

    def _import_registers(self):
        if self.position_register_panel:
            path = filedialog.askopenfilename(
                filetypes=[("JSON", "*.json")], title="Import Position Registers"
            )
            if path:
                try:
                    self.position_register_panel.load_registers(path)
                    self._log(f"Registers imported: {path}", "success")
                except Exception as e:
                    self._log(f"Import error: {e}", "error")

    # ── Coordinates ───────────────────────────────────────────────────────────
    def _update_tool_coordinates(self):
        if not self.kinematics_panel:
            return
        angles = self.kinematics_panel.joint_angles
        end_pos = self.kinematics_panel.kinematics.get_end_effector_position(angles)
        vals = {
            "X": f"{end_pos[0]:.2f}",
            "Y": f"{end_pos[1]:.2f}",
            "Z": f"{end_pos[2]:.2f}",
            "Rx": f"{angles[4]:.2f}",
            "Ry": f"{angles[3]:.2f}",
            "Rz": f"{angles[0]:.2f}",
        }
        self.tool_x_var.set(vals["X"])
        self.tool_y_var.set(vals["Y"])
        self.tool_z_var.set(vals["Z"])
        self.tool_rx_var.set(vals["Rx"])
        self.tool_ry_var.set(vals["Ry"])
        self.tool_rz_var.set(vals["Rz"])
        if hasattr(self, "dash_coord_labels"):
            for k, v in vals.items():
                if k in self.dash_coord_labels:
                    self.dash_coord_labels[k].configure(text=v)

    def _update_dashboard_joints(self):
        if not hasattr(self, "dash_joint_labels"):
            return
        for j in range(6):
            mid = self.controller.get_motor_id_for_joint(j)
            pos = self.controller.joint_positions.get(mid, 2048)
            angle = (pos / MAX_POSITION) * 360 - 180
            if j in self.dash_joint_labels:
                self.dash_joint_labels[j].configure(text=f"{angle:.1f}")

    def _reset_tool_coordinates(self):
        for var in (
            self.tool_x_var,
            self.tool_y_var,
            self.tool_z_var,
            self.tool_rx_var,
            self.tool_ry_var,
            self.tool_rz_var,
        ):
            var.set("0.00")
        self._log("Coordinates reset", "info")

    # ── Keyboard shortcuts ────────────────────────────────────────────────────
    def _bind_keyboard_shortcuts(self):
        self.bind("<Control-s>", lambda e: self._save_config())
        self.bind("<F5>", lambda e: self._run_program())
        self.bind("<Escape>", lambda e: self._emergency_stop())
        for i in range(6):
            self.bind(f"<Control-Key-{i + 1}>", lambda e, idx=i: self._select_joint(idx))
        self.bind("<Left>", lambda e: self._jog_selected(-1))
        self.bind("<Right>", lambda e: self._jog_selected(1))
        self.bind("<Up>", lambda e: self._jog_selected(1))
        self.bind("<Down>", lambda e: self._jog_selected(-1))
        self.bind("<plus>", lambda e: self._adjust_speed(5))
        self.bind("<minus>", lambda e: self._adjust_speed(-5))
        self.bind("<KP_Add>", lambda e: self._adjust_speed(5))
        self.bind("<KP_Subtract>", lambda e: self._adjust_speed(-5))

    def _select_joint(self, idx):
        if self.manual_panel:
            self.manual_panel.select_joint(idx)

    def _jog_selected(self, direction):
        if self.manual_panel and hasattr(self.manual_panel, "jog"):
            self.manual_panel.jog(direction)

    def _adjust_speed(self, delta):
        new_val = max(SPEED_OVERRIDE_MIN, min(SPEED_OVERRIDE_MAX, self.speed_override + delta))
        self.speed_override_var.set(new_val)
        self._on_speed_override_change(new_val)

    # ── Help ─────────────────────────────────────────────────────────────────
    def _show_shortcuts(self):
        messagebox.showinfo(
            "Keyboard Shortcuts",
            "Ctrl+1..6  — Select joint J1..J6\n"
            "Arrow keys — Jog selected joint\n"
            "+/-        — Speed override\n"
            "Ctrl+S     — Save config\n"
            "F5         — Run program\n"
            "Escape     — Emergency stop",
        )

    def _show_about(self):
        messagebox.showinfo(
            "About",
            "ST3215 Robot Control Panel v8.0\n"
            "CustomTkinter UI\n\n"
            "6-DOF Robot Arm Controller\n"
            "ST3215 Servo Motors\n"
            "DH Kinematics + IK Solver\n\n"
            "Author: Alexandr Lyachov",
        )

    def _show_mapping_panel(self):
        self.tabview.set("Setup")

    def _show_monitor_panel(self):
        self.tabview.set("Dashboard")

    # ── Closing ───────────────────────────────────────────────────────────────
    def _on_closing(self):
        if messagebox.askyesno("Exit", "Quit application?"):
            if self.monitor:
                self.monitor.stop()
            self.controller.disconnect()
            self.controller.save_config()
            self.logger.close()
            self.destroy()
