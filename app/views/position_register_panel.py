#!/usr/bin/env python3
"""Position Register Panel — сохранение/загрузка точек в стиле FANUC."""

import json
import time
import tkinter as tk
from tkinter import messagebox, ttk

from app.config.constants import (
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    MAX_POSITION,
)
from app.models.kinematics import InverseKinematics6DOF


class PositionRegisterPanel(ttk.Frame):
    """Панель позиционных регистров (PR) в стиле FANUC."""

    def __init__(self, parent, controller, kinematics, log_callback):
        super().__init__(parent)
        self.controller = controller
        self.kinematics = kinematics
        self.ik_solver = InverseKinematics6DOF(kinematics)
        self.log = log_callback
        self.registers: dict[int, dict] = {}
        self._create_widgets()

    def _create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Заголовок
        header = tk.Frame(main, bg=FANUC_PANEL)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="POSITION REGISTERS (PR)", font=("Consolas", 14, "bold"),
                 bg=FANUC_PANEL, fg=FANUC_GREEN).pack(side="left", padx=10, pady=5)

        btn_frame = tk.Frame(header, bg=FANUC_PANEL)
        btn_frame.pack(side="right", padx=10)
        for text, bg, cmd in [
            ("RECORD", FANUC_GREEN, self._record_current),
            ("MOVE TO", FANUC_BLUE, self._move_to_selected),
            ("DELETE", FANUC_RED, self._delete_selected),
            ("CLEAR ALL", FANUC_ORANGE, self._clear_all),
        ]:
            tk.Button(btn_frame, text=text, font=("Arial", 9, "bold"), bg=bg, fg=FANUC_TEXT,
                      bd=0, padx=12, pady=4, command=cmd).pack(side="left", padx=3)

        # XYZ ввод
        input_frame = ttk.LabelFrame(main, text="MANUAL INPUT (XYZ mm)")
        input_frame.pack(fill="x", pady=(0, 10))
        coords_frame = tk.Frame(input_frame, bg=FANUC_PANEL)
        coords_frame.pack(fill="x", padx=10, pady=8)

        self.xyz_vars = {}
        for i, (label, color) in enumerate([("X", FANUC_RED), ("Y", FANUC_GREEN), ("Z", FANUC_BLUE)]):
            tk.Label(coords_frame, text=f"{label}:", font=("Consolas", 11, "bold"),
                     bg=FANUC_PANEL, fg=color).grid(row=0, column=i * 2, padx=(10, 2))
            var = tk.DoubleVar(value=0.0)
            self.xyz_vars[label.lower()] = var
            ttk.Spinbox(coords_frame, from_=-400, to=400, textvariable=var,
                        width=8, font=("Consolas", 11), increment=5.0).grid(row=0, column=i * 2 + 1, padx=(2, 10))

        tk.Button(coords_frame, text="CALC IK + RECORD", font=("Arial", 9, "bold"),
                  bg="#7B68EE", fg=FANUC_TEXT, bd=0, padx=12, pady=4,
                  command=self._record_from_xyz).grid(row=0, column=6, padx=10)

        # Таблица
        table_frame = ttk.Frame(main)
        table_frame.pack(fill="both", expand=True)
        columns = ("pr", "j1", "j2", "j3", "j4", "j5", "j6", "x", "y", "z", "comment")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        widths = {"pr": 50, "comment": 150}
        for col in columns:
            self.tree.heading(col, text="PR#" if col == "pr" else col.upper())
            self.tree.column(col, width=widths.get(col, 65), anchor="center")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.status_label = tk.Label(main, text="0 registers", font=("Consolas", 10),
                                     bg=FANUC_BG, fg=FANUC_GRAY, anchor="w")
        self.status_label.pack(fill="x", pady=(5, 0))

    def _get_current_angles(self) -> list[float]:
        angles = []
        for joint_idx in range(6):
            motor_id = self.controller.get_motor_id_for_joint(joint_idx)
            pos = self.controller.joint_positions.get(motor_id, 2048)
            angles.append(round((pos / MAX_POSITION) * 360 - 180, 1))
        return angles

    def _next_pr_index(self) -> int:
        return max(self.registers.keys()) + 1 if self.registers else 1

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
            "angles": angles, "xyz": [round(x, 1), round(y, 1), round(z, 1)],
            "comment": f"IK ({x:.0f},{y:.0f},{z:.0f})",
        }
        self._refresh_table()
        self.log(f"PR[{pr_idx}] from IK: ({x},{y},{z}) -> {angles}", "success")

    def _move_to_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a register first!")
            return
        pr_idx = int(self.tree.item(selected[0])["values"][0])
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
        selected = self.tree.selection()
        if selected:
            pr_idx = int(self.tree.item(selected[0])["values"][0])
            self.registers.pop(pr_idx, None)
            self._refresh_table()

    def _clear_all(self):
        if messagebox.askyesno("Confirm", "Clear all position registers?"):
            self.registers.clear()
            self._refresh_table()
            self.log("All registers cleared", "warning")

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for pr_idx in sorted(self.registers.keys()):
            reg = self.registers[pr_idx]
            a, xyz = reg["angles"], reg.get("xyz", [0, 0, 0])
            self.tree.insert("", "end", values=(
                pr_idx, *[f"{v:.1f}" for v in a], *[f"{v:.1f}" for v in xyz], reg.get("comment", ""),
            ))
        self.status_label.config(text=f"{len(self.registers)} registers")

    def save_registers(self, filename: str):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in self.registers.items()}, f, indent=2, ensure_ascii=False)

    def load_registers(self, filename: str):
        with open(filename, encoding="utf-8") as f:
            self.registers = {int(k): v for k, v in json.load(f).items()}
        self._refresh_table()
