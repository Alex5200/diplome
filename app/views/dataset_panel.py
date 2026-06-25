#!/usr/bin/env python3
"""
Dataset Panel — запись эпизодов в VAMOS и LeRobot форматы.
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path

import customtkinter as ctk

from app.config.constants import FANUC_BG, FANUC_BLUE, FANUC_GRAY, FANUC_GREEN, FANUC_ORANGE, FANUC_PANEL, FANUC_RED, FANUC_TEXT, FANUC_TEXT2
from app.services.camera_service import CameraService
from app.services.dataset_recorder_service import DatasetRecorderService

_ACCENT = "#7dd3c0"
_ACCENT_H = "#5bb8a4"
_BORDER = "#e8e4e0"
_CARD_BG = FANUC_PANEL


class DatasetPanel(ctk.CTkFrame):
    """Панель записи датасетов в VAMOS + LeRobot."""

    def __init__(self, parent, robot_service, kinematics_service, log_callback):
        super().__init__(parent, fg_color=FANUC_BG, corner_radius=0)
        self.robot_service = robot_service
        self.kinematics_service = kinematics_service
        self._camera = CameraService()
        self._camera_running = False
        self.recorder = DatasetRecorderService(
            robot_service=robot_service,
            camera_service=self._camera,
            kinematics_service=kinematics_service,
            base_path="datasets",
            log_callback=log_callback,
        )
        self._create_widgets()
        self._update_status_loop()

    def _create_widgets(self):
        main = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # Header
        hdr = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        hdr.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            hdr, text="DATASET RECORDER", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=_ACCENT
        ).pack(side="left", padx=14, pady=10)

        # Controls card
        ctrl_card = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        ctrl_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            ctrl_card, text="RECORDING CONTROLS", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=_ACCENT
        ).pack(anchor="w", padx=12, pady=(8, 2))

        # Format selection
        fmt_frame = ctk.CTkFrame(ctrl_card, fg_color=_CARD_BG, corner_radius=0)
        fmt_frame.pack(fill="x", padx=12, pady=(4, 0))

        self.vamos_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            fmt_frame, text="VAMOS", variable=self.vamos_var,
            font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT,
            fg_color=_ACCENT, hover_color=_ACCENT_H,
        ).pack(side="left", padx=(0, 20))

        self.lerobot_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            fmt_frame, text="LeRobot", variable=self.lerobot_var,
            font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT,
            fg_color=_ACCENT, hover_color=_ACCENT_H,
        ).pack(side="left")

        ctk.CTkLabel(
            fmt_frame, text="FPS:", font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2
        ).pack(side="left", padx=(20, 4))
        self.fps_var = tk.IntVar(value=30)
        ttk.Spinbox(
            fmt_frame, from_=5, to=60, textvariable=self.fps_var, width=5, font=("Consolas", 10)
        ).pack(side="left")

        # Task / Command
        task_frame = ctk.CTkFrame(ctrl_card, fg_color=_CARD_BG, corner_radius=0)
        task_frame.pack(fill="x", padx=12, pady=(8, 0))

        ctk.CTkLabel(
            task_frame, text="Task:", font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2
        ).pack(side="left")
        self.task_var = tk.StringVar(value="pick_and_place")
        ctk.CTkEntry(
            task_frame, textvariable=self.task_var, font=ctk.CTkFont("Consolas", 10),
            fg_color=FANUC_BG, text_color=FANUC_TEXT, border_color=_BORDER, width=180,
        ).pack(side="left", padx=6)

        ctk.CTkLabel(
            task_frame, text="Command:", font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2
        ).pack(side="left", padx=(10, 4))
        self.cmd_var = tk.StringVar(value="")
        ctk.CTkEntry(
            task_frame, textvariable=self.cmd_var, font=ctk.CTkFont("Consolas", 10),
            fg_color=FANUC_BG, text_color=FANUC_TEXT, border_color=_BORDER, width=250,
        ).pack(side="left", padx=6)

        # Buttons
        btn_frame = ctk.CTkFrame(ctrl_card, fg_color=_CARD_BG, corner_radius=0)
        btn_frame.pack(fill="x", padx=12, pady=(8, 10))

        self.record_btn = ctk.CTkButton(
            btn_frame, text="START RECORDING",
            fg_color=FANUC_GREEN, hover_color="#4a9a6a",
            text_color=FANUC_TEXT, height=36, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._toggle_recording,
        )
        self.record_btn.pack(side="left", padx=4)

        self.pause_btn = ctk.CTkButton(
            btn_frame, text="PAUSE",
            fg_color=FANUC_ORANGE, hover_color="#d4995a",
            text_color=FANUC_TEXT, height=36, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            state="disabled", command=self._toggle_pause,
        )
        self.pause_btn.pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame, text="OPEN DATASETS",
            fg_color=FANUC_BLUE, hover_color="#6a94d8",
            text_color=FANUC_TEXT, height=36, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._open_datasets_dir,
        ).pack(side="left", padx=4)

        # Status card
        status_card = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        status_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            status_card, text="STATUS", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=_ACCENT
        ).pack(anchor="w", padx=12, pady=(8, 2))

        status_inner = ctk.CTkFrame(status_card, fg_color=_CARD_BG, corner_radius=0)
        status_inner.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(status_inner, text="State:", font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2).grid(row=0, column=0, sticky="w")
        self.state_label = ctk.CTkLabel(status_inner, text="IDLE", font=ctk.CTkFont("Consolas", 11, "bold"), text_color=FANUC_GRAY)
        self.state_label.grid(row=0, column=1, padx=(8, 20), sticky="w")

        ctk.CTkLabel(status_inner, text="Frames:", font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2).grid(row=0, column=2, sticky="w")
        self.frames_label = ctk.CTkLabel(status_inner, text="0", font=ctk.CTkFont("Consolas", 11, "bold"), text_color=FANUC_TEXT)
        self.frames_label.grid(row=0, column=3, padx=(8, 20), sticky="w")

        ctk.CTkLabel(status_inner, text="Episodes:", font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2).grid(row=0, column=4, sticky="w")
        self.episodes_label = ctk.CTkLabel(status_inner, text="0", font=ctk.CTkFont("Consolas", 11, "bold"), text_color=FANUC_TEXT)
        self.episodes_label.grid(row=0, column=5, padx=(8, 0), sticky="w")

        # Presets card
        presets_card = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        presets_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            presets_card, text="PRESET TASKS", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=_ACCENT
        ).pack(anchor="w", padx=12, pady=(8, 2))

        presets_inner = ctk.CTkFrame(presets_card, fg_color=_CARD_BG, corner_radius=0)
        presets_inner.pack(fill="x", padx=12, pady=(4, 10))

        for task, cmd in [
            ("Pick & Place", ("pick_and_place", "Pick up the red object and place it in the bin")),
            ("Reach Target", ("reach_target", "Move end effector to the target position")),
            ("Push Object", ("push_object", "Push the blue cube forward 10cm")),
            ("Draw Circle", ("draw_circle", "Trace a 5cm circle in the air")),
            ("Grasp & Hold", ("grasp_hold", "Grasp the object and hold for 5 seconds")),
            ("Screw Insertion", ("screw_insertion", "Insert the peg into the hole")),
        ]:
            ctk.CTkButton(
                presets_inner,
                text=task,
                fg_color="#3a4a5a",
                hover_color="#4a5a6a",
                text_color=FANUC_TEXT,
                height=28,
                corner_radius=6,
                font=ctk.CTkFont("Segoe UI", 9),
                command=lambda t=cmd[0], c=cmd[1]: self._apply_preset(t, c),
            ).pack(side="left", padx=3)

        # Log card
        log_card = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        log_card.pack(fill="both", expand=True)

        ctk.CTkLabel(
            log_card, text="SESSION LOG", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=_ACCENT
        ).pack(anchor="w", padx=12, pady=(8, 2))

        self.log_text = tk.Text(
            log_card, height=8, bg=FANUC_BG, fg=FANUC_TEXT,
            font=("Consolas", 9), relief="flat", bd=0, padx=8, pady=4,
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_text.insert("end", "Ready. Select format, configure task, and press START RECORDING.\n")

    # ── Actions ─────────────────────────────────────────────────────────────

    def _toggle_recording(self):
        if self.recorder.is_recording:
            self.recorder.stop_episode()
            self.record_btn.configure(text="START RECORDING", fg_color=FANUC_GREEN, hover_color="#4a9a6a")
            self.pause_btn.configure(state="disabled", text="PAUSE")
            self._update_status_loop()
        else:
            self.recorder.configure(
                format_vamos=self.vamos_var.get(),
                format_lerobot=self.lerobot_var.get(),
                fps=self.fps_var.get(),
            )
            ok = self.recorder.start_episode(
                task_name=self.task_var.get(),
                command_text=self.cmd_var.get(),
            )
            if ok:
                self.record_btn.configure(text="STOP RECORDING", fg_color=FANUC_RED, hover_color="#c07065")
                self.pause_btn.configure(state="normal")

    def _toggle_pause(self):
        self.recorder.pause_episode()
        is_paused = self.recorder.is_paused
        self.pause_btn.configure(text="RESUME" if is_paused else "PAUSE")

    def _apply_preset(self, task: str, command: str):
        self.task_var.set(task)
        self.cmd_var.set(command)

    def _open_datasets_dir(self):
        path = Path("datasets").absolute()
        if path.exists():
            import subprocess
            subprocess.Popen(["explorer", str(path)])

    def _update_status_loop(self):
        if self.recorder.is_recording:
            self.state_label.configure(text="RECORDING", text_color=FANUC_RED)
        elif self.recorder.is_paused:
            self.state_label.configure(text="PAUSED", text_color=FANUC_ORANGE)
        else:
            self.state_label.configure(text="IDLE", text_color=FANUC_GRAY)

        self.frames_label.configure(text=str(self.recorder.frame_count))
        self.episodes_label.configure(text=str(self.recorder.episode_count))

        self.after(200, self._update_status_loop)
