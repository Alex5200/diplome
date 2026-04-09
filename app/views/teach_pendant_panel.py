#!/usr/bin/env python3
"""Teach Pendant Panel — запись и воспроизведение траекторий."""

import threading
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


class TeachPendantPanel(ttk.Frame):
    """Панель Teach Pendant — запись и воспроизведение траекторий."""

    def __init__(self, parent, controller, kinematics, log_callback):
        super().__init__(parent)
        self.controller = controller
        self.kinematics = kinematics
        self.log = log_callback
        self.teach_points: list[dict] = []
        self.is_playing = False
        self._stop_flag = False
        self._create_widgets()

    def _create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Заголовок
        header = tk.Frame(main, bg=FANUC_PANEL)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(
            header,
            text="TEACH PENDANT",
            font=("Consolas", 14, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_GREEN,
        ).pack(side="left", padx=10, pady=5)

        # Кнопки
        ctrl_frame = ttk.LabelFrame(main, text="CONTROLS")
        ctrl_frame.pack(fill="x", pady=(0, 10))
        btn_row = tk.Frame(ctrl_frame, bg=FANUC_PANEL)
        btn_row.pack(fill="x", padx=10, pady=8)

        for text, bg, fg, cmd in [
            ("TEACH POINT", FANUC_GREEN, "black", self._teach_point),
            ("PLAY ALL", FANUC_BLUE, "white", self._play_all),
            ("PLAY ONCE", "#7B68EE", "white", self._play_once),
            ("STOP", FANUC_RED, "white", self._stop_play),
            ("CLEAR ALL", FANUC_ORANGE, "white", self._clear_all),
        ]:
            tk.Button(
                btn_row,
                text=text,
                font=("Arial", 10, "bold"),
                bg=bg,
                fg=fg,
                bd=0,
                padx=14,
                pady=6,
                command=cmd,
            ).pack(side="left", padx=4)

        # Настройки
        settings = tk.Frame(ctrl_frame, bg=FANUC_PANEL)
        settings.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(
            settings, text="Delay (s):", font=("Arial", 10), bg=FANUC_PANEL, fg=FANUC_TEXT
        ).pack(side="left", padx=5)
        self.delay_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(
            settings,
            from_=0.1,
            to=10.0,
            textvariable=self.delay_var,
            width=6,
            increment=0.1,
            font=("Consolas", 10),
        ).pack(side="left", padx=5)

        tk.Label(settings, text="Loops:", font=("Arial", 10), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left", padx=(20, 5)
        )
        self.loop_var = tk.IntVar(value=1)
        ttk.Spinbox(
            settings, from_=1, to=100, textvariable=self.loop_var, width=5, font=("Consolas", 10)
        ).pack(side="left", padx=5)

        self.play_status = tk.Label(
            settings, text="IDLE", font=("Consolas", 10, "bold"), bg=FANUC_PANEL, fg=FANUC_GRAY
        )
        self.play_status.pack(side="right", padx=10)

        # Таблица
        table_frame = ttk.Frame(main)
        table_frame.pack(fill="both", expand=True)
        columns = ("idx", "j1", "j2", "j3", "j4", "j5", "j6", "x", "y", "z")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.tree.heading(col, text="#" if col == "idx" else col.upper())
            self.tree.column(col, width=50 if col == "idx" else 75, anchor="center")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Нижняя строка
        del_frame = tk.Frame(main, bg=FANUC_BG)
        del_frame.pack(fill="x", pady=5)
        tk.Button(
            del_frame,
            text="DELETE SELECTED",
            font=("Arial", 9, "bold"),
            bg=FANUC_RED,
            fg=FANUC_TEXT,
            bd=0,
            padx=10,
            pady=3,
            command=self._delete_selected,
        ).pack(side="left")
        self.count_label = tk.Label(
            del_frame, text="0 points", font=("Consolas", 10), bg=FANUC_BG, fg=FANUC_GRAY
        )
        self.count_label.pack(side="right")

    def _get_current_state(self) -> dict:
        angles = []
        for joint_idx in range(6):
            motor_id = self.controller.get_motor_id_for_joint(joint_idx)
            pos = self.controller.joint_positions.get(motor_id, 2048)
            angles.append(round((pos / MAX_POSITION) * 360 - 180, 1))
        xyz = self.kinematics.get_end_effector_position(angles)
        return {"angles": angles, "xyz": [round(xyz[0], 1), round(xyz[1], 1), round(xyz[2], 1)]}

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
        self.after(0, lambda: self.play_status.config(text="RUNNING", fg=FANUC_GREEN))
        delay = self.delay_var.get()
        for _loop_i in range(loops):
            if self._stop_flag:
                break
            for i, point in enumerate(self.teach_points):
                if self._stop_flag:
                    break
                self.after(0, lambda idx=i: self._highlight_row(idx))
                for j, angle in enumerate(point["angles"]):
                    position = max(0, min(MAX_POSITION, int((angle + 180) / 360 * MAX_POSITION)))
                    motor_id = self.controller.get_motor_id_for_joint(j)
                    self.controller.move_to_position(motor_id, position)
                time.sleep(delay)
        self.is_playing = False
        self.after(0, lambda: self.play_status.config(text="DONE", fg=FANUC_BLUE))

    def _stop_play(self):
        self._stop_flag = True
        self.is_playing = False
        self.play_status.config(text="STOPPED", fg=FANUC_RED)

    def _highlight_row(self, idx: int):
        for item in self.tree.get_children():
            self.tree.item(item, tags=())
        items = self.tree.get_children()
        if idx < len(items):
            self.tree.item(items[idx], tags=("active",))
            self.tree.tag_configure("active", background="#2a4a2a")
            self.tree.see(items[idx])

    def _delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(self.tree.item(selected[0])["values"][0]) - 1
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
            a, xyz = pt["angles"], pt.get("xyz", [0, 0, 0])
            self.tree.insert(
                "",
                "end",
                values=(
                    i + 1,
                    *[f"{v:.1f}" for v in a],
                    *[f"{v:.1f}" for v in xyz],
                ),
            )
        self.count_label.config(text=f"{len(self.teach_points)} points")
