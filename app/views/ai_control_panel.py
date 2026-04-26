#!/usr/bin/env python3
"""
AI Control Panel — GUI для управления роботом через локальный ИИ (Qwen3 VL).

Элементы интерфейса:
┌─────────────────────────────────────────────────────────┐
│  [Provider] [URL___________] [Model_______] [CHECK]     │
│  Task: [_____________________________________________]   │
│  Mode: ○ AUTO  ○ STEP  ○ WATCH   [▶ START] [⏹ STOP]   │
├──────────────────────┬──────────────────────────────────┤
│                      │  AI LOG                         │
│   CAMERA PREVIEW     │  [13:01] → query joints=[...]   │
│   640×480            │  [13:02] ← move J1=+5 "turn"   │
│                      │  [13:02] ⚙ executing...         │
│                      ├─────────────────────────────────┤
│                      │  STATUS                          │
│                      │  Task: ...                       │
│                      │  Steps: 12  Latency: 1.4s       │
│                      │  Last: move J2=+3 conf=0.87     │
│                      │  Joints: [0,30,-20,0,10,0]      │
└──────────────────────┴─────────────────────────────────┘
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageTk

from app.config.constants import (
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
)
from app.services.ai_provider import AIProvider
from app.services.ai_robot_controller_service import (
    AICommand,
    AIRobotControllerService,
    ControllerState,
    ControlMode,
)

if TYPE_CHECKING:
    pass


class AIControlPanel(ttk.Frame):
    """
    Панель управления роботом через локальный ИИ.

    Интегрируется как вкладка в главное окно:
        panel = AIControlPanel(notebook, robot_service, kin_service, log_cb)
        notebook.add(panel, text="🤖 AI Control")
    """

    PROVIDERS = {
        "Ollama (Local)": "ollama",
        "LM Studio (Local/Remote)": "lm_studio",
        "OpenAI API": "openai",
        "Custom (OpenAI-compat)": "custom",
    }

    DEFAULT_URLS = {
        "ollama": "http://localhost:11434",
        "lm_studio": "http://localhost:1234/v1",
        "openai": "https://api.openai.com/v1",
        "custom": "http://localhost:8080/v1",
    }

    DEFAULT_MODELS = {
        "ollama": "qwen2.5-vl:7b",
        "lm_studio": "qwen2.5-vl-7b",
        "openai": "gpt-4o",
        "custom": "",
    }

    # Пресеты задач для быстрого выбора
    TASK_PRESETS = [
        "Найди красный предмет и возьми его",
        "Положи объект в левую сторону стола",
        "Найди синюю коробку и поставь её в центр",
        "Медленно подними руку вверх",
        "Вернись в исходное положение",
        "Следи за моей рукой и повторяй движения",
        "Осмотри сцену и опиши что видишь",
    ]

    def __init__(self, parent, robot_service, kinematics_service, log_callback=None):
        super().__init__(parent)
        self.robot = robot_service
        self.kin = kinematics_service
        self.log = log_callback or (lambda msg, lvl="info": None)

        self._controller: AIRobotControllerService | None = None
        self._ai: AIProvider | None = None
        self._photo_image = None
        self._is_running = False

        self._create_widgets()

    # ════════════════════════════════════════════
    #  UI построение
    # ════════════════════════════════════════════

    def _create_widgets(self):
        # Верхняя панель (настройки)
        top = tk.Frame(self, bg=FANUC_PANEL)
        top.pack(fill="x", padx=8, pady=(8, 4))

        # Нижняя панель (камера + лог)
        bottom = tk.Frame(self, bg=FANUC_BG)
        bottom.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._build_settings(top)
        self._build_bottom(bottom)

    def _build_settings(self, parent):
        # ── Row 1: Provider + URL + Model + CHECK ──
        r1 = tk.Frame(parent, bg=FANUC_PANEL)
        r1.pack(fill="x", pady=2)

        tk.Label(r1, text="Provider:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left"
        )

        self._provider_var = tk.StringVar(value="Ollama (Local)")
        prov_cb = ttk.Combobox(
            r1,
            textvariable=self._provider_var,
            values=list(self.PROVIDERS.keys()),
            state="readonly",
            width=22,
            font=("Consolas", 9),
        )
        prov_cb.pack(side="left", padx=4)
        self._provider_var.trace_add("write", lambda *_: self._on_provider_change())

        tk.Label(r1, text="URL:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left", padx=(8, 0)
        )
        self._url_var = tk.StringVar(value=self.DEFAULT_URLS["ollama"])
        ttk.Entry(r1, textvariable=self._url_var, width=28, font=("Consolas", 9)).pack(
            side="left", padx=3
        )

        tk.Label(r1, text="Model:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left", padx=(6, 0)
        )
        self._model_var = tk.StringVar(value=self.DEFAULT_MODELS["ollama"])
        self._model_combo = ttk.Combobox(
            r1, textvariable=self._model_var, width=20, font=("Consolas", 9)
        )
        self._model_combo.pack(side="left", padx=3)
        tk.Button(
            r1,
            text="↻",
            font=("Arial", 9),
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
            bd=0,
            padx=4,
            command=self._fetch_models,
        ).pack(side="left")

        tk.Label(r1, text="Key:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left", padx=(6, 0)
        )
        self._apikey_var = tk.StringVar(value="ollama")
        ttk.Entry(r1, textvariable=self._apikey_var, width=12, font=("Consolas", 9), show="•").pack(
            side="left", padx=3
        )

        tk.Button(
            r1,
            text="CHECK",
            font=("Arial", 8, "bold"),
            bg=FANUC_BLUE,
            fg="white",
            bd=0,
            padx=8,
            pady=2,
            command=self._check_connection,
        ).pack(side="left", padx=4)

        self._conn_label = tk.Label(
            r1, text="", font=("Consolas", 9), bg=FANUC_PANEL, fg=FANUC_GRAY
        )
        self._conn_label.pack(side="right", padx=6)

        # ── Row 2: Task + Preset ──
        r2 = tk.Frame(parent, bg=FANUC_PANEL)
        r2.pack(fill="x", pady=2)

        tk.Label(
            r2, text="Task:", font=("Arial", 10, "bold"), bg=FANUC_PANEL, fg=FANUC_ORANGE
        ).pack(side="left")
        self._task_var = tk.StringVar(value=self.TASK_PRESETS[0])
        ttk.Entry(r2, textvariable=self._task_var, width=50, font=("Consolas", 10)).pack(
            side="left", padx=6
        )

        tk.Label(r2, text="Preset:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left", padx=(8, 0)
        )
        self._preset_var = tk.StringVar()
        preset_cb = ttk.Combobox(
            r2,
            textvariable=self._preset_var,
            values=self.TASK_PRESETS,
            state="readonly",
            width=32,
            font=("Consolas", 9),
        )
        preset_cb.pack(side="left", padx=3)
        self._preset_var.trace_add("write", lambda *_: self._task_var.set(self._preset_var.get()))

        # ── Row 3: Mode + AI Interval + Buttons ──
        r3 = tk.Frame(parent, bg=FANUC_BG)
        r3.pack(fill="x", pady=(4, 2))

        tk.Label(r3, text="Mode:", font=("Arial", 9), bg=FANUC_BG, fg=FANUC_TEXT).pack(side="left")

        self._mode_var = tk.StringVar(value="AUTO")
        for mode_name in ("AUTO", "STEP", "WATCH"):
            tk.Radiobutton(
                r3,
                text=mode_name,
                variable=self._mode_var,
                value=mode_name,
                font=("Arial", 9),
                bg=FANUC_BG,
                fg=FANUC_TEXT,
                selectcolor=FANUC_PANEL,
                activebackground=FANUC_BG,
            ).pack(side="left", padx=3)

        tk.Label(r3, text="Interval(s):", font=("Arial", 9), bg=FANUC_BG, fg=FANUC_TEXT).pack(
            side="left", padx=(12, 0)
        )
        self._interval_var = tk.DoubleVar(value=1.5)
        ttk.Spinbox(
            r3,
            from_=0.5,
            to=10.0,
            increment=0.5,
            textvariable=self._interval_var,
            width=5,
            font=("Consolas", 9),
        ).pack(side="left", padx=3)

        # Кнопки управления
        self._start_btn = tk.Button(
            r3,
            text="▶ START AI",
            font=("Arial", 10, "bold"),
            bg=FANUC_GREEN,
            fg="black",
            bd=0,
            padx=16,
            pady=4,
            command=self._start,
        )
        self._start_btn.pack(side="left", padx=8)

        self._stop_btn = tk.Button(
            r3,
            text="⏹ STOP",
            font=("Arial", 10, "bold"),
            bg=FANUC_RED,
            fg="white",
            bd=0,
            padx=14,
            pady=4,
            command=self._stop,
            state="disabled",
        )
        self._stop_btn.pack(side="left", padx=3)

        self._step_btn = tk.Button(
            r3,
            text="⏭ STEP",
            font=("Arial", 9, "bold"),
            bg=FANUC_BLUE,
            fg="white",
            bd=0,
            padx=12,
            pady=4,
            command=self._trigger_step,
            state="disabled",
        )
        self._step_btn.pack(side="left", padx=3)

        self._status_label = tk.Label(
            r3, text="IDLE", font=("Consolas", 11, "bold"), bg=FANUC_BG, fg=FANUC_GRAY
        )
        self._status_label.pack(side="right", padx=10)

    def _build_bottom(self, parent):
        # Левая: камера
        left = ttk.LabelFrame(parent, text="CAMERA (AI vision)")
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        cam_container = tk.Frame(left, bg="black", width=520, height=400)
        cam_container.pack(fill="both", expand=True, padx=4, pady=4)
        cam_container.pack_propagate(False)

        self._video_label = tk.Label(
            cam_container,
            bg="black",
            text="Camera OFF\nPress ▶ START AI",
            fg=FANUC_GRAY,
            font=("Consolas", 12),
        )
        self._video_label.pack(fill="both", expand=True)

        # Правая: AI лог + статус
        right = tk.Frame(parent, bg=FANUC_BG)
        right.pack(side="right", fill="both", expand=False)

        # AI Log
        log_frame = ttk.LabelFrame(right, text="AI LOG")
        log_frame.pack(fill="both", expand=True, pady=(0, 4))

        self._ai_log = scrolledtext.ScrolledText(
            log_frame,
            width=42,
            height=14,
            font=("Consolas", 8),
            bg="#0d1117",
            fg="#c9d1d9",
            insertbackground="white",
            state="disabled",
            wrap="word",
            bd=0,
        )
        self._ai_log.pack(fill="both", expand=True, padx=4, pady=4)

        # Цвета тегов
        self._ai_log.tag_configure("time", foreground="#8b949e")
        self._ai_log.tag_configure("query", foreground="#79c0ff")
        self._ai_log.tag_configure("response", foreground="#7ee787")
        self._ai_log.tag_configure("execute", foreground="#ffa657")
        self._ai_log.tag_configure("error", foreground="#ff7b72")
        self._ai_log.tag_configure("warn", foreground="#d29922")
        self._ai_log.tag_configure("info", foreground="#c9d1d9")

        # Status
        status_frame = ttk.LabelFrame(right, text="STATUS")
        status_frame.pack(fill="x")

        self._status_text = tk.Text(
            status_frame,
            width=42,
            height=8,
            font=("Consolas", 8),
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
            state="disabled",
            wrap="word",
            bd=0,
        )
        self._status_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ════════════════════════════════════════════
    #  Provider / Connection
    # ════════════════════════════════════════════

    def _on_provider_change(self):
        key = self.PROVIDERS.get(self._provider_var.get(), "ollama")
        self._url_var.set(self.DEFAULT_URLS.get(key, ""))
        self._model_var.set(self.DEFAULT_MODELS.get(key, ""))

    def _build_ai_provider(self) -> AIProvider:
        key = self.PROVIDERS.get(self._provider_var.get(), "ollama")
        url = self._url_var.get().strip()
        model = self._model_var.get().strip()
        key_ = self._apikey_var.get().strip()

        if key == "ollama":
            return AIProvider.ollama(model=model, url=url)
        elif key == "lm_studio":
            return AIProvider.lm_studio(url=url, model=model, api_key=key_ or "lm-studio")
        elif key == "openai":
            return AIProvider.openai(api_key=key_, model=model)
        else:
            return AIProvider.custom(url=url, model=model, api_key=key_)

    def _check_connection(self):
        ai = self._build_ai_provider()
        self._conn_label.config(text="Checking...", fg=FANUC_ORANGE)
        self.update_idletasks()

        def check():
            ok = ai.is_available()
            models = ai.list_models() if ok else []
            self.after(
                0,
                lambda: (
                    self._conn_label.config(
                        text=f"✓ {len(models)} models" if ok else "✗ Unreachable",
                        fg=FANUC_GREEN if ok else FANUC_RED,
                    ),
                    self._populate_model_combo(models) if models else None,
                ),
            )

        threading.Thread(target=check, daemon=True).start()

    def _fetch_models(self):
        ai = self._build_ai_provider()

        def fetch():
            models = ai.list_models()
            self.after(0, lambda: self._populate_model_combo(models))

        threading.Thread(target=fetch, daemon=True).start()

    def _populate_model_combo(self, models: list[str]):
        if models:
            self._model_combo["values"] = models
            if self._model_var.get() not in models:
                self._model_combo.current(0)
            self._log_ai(f"Models: {models}", "info")

    # ════════════════════════════════════════════
    #  Start / Stop
    # ════════════════════════════════════════════

    def _start(self):
        if self._is_running:
            return

        task = self._task_var.get().strip()
        if not task:
            messagebox.showwarning("Warning", "Enter a task for the AI!")
            return

        self._ai = self._build_ai_provider()

        mode_map = {
            "AUTO": ControlMode.AUTO,
            "STEP": ControlMode.STEP,
            "WATCH": ControlMode.WATCH,
        }
        mode = mode_map.get(self._mode_var.get(), ControlMode.AUTO)

        self._controller = AIRobotControllerService(
            robot_service=self.robot,
            kinematics_service=self.kin,
            ai_provider=self._ai,
            mode=mode,
            ai_interval=self._interval_var.get(),
        )
        self._controller.set_task(task)
        self._controller.set_frame_callback(self._on_frame)
        self._controller.set_command_callback(self._on_command)
        self._controller.set_state_callback(self._on_state)
        self._controller.set_log_callback(self._on_log)

        try:
            ok = self._controller.start()
            if not ok:
                messagebox.showerror(
                    "Error",
                    "Failed to start AI controller.\nCheck camera and AI provider connection.",
                )
                return

            self._is_running = True
            self._start_btn.config(state="disabled")
            self._stop_btn.config(state="normal")

            if mode == ControlMode.STEP:
                self._step_btn.config(state="normal")

            self._status_label.config(text=f"RUNNING ({mode.name})", fg=FANUC_GREEN)
            self._log_ai(f"=== AI started | task: '{task}' | mode: {mode.name} ===", "response")
            self.log(f"AI Robot Controller started: '{task}'", "success")

        except Exception as e:
            messagebox.showerror("Error", f"Start failed:\n{e}")

    def _stop(self):
        if not self._is_running:
            return

        if self._controller:
            self._controller.stop()
            self._controller = None

        self._is_running = False
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._step_btn.config(state="disabled")
        self._status_label.config(text="STOPPED", fg=FANUC_RED)
        self._video_label.config(image="", text="Camera OFF\nPress ▶ START AI", fg=FANUC_GRAY)
        self._photo_image = None
        self._log_ai("=== AI stopped ===", "warn")
        self.log("AI Robot Controller stopped", "warning")

    def _trigger_step(self):
        if self._controller and self._is_running:
            self._controller.trigger_step()
            self._log_ai("→ Manual step triggered", "query")

    # ════════════════════════════════════════════
    #  Callbacks от контроллера
    # ════════════════════════════════════════════

    def _on_frame(self, rgb: np.ndarray):
        """Новый кадр с камеры."""
        try:
            h, w = rgb.shape[:2]
            max_w, max_h = 520, 400
            pil = Image.fromarray(rgb)
            if w > max_w or h > max_h:
                s = min(max_w / w, max_h / h)
                pil = pil.resize((int(w * s), int(h * s)), Image.LANCZOS)
            self._video_label.after(0, self._show_frame, pil)
        except Exception:
            pass

    def _show_frame(self, pil_img: Image.Image):
        try:
            photo = ImageTk.PhotoImage(pil_img)
            self._photo_image = photo
            self._video_label.config(image=photo, text="")
        except Exception:
            pass

    def _on_command(self, cmd: AICommand):
        """Новая команда от ИИ."""
        tag = "response" if cmd.success else "error"
        msg = (
            f"← action={cmd.action} "
            f"Δjoints={[round(d, 1) for d in cmd.joint_deltas]} "
            f"grip={cmd.gripper_open} "
            f"conf={cmd.confidence:.2f}"
        )
        self._log_ai(msg, tag)
        if cmd.reason:
            self._log_ai(f"   reason: {cmd.reason[:80]}", "info")
        if not cmd.success:
            self._log_ai(f"   error: {cmd.error}", "error")

    def _on_state(self, state: ControllerState):
        """Обновление состояния контроллера."""
        self.after(0, self._update_status, state)

    def _on_log(self, msg: str, level: str):
        """Лог от контроллера."""
        level_map = {
            "info": "info",
            "success": "response",
            "warning": "warn",
            "error": "error",
        }
        self._log_ai(msg, level_map.get(level, "info"))

    # ════════════════════════════════════════════
    #  UI helpers
    # ════════════════════════════════════════════

    def _log_ai(self, text: str, tag: str = "info"):
        def _append():
            self._ai_log.config(state="normal")
            ts = time.strftime("%H:%M:%S")
            self._ai_log.insert("end", f"[{ts}] ", "time")
            self._ai_log.insert("end", text + "\n", tag)
            self._ai_log.see("end")
            self._ai_log.config(state="disabled")

        self.after(0, _append)

    def _update_status(self, state: ControllerState):
        cmd = state.last_command

        lines = [
            f"Mode:    {state.mode.upper()}",
            f"Task:    {state.task[:45]}",
            f"Steps:   {state.step_count}",
            f"FPS:     {state.fps:.1f}",
            f"Latency: {state.last_ai_latency:.2f}s",
            f"Model:   {state.ai_model[:30]}",
            "",
        ]

        if cmd:
            lines += [
                f"Action:  {cmd.action}",
                f"Δjoints: {[round(d, 1) for d in cmd.joint_deltas]}",
                f"Gripper: {cmd.gripper_open}",
                f"Conf:    {cmd.confidence:.2f}",
                f"Reason:  {cmd.reason[:40]}",
            ]

        if state.joint_angles:
            lines.append("")
            lines.append(f"Joints: {[round(a, 1) for a in state.joint_angles]}")

        if state.error:
            lines.append(f"ERROR: {state.error[:40]}")

        self._status_text.config(state="normal")
        self._status_text.delete("1.0", "end")
        self._status_text.insert("1.0", "\n".join(lines))
        self._status_text.config(state="disabled")

        if state.is_running:
            if cmd and cmd.action not in ("idle", ""):
                self._status_label.config(text=f"⚡ {cmd.action.upper()}", fg=FANUC_GREEN)
            else:
                self._status_label.config(text=f"● {state.mode.upper()}", fg=FANUC_BLUE)

    # ════════════════════════════════════════════
    #  Cleanup
    # ════════════════════════════════════════════

    def destroy(self):
        if self._is_running:
            self._stop()
        super().destroy()
