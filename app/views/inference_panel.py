#!/usr/bin/env python3
"""Inference Panel — запуск LeRobot моделей (ACT, Diffusion, pi0, pi0.5, SmolVLA) + fino-tuning + Jupyter."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path

import customtkinter as ctk

from app.config.constants import (
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    FANUC_TEXT2,
    contrast_text_color,
)
from app.services.camera_service import CameraService
from app.services.inference_service import InferenceService

_ACCENT = "#7dd3c0"
_ACCENT_H = "#5bb8a4"
_BORDER = "#e8e4e0"
_CARD_BG = FANUC_PANEL

_BTN_HEIGHT = 32
_BTN_RADIUS = 8

_SO100_MODELS = [
    # ACT for SO-100
    {"label": "ACT SO-100 Pick Cup",     "value": "lerobot/act_so100_pick_cup",              "type": "act"},
    {"label": "ACT ALOHA Cube Transfer", "value": "lerobot/act_aloha_sim_transfer_cube_human","type": "act"},
    {"label": "ACT ALOHA Mobile Cabinet","value": "lerobot/act_aloha_mobile_cabinet",        "type": "act"},
    # Diffusion for SO-100
    {"label": "Diffusion PushT",         "value": "lerobot/diffusion_pusht",                  "type": "diffusion"},
    {"label": "Diffusion Grasp",        "value": "lerobot/diffusion_policy-grasp",            "type": "diffusion"},
    # VLA — pi0 / pi0.5 (SO-100 compatible)
    {"label": "pi0 Base (VLA)",          "value": "lerobot/pi0_base",                         "type": "vla"},
    {"label": "pi0 Libero (VLA)",        "value": "lerobot/pi0_libero",                       "type": "vla"},
    {"label": "pi0.5 Base (VLA)",        "value": "lerobot/pi05_base",                        "type": "vla"},
    {"label": "pi0.5 Libero (VLA)",      "value": "lerobot/pi05_libero",                      "type": "vla"},
    # SmolVLA
    {"label": "SmolVLA ALOHA",           "value": "lerobot/smolvla-aloha",                    "type": "smolvla"},
]


class InferencePanel(ctk.CTkFrame):
    """Панель инференса и fino-tuning LeRobot."""

    def __init__(self, parent, robot_service, kinematics_service, log_callback):
        super().__init__(parent, fg_color=FANUC_BG, corner_radius=0)
        self.robot_service = robot_service
        self.kinematics_service = kinematics_service
        self._camera = CameraService()
        self._camera_running = False
        self.inference = InferenceService(
            robot_service=robot_service,
            camera_service=self._camera,
            kinematics_service=kinematics_service,
            log_callback=log_callback,
        )
        self._ray_supported = self.inference.ray_available
        self._create_widgets()
        self._update_status_loop()

    def _contrast_btn(self, bg: str, text: str = "WHITE") -> str:
        """Возвращает text_color для кнопки: белый на тёмном фоне, чёрный на светлом."""
        _ = text
        return contrast_text_color(bg)

    def _make_btn(self, parent, text, fg_color, command, width=None, height=_BTN_HEIGHT):
        kwargs = dict(
            text=text,
            fg_color=fg_color,
            hover_color=self._darken(fg_color),
            text_color=contrast_text_color(fg_color),
            height=height,
            corner_radius=_BTN_RADIUS,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=command,
        )
        if width is not None:
            kwargs["width"] = width
        return ctk.CTkButton(parent, **kwargs)

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.15) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _create_widgets(self):
        main = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # ── Header ──
        hdr = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        hdr.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            hdr, text="INFERENCE — LEROBOT (SO-100 / pi0 / pi0.5)",
            font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=_ACCENT,
        ).pack(side="left", padx=14, pady=10)

        # ── Model Card ──
        mdl_card = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        mdl_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            mdl_card, text="MODEL", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=_ACCENT,
        ).pack(anchor="w", padx=12, pady=(8, 2))

        row1 = ctk.CTkFrame(mdl_card, fg_color=_CARD_BG, corner_radius=0)
        row1.pack(fill="x", padx=12, pady=6)

        self.model_var = tk.StringVar(value=_SO100_MODELS[0]["value"])
        model_labels = [m["label"] for m in _SO100_MODELS]
        self.model_combo = ttk.Combobox(
            row1, textvariable=self.model_var, values=model_labels,
            width=45, font=("Segoe UI", 10),
        )
        self.model_combo.pack(side="left", padx=4)

        self.load_btn = self._make_btn(
            row1, "LOAD", FANUC_BLUE, self._load_model,
        )
        self.load_btn.pack(side="left", padx=4)

        self.unload_btn = self._make_btn(
            row1, "UNLOAD", FANUC_ORANGE, self._unload_model,
        )
        self.unload_btn.configure(state="disabled")
        self.unload_btn.pack(side="left", padx=4)

        self.model_type_lbl = ctk.CTkLabel(
            row1, text="", font=ctk.CTkFont("Consolas", 8, "bold"),
            text_color=FANUC_GRAY,
        )
        self.model_type_lbl.pack(side="left", padx=(10, 4))

        self.model_status = ctk.CTkLabel(
            row1, text="—", font=ctk.CTkFont("Consolas", 9), text_color=FANUC_GRAY,
        )
        self.model_status.pack(side="left", padx=4)

        # ── Control Card ──
        ctrl_card = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        ctrl_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            ctrl_card, text="CONTROLS", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=_ACCENT,
        ).pack(anchor="w", padx=12, pady=(8, 2))

        row2 = ctk.CTkFrame(ctrl_card, fg_color=_CARD_BG, corner_radius=0)
        row2.pack(fill="x", padx=12, pady=6)

        self.run_btn = self._make_btn(
            row2, "START INFERENCE", FANUC_GREEN, self._toggle_inference,
            height=36,
        )
        self.run_btn.configure(state="disabled")
        self.run_btn.pack(side="left", padx=4)

        ctk.CTkLabel(row2, text="Device:", font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2
                     ).pack(side="left", padx=(20, 4))
        self.device_label = ctk.CTkLabel(
            row2, text=self.inference.device.upper(),
            font=ctk.CTkFont("Consolas", 10, "bold"), text_color=_ACCENT,
        )
        self.device_label.pack(side="left")

        if self._ray_supported:
            self._ray_var = tk.BooleanVar(value=False)
            self._ray_cb = ctk.CTkCheckBox(
                row2, text="Ray", variable=self._ray_var,
                font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2,
                command=self._toggle_ray,
                fg_color=_ACCENT, checkmark_color=FANUC_TEXT,
            )
            self._ray_cb.pack(side="left", padx=(20, 4))

        # ── Status Card ──
        stat_card = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        stat_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            stat_card, text="STATUS", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=_ACCENT,
        ).pack(anchor="w", padx=12, pady=(8, 2))

        st = ctk.CTkFrame(stat_card, fg_color=_CARD_BG, corner_radius=0)
        st.pack(fill="x", padx=12, pady=8)

        self.state_lbl = ctk.CTkLabel(
            st, text="IDLE", font=ctk.CTkFont("Consolas", 11, "bold"), text_color=FANUC_GRAY,
        )
        self.state_lbl.grid(row=0, column=0, padx=(0, 20))

        ctk.CTkLabel(st, text="FPS:",           font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2
                     ).grid(row=0, column=1)
        self.fps_lbl = ctk.CTkLabel(st, text="0", font=ctk.CTkFont("Consolas", 10), text_color=FANUC_TEXT)
        self.fps_lbl.grid(row=0, column=2, padx=4)

        ctk.CTkLabel(st, text="Latency:",       font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2
                     ).grid(row=0, column=3, padx=(20, 4))
        self.lat_lbl = ctk.CTkLabel(st, text="0 ms", font=ctk.CTkFont("Consolas", 10), text_color=FANUC_TEXT)
        self.lat_lbl.grid(row=0, column=4)

        ctk.CTkLabel(st, text="Frames:",        font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2
                     ).grid(row=0, column=5, padx=(20, 4))
        self.frm_lbl = ctk.CTkLabel(st, text="0", font=ctk.CTkFont("Consolas", 10), text_color=FANUC_TEXT)
        self.frm_lbl.grid(row=0, column=6)

        ctk.CTkLabel(st, text="Model Type:",    font=ctk.CTkFont("Segoe UI", 10), text_color=FANUC_TEXT2
                     ).grid(row=0, column=7, padx=(20, 4))
        self.model_type_val = ctk.CTkLabel(
            st, text="—", font=ctk.CTkFont("Consolas", 10), text_color=FANUC_TEXT,
        )
        self.model_type_val.grid(row=0, column=8)

        # ── Fine-tuning Card ──
        train_card = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        train_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            train_card, text="FINE-TUNING & NOTEBOOK",
            font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=_ACCENT,
        ).pack(anchor="w", padx=12, pady=(8, 2))

        row3 = ctk.CTkFrame(train_card, fg_color=_CARD_BG, corner_radius=0)
        row3.pack(fill="x", padx=12, pady=(4, 10))

        jup_bg = "#7B68EE"
        self._make_btn(row3, "LAUNCH JUPYTER",  jup_bg, self._launch_jupyter).pack(side="left", padx=4)
        self._make_btn(row3, "OPEN NOTEBOOKS",  FANUC_BLUE, self._open_notebooks_dir).pack(side="left", padx=4)

        _, ray_avail = ("Ray", "✓") if self._ray_supported else ("Ray", "✗")
        ctk.CTkLabel(
            row3, text=f"Train on collected episodes from Dataset tab  |  Ray: {ray_avail}",
            font=ctk.CTkFont("Segoe UI", 9), text_color=FANUC_GRAY,
        ).pack(side="left", padx=10)

    def _toggle_ray(self):
        self.inference.use_ray = self._ray_var.get()

    def _load_model(self):
        idx = self.model_combo.current()
        if idx < 0:
            return
        model_name = _SO100_MODELS[idx]["value"]
        model_type = _SO100_MODELS[idx]["type"]
        self.load_btn.configure(state="disabled")
        self.model_status.configure(text="Loading...")
        self.update_idletasks()

        ok = self.inference.load_model(model_name)
        if ok:
            self.model_status.configure(text=f"✓ {model_name.split('/')[-1]}", text_color=_ACCENT)
            self.model_type_lbl.configure(text=f"[{model_type.upper()}]", text_color=_ACCENT)
            self.model_type_val.configure(text=model_type.upper())
            self.unload_btn.configure(state="normal")
            self.run_btn.configure(state="normal")
        else:
            self.model_status.configure(text="Load failed", text_color=FANUC_RED)
            self.load_btn.configure(state="normal")

    def _unload_model(self):
        self.inference.unload_model()
        self.model_status.configure(text="—", text_color=FANUC_GRAY)
        self.model_type_lbl.configure(text="")
        self.model_type_val.configure(text="—")
        self.load_btn.configure(state="normal")
        self.unload_btn.configure(state="disabled")
        self.run_btn.configure(state="disabled", text="START INFERENCE")

    def _toggle_inference(self):
        if self.inference.is_running:
            self.inference.stop_inference()
            self.run_btn.configure(text="START INFERENCE", fg_color=FANUC_GREEN)
        else:
            ok = self.inference.start_inference()
            if ok:
                self.run_btn.configure(text="STOP INFERENCE", fg_color=FANUC_RED)

    def _launch_jupyter(self):
        import subprocess
        import sys
        nb_dir = Path("notebooks").absolute()
        nb_dir.mkdir(exist_ok=True)
        self._log("Launching Jupyter notebook server...", "info")
        subprocess.Popen(
            [sys.executable, "-m", "jupyter", "notebook", "--notebook-dir", str(nb_dir)],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _open_notebooks_dir(self):
        import subprocess
        path = Path("notebooks").absolute()
        path.mkdir(exist_ok=True)
        subprocess.Popen(["explorer", str(path)])

    def _log(self, msg: str, level: str = "info"):
        if hasattr(self, "log_cb") and self.log_cb:
            self.log_cb(msg, level)

    def _update_status_loop(self):
        s = self.inference.stats
        self.fps_lbl.configure(text=str(s["fps"]))
        self.lat_lbl.configure(text=f'{s["latency_ms"]} ms')
        self.frm_lbl.configure(text=str(s["frames"]))
        if self.inference.is_running:
            self.state_lbl.configure(text="RUNNING", text_color=FANUC_GREEN)
        else:
            self.state_lbl.configure(text="IDLE", text_color=FANUC_GRAY)
        self.after(250, self._update_status_loop)
