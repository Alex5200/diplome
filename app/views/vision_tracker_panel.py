#!/usr/bin/env python3

"""
Vision Tracker Panel — GUI для AI-визуального слежения за объектом.

Ключевые элементы:
- Живой вывод камеры (preview всегда работает)
- Лог ответов LLM (raw text от модели)
- Настройки AI-провайдера (Ollama / LM Studio / OpenAI / Custom)
- Объект для слежения, камера, PID
- Кнопки: START/STOP трекинг, SEND ONCE (одиночный запрос к VLM)
"""

import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

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
from app.services.camera_service import CameraService
from app.services.vision_tracker_service import VisionTrackerService


class VisionTrackerPanel(ttk.Frame):
    """GUI-панель визуального слежения за объектом через AI."""

    PROVIDERS = {
        "Ollama (Local)": "ollama",
        "LM Studio (Local/Remote)": "lm_studio",
        "OpenAI API": "openai",
        "Custom (OpenAI-compatible)": "custom",
    }

    DEFAULT_URLS = {
        "ollama": "http://localhost:11434",
        "lm_studio": "http://localhost:1234/v1",
        "openai": "https://api.openai.com/v1",
        "custom": "http://localhost:8080/v1",
    }

    DEFAULT_MODELS = {
        "ollama": "qwen2.5-vl",
        "lm_studio": "qwen2.5-vl-7b",
        "openai": "gpt-4o",
        "custom": "",
    }

    def __init__(self, parent, robot_service, kinematics_service, log_callback=None):
        super().__init__(parent)
        self.robot = robot_service
        self.kin = kinematics_service
        self.log = log_callback or (lambda msg, lvl="info": None)

        self._tracker: VisionTrackerService | None = None
        self._ai: AIProvider | None = None
        self._is_tracking = False
        self._photo_image = None  # prevent GC

        # Камера preview (через CameraService / OpenCV)
        self._camera = CameraService()
        self._camera_running = False
        self._current_frame: np.ndarray | None = None
        self._frame_lock = threading.Lock()

        self._create_widgets()

    # ════════════════════════════════════════════════════════════
    #  UI
    # ════════════════════════════════════════════════════════════

    def _create_widgets(self):
        # Верхняя часть (настройки) + нижняя (камера + лог)
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=(8, 4))
        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._create_settings(top)
        self._create_bottom(bottom)

    def _create_settings(self, parent):
        # ── Row 1: Provider + кнопки ──
        r1 = tk.Frame(parent, bg=FANUC_PANEL)
        r1.pack(fill="x", pady=2)

        tk.Label(r1, text="Provider:", font=("Arial", 10), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left"
        )
        self._provider_var = tk.StringVar(value="LM Studio (Local/Remote)")
        ttk.Combobox(
            r1,
            textvariable=self._provider_var,
            values=list(self.PROVIDERS.keys()),
            state="readonly",
            width=24,
            font=("Consolas", 9),
        ).pack(side="left", padx=4)
        self._provider_var.trace_add("write", lambda *_: self._on_provider_change())

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
        ).pack(side="left", padx=3)
        tk.Button(
            r1,
            text="MODELS",
            font=("Arial", 8, "bold"),
            bg=FANUC_GRAY,
            fg="white",
            bd=0,
            padx=8,
            pady=2,
            command=self._list_models,
        ).pack(side="left", padx=3)

        self._conn_label = tk.Label(
            r1, text="", font=("Consolas", 9), bg=FANUC_PANEL, fg=FANUC_GRAY
        )
        self._conn_label.pack(side="right", padx=6)

        # ── Row 2: URL + Model + Key ──
        r2 = tk.Frame(parent, bg=FANUC_PANEL)
        r2.pack(fill="x", pady=2)

        tk.Label(r2, text="URL:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left"
        )
        self._url_var = tk.StringVar(value=self.DEFAULT_URLS["lm_studio"])
        ttk.Entry(r2, textvariable=self._url_var, width=30, font=("Consolas", 9)).pack(
            side="left", padx=3
        )

        tk.Label(r2, text="Model:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left", padx=(8, 0)
        )
        self._model_var = tk.StringVar(value=self.DEFAULT_MODELS["lm_studio"])
        self._model_combo = ttk.Combobox(
            r2, textvariable=self._model_var, width=22, font=("Consolas", 9)
        )
        self._model_combo.pack(side="left", padx=3)

        tk.Button(
            r2,
            text="↻",
            font=("Arial", 9),
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
            bd=0,
            padx=4,
            pady=0,
            command=self._fetch_models,
        ).pack(side="left", padx=1)

        tk.Label(r2, text="Key:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left", padx=(8, 0)
        )
        self._apikey_var = tk.StringVar(value="lm-studio")
        ttk.Entry(r2, textvariable=self._apikey_var, width=14, font=("Consolas", 9), show="•").pack(
            side="left", padx=3
        )

        # ── Row 3: Target + Camera + Interval ──
        r3 = tk.Frame(parent, bg=FANUC_PANEL)
        r3.pack(fill="x", pady=2)

        tk.Label(r3, text="Target:", font=("Arial", 10, "bold"), bg=FANUC_PANEL, fg=FANUC_RED).pack(
            side="left"
        )
        self._target_var = tk.StringVar(value="red ball")
        ttk.Entry(r3, textvariable=self._target_var, width=24, font=("Consolas", 10)).pack(
            side="left", padx=4
        )

        tk.Label(r3, text="Cam:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left", padx=(8, 0)
        )
        self._camera_var = tk.StringVar(value="0")
        self._camera_combo = ttk.Combobox(
            r3, textvariable=self._camera_var, width=18, font=("Consolas", 9), state="readonly"
        )
        self._camera_combo.pack(side="left", padx=3)

        tk.Button(
            r3,
            text="🔍",
            font=("Arial", 9),
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
            bd=0,
            padx=4,
            pady=0,
            command=self._scan_cameras,
        ).pack(side="left", padx=1)

        # Авто-сканировать при создании
        self.after(100, self._scan_cameras)

        tk.Label(r3, text="Interval:", font=("Arial", 9), bg=FANUC_PANEL, fg=FANUC_TEXT).pack(
            side="left", padx=(8, 0)
        )
        self._interval_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(
            r3,
            from_=0.1,
            to=5.0,
            textvariable=self._interval_var,
            width=5,
            increment=0.1,
            font=("Consolas", 9),
        ).pack(side="left", padx=3)

        # ── Row 4: Buttons ──
        r4 = tk.Frame(parent, bg=FANUC_BG)
        r4.pack(fill="x", pady=(4, 2))

        tk.Button(
            r4,
            text="📷 CAMERA ON",
            font=("Arial", 9, "bold"),
            bg=FANUC_BLUE,
            fg="white",
            bd=0,
            padx=12,
            pady=4,
            command=self._toggle_camera,
        ).pack(side="left", padx=3)

        tk.Button(
            r4,
            text="📤 SEND ONCE",
            font=("Arial", 9, "bold"),
            bg=FANUC_ORANGE,
            fg="white",
            bd=0,
            padx=12,
            pady=4,
            command=self._send_once,
        ).pack(side="left", padx=3)

        self._start_btn = tk.Button(
            r4,
            text="▶ START TRACK",
            font=("Arial", 10, "bold"),
            bg=FANUC_GREEN,
            fg="black",
            bd=0,
            padx=16,
            pady=4,
            command=self._start_tracking,
        )
        self._start_btn.pack(side="left", padx=3)

        self._stop_btn = tk.Button(
            r4,
            text="⏹ STOP",
            font=("Arial", 10, "bold"),
            bg=FANUC_RED,
            fg="white",
            bd=0,
            padx=16,
            pady=4,
            command=self._stop_tracking,
            state="disabled",
        )
        self._stop_btn.pack(side="left", padx=3)

        tk.Button(
            r4,
            text="↻ TARGET",
            font=("Arial", 8, "bold"),
            bg=FANUC_GRAY,
            fg="white",
            bd=0,
            padx=8,
            pady=4,
            command=self._update_target,
        ).pack(side="left", padx=3)

        self._status_label = tk.Label(
            r4, text="IDLE", font=("Consolas", 10, "bold"), bg=FANUC_BG, fg=FANUC_GRAY
        )
        self._status_label.pack(side="right", padx=8)

    def _create_bottom(self, parent):
        # Левая: камера  |  Правая: LLM лог + статус
        left = ttk.LabelFrame(parent, text="CAMERA")
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        # Контейнер с фиксированным минимальным размером для видео
        video_container = tk.Frame(left, bg="black", width=500, height=380)
        video_container.pack(fill="both", expand=True, padx=4, pady=4)
        video_container.pack_propagate(False)

        self._video_label = tk.Label(
            video_container, bg="black", text="Camera OFF", fg=FANUC_GRAY, font=("Consolas", 12)
        )
        self._video_label.pack(fill="both", expand=True)

        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=False)

        # LLM Response log
        llm_frame = ttk.LabelFrame(right, text="LLM RESPONSES")
        llm_frame.pack(fill="both", expand=True, pady=(0, 4))

        self._llm_log = scrolledtext.ScrolledText(
            llm_frame,
            width=38,
            height=10,
            font=("Consolas", 8),
            bg="#1a1a2e",
            fg="#e0e0e0",
            insertbackground="white",
            state="disabled",
            wrap="word",
            bd=0,
        )
        self._llm_log.pack(fill="both", expand=True, padx=4, pady=4)
        self._llm_log.tag_configure("found", foreground="#7dd3c0")
        self._llm_log.tag_configure("notfound", foreground="#e8927c")
        self._llm_log.tag_configure("error", foreground="#ff6b6b")
        self._llm_log.tag_configure("time", foreground="#8ab4f8")
        self._llm_log.tag_configure("prompt", foreground="#f5b971")

        # Status info
        info_frame = ttk.LabelFrame(right, text="STATUS")
        info_frame.pack(fill="x", pady=(0, 0))

        self._info_text = tk.Text(
            info_frame,
            width=38,
            height=8,
            font=("Consolas", 8),
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
            state="disabled",
            wrap="word",
            bd=0,
        )
        self._info_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ════════════════════════════════════════════════════════════
    #  Camera Preview (независимо от трекинга)
    # ════════════════════════════════════════════════════════════

    def _scan_cameras(self):
        """Сканировать доступные камеры через OpenCV."""

        def _do_scan():
            cameras = CameraService.scan_cameras_labels(max_index=8)
            self.after(0, lambda: self._update_camera_list(cameras))
            self._log_llm(f"Found {len(cameras)} camera(s)", "found")

        self._log_llm("Scanning cameras...", "time")
        threading.Thread(target=_do_scan, daemon=True).start()

    def _update_camera_list(self, cameras: list[str]):
        if cameras:
            self._camera_combo["values"] = cameras
            self._camera_combo.current(0)
            self._log_llm(f"Found {len(cameras)} camera(s): {cameras}", "found")
            self.log(f"Cameras: {cameras}", "info")
        else:
            self._camera_combo["values"] = ["No cameras found"]
            self._log_llm("No cameras found!", "error")

    def _get_camera_id(self) -> int:
        """Извлечь ID камеры из комбобокса ('0: 640x480 ...' → 0)."""
        val = self._camera_var.get()
        try:
            return int(val.split(":")[0])
        except (ValueError, IndexError):
            return 0

    def _toggle_camera(self):
        if self._camera_running:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        if self._camera_running:
            return

        cam_id = self._get_camera_id()
        self._video_label.config(text=f"Opening camera {cam_id}...", fg=FANUC_ORANGE)
        self.update_idletasks()

        self._camera.set_frame_callback(self._on_camera_frame)
        self._camera.set_error_callback(lambda err: self._log_llm(f"Camera error: {err}", "error"))

        ok = self._camera.start(cam_id)
        if not ok:
            self._video_label.config(text="Camera FAILED", fg=FANUC_RED)
            self._log_llm(f"Cannot open camera {cam_id}", "error")
            self.log(f"Camera {cam_id} failed to open", "error")
            return

        self._camera_running = True
        self._log_llm(f"Camera {cam_id} opened (OpenCV)", "found")
        self.log("Camera started", "info")

    def _stop_camera(self):
        self._camera_running = False
        self._camera.stop()
        self._video_label.config(image="", text="Camera OFF", fg=FANUC_GRAY)
        self._photo_image = None
        self._log_llm("Camera stopped", "notfound")
        self.log("Camera stopped", "info")

    def _on_camera_frame(self, rgb: np.ndarray):
        """Callback от CameraService — новый RGB кадр."""
        with self._frame_lock:
            self._current_frame = rgb.copy()
        self._push_rgb_to_ui(rgb)

    def _push_rgb_to_ui(self, rgb: np.ndarray):
        """Отправить RGB-кадр в главный поток для отображения."""
        try:
            h, w = rgb.shape[:2]
            max_w, max_h = 500, 380
            pil_img = Image.fromarray(rgb)
            if w > max_w or h > max_h:
                s = min(max_w / w, max_h / h)
                pil_img = pil_img.resize((int(w * s), int(h * s)), Image.LANCZOS)
            self._video_label.after(0, self._display_pil_image, pil_img)
        except Exception:
            pass

    def _display_pil_image(self, pil_img):
        """Вызывается ТОЛЬКО в главном потоке — создаёт PhotoImage и показывает."""
        try:
            photo = ImageTk.PhotoImage(pil_img)
            self._photo_image = photo  # prevent GC
            self._video_label.config(image=photo, text="")
        except Exception:
            pass

    def _draw_bbox_on_frame(self, rgb_frame: np.ndarray, bbox: list, label: str):
        """Нарисовать bounding box на RGB-кадре через PIL и показать."""
        from PIL import ImageDraw

        h, w = rgb_frame.shape[:2]
        x1, y1, x2, y2 = [max(0.0, min(1.0, float(v))) for v in bbox]
        pil_img = Image.fromarray(rgb_frame)
        draw = ImageDraw.Draw(pil_img)
        draw.rectangle(
            [int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)],
            outline="lime",
            width=3,
        )
        draw.text((int(x1 * w), int(y1 * h) - 14), label, fill="lime")
        self._video_label.after(0, self._display_pil_image, pil_img)

    # ════════════════════════════════════════════════════════════
    #  AI Provider
    # ════════════════════════════════════════════════════════════

    def _on_provider_change(self):
        key = self.PROVIDERS.get(self._provider_var.get(), "ollama")
        self._url_var.set(self.DEFAULT_URLS.get(key, ""))
        self._model_var.set(self.DEFAULT_MODELS.get(key, ""))
        self._apikey_var.set("lm-studio" if key == "lm_studio" else "")

    def _build_ai_provider(self) -> AIProvider:
        key = self.PROVIDERS.get(self._provider_var.get(), "ollama")
        url = self._url_var.get().strip()
        model = self._model_var.get().strip()
        api_key = self._apikey_var.get().strip()

        if key == "ollama":
            return AIProvider.ollama(model=model, url=url)
        elif key == "lm_studio":
            return AIProvider.lm_studio(url=url, model=model, api_key=api_key or "lm-studio")
        elif key == "openai":
            return AIProvider.openai(api_key=api_key, model=model)
        else:
            return AIProvider.custom(url=url, model=model, api_key=api_key)

    def _check_connection(self):
        ai = self._build_ai_provider()
        self._conn_label.config(text="Checking...", fg=FANUC_ORANGE)
        self.update_idletasks()

        def check():
            ok = ai.is_available()
            self.after(
                0,
                lambda: self._conn_label.config(
                    text="✓ Connected" if ok else "✗ Unreachable",
                    fg=FANUC_GREEN if ok else FANUC_RED,
                ),
            )

        threading.Thread(target=check, daemon=True).start()

    def _fetch_models(self):
        """Загрузить список моделей с сервера и заполнить выпадающий список."""
        ai = self._build_ai_provider()
        self._conn_label.config(text="Loading models...", fg=FANUC_ORANGE)

        def fetch():
            models = ai.list_models()
            self.after(0, lambda: self._populate_model_combo(models))

        threading.Thread(target=fetch, daemon=True).start()

    def _populate_model_combo(self, models: list[str]):
        if models:
            self._model_combo["values"] = models
            # Выбрать первую если текущая не в списке
            if self._model_var.get() not in models:
                self._model_combo.current(0)
            self._conn_label.config(text=f"{len(models)} models", fg=FANUC_GREEN)
            self._log_llm(f"Models: {models}", "found")
        else:
            self._model_combo["values"] = []
            self._conn_label.config(text="No models", fg=FANUC_RED)
            self._log_llm("No models found on server", "error")

    def _list_models(self):
        """Кнопка MODELS — загрузить + показать popup."""
        ai = self._build_ai_provider()
        self._conn_label.config(text="Loading...", fg=FANUC_ORANGE)

        def fetch():
            models = ai.list_models()
            self.after(0, lambda: self._show_models_result(models))

        threading.Thread(target=fetch, daemon=True).start()

    def _show_models_result(self, models: list[str]):
        # Заполнить комбо
        self._populate_model_combo(models)
        # Показать popup
        if models:
            txt = "\n".join(f"  • {m}" for m in models)
            messagebox.showinfo("Models", f"Available:\n\n{txt}")
        else:
            messagebox.showwarning("Models", "No models found")

    # ════════════════════════════════════════════════════════════
    #  LLM Log
    # ════════════════════════════════════════════════════════════

    def _log_llm(self, text: str, tag: str = ""):
        """Добавить запись в лог LLM ответов."""

        def _append():
            self._llm_log.config(state="normal")
            ts = time.strftime("%H:%M:%S")
            self._llm_log.insert("end", f"[{ts}] ", "time")
            if tag:
                self._llm_log.insert("end", text + "\n", tag)
            else:
                self._llm_log.insert("end", text + "\n")
            self._llm_log.see("end")
            self._llm_log.config(state="disabled")

        self.after(0, _append)

    # ════════════════════════════════════════════════════════════
    #  SEND ONCE — одиночный запрос к VLM с текущим кадром
    # ════════════════════════════════════════════════════════════

    def _send_once(self):
        """Отправить один кадр в VLM и показать ответ."""
        with self._frame_lock:
            frame = self._current_frame.copy() if self._current_frame is not None else None

        if frame is None:
            messagebox.showwarning("Warning", "Turn on the camera first!")
            return

        target = self._target_var.get().strip() or "any object"
        ai = self._build_ai_provider()

        prompt = (
            f'Find the object: "{target}". '
            f'If visible, respond with JSON: {{"found": true, "label": "{target}", '
            f'"bbox": [x1, y1, x2, y2]}} (normalized 0-1). '
            f'If NOT visible: {{"found": false}}'
        )

        self._log_llm(f'→ Prompt: "{target}"', "prompt")
        self._status_label.config(text="SENDING...", fg=FANUC_ORANGE)

        def do_request():
            t0 = time.time()
            resp = ai.chat_json(prompt, images=[frame])
            dt = time.time() - t0

            if resp.success:
                self._log_llm(
                    f"← [{dt:.1f}s] {resp.content}",
                    "found" if resp.json_data and resp.json_data.get("found") else "notfound",
                )

                # Нарисовать bbox на кадре если найден
                if resp.json_data and resp.json_data.get("found"):
                    bbox = resp.json_data.get("bbox", [])
                    if len(bbox) == 4:
                        self._draw_bbox_on_frame(frame, bbox, target)
            else:
                self._log_llm(f"← ERROR: {resp.error}", "error")

            self.after(
                0, lambda: self._status_label.config(text=f"DONE ({dt:.1f}s)", fg=FANUC_BLUE)
            )

        threading.Thread(target=do_request, daemon=True).start()

    # ════════════════════════════════════════════════════════════
    #  Tracking (full loop)
    # ════════════════════════════════════════════════════════════

    def _start_tracking(self):
        if self._is_tracking:
            return

        target = self._target_var.get().strip()
        if not target:
            messagebox.showwarning("Warning", "Enter a target object!")
            return

        # Остановить preview камеру — трекер сам откроет камеру
        if self._camera_running:
            self._stop_camera()

        self._ai = self._build_ai_provider()
        self._tracker = VisionTrackerService(self.robot, self.kin, self._ai)
        self._tracker.configure(
            target_label=target,
            camera_id=self._get_camera_id(),
            vlm_interval=self._interval_var.get(),
        )
        self._tracker.set_frame_callback(self._on_tracker_frame)
        self._tracker.set_state_callback(self._on_tracker_state)

        try:
            self._tracker.start_tracking()
            self._is_tracking = True
            self._start_btn.config(state="disabled")
            self._stop_btn.config(state="normal")
            self._status_label.config(text="TRACKING", fg=FANUC_GREEN)
            self._log_llm(f"=== Tracking started: '{target}' ===", "found")
            self.log(f"Vision tracking: '{target}'", "success")
        except Exception as e:
            messagebox.showerror("Error", f"Failed:\n{e}")
            self.log(f"Tracking failed: {e}", "error")

    def _stop_tracking(self):
        if not self._is_tracking:
            return
        if self._tracker:
            self._tracker.stop_tracking()
        self._is_tracking = False
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._status_label.config(text="STOPPED", fg=FANUC_RED)
        self._log_llm("=== Tracking stopped ===", "notfound")
        self.log("Vision tracking stopped", "warning")

    def _update_target(self):
        target = self._target_var.get().strip()
        if self._tracker and self._is_tracking and target:
            self._tracker.set_target(target)
            self._log_llm(f"=== Target → '{target}' ===", "prompt")

    # ──────────── Tracker callbacks ────────────

    def _on_tracker_frame(self, frame: np.ndarray):
        # Трекер отдаёт BGR (из OpenCV) — конвертируем в RGB
        try:
            import cv2 as _cv2

            rgb = _cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)
        except ImportError:
            rgb = frame  # fallback — считаем что уже RGB
        self._push_rgb_to_ui(rgb)

    def _on_tracker_state(self, state):
        try:
            # Логировать каждый ответ VLM
            target = state.target
            if target.raw_response:
                tag = "found" if target.found else "notfound"
                self._log_llm(
                    f"[{state.vlm_latency:.1f}s] {target.raw_response[:120]}",
                    tag,
                )

            self.after(0, lambda: self._update_status(state))
        except Exception:
            pass

    def _update_status(self, state):
        target = state.target
        self._info_text.config(state="normal")
        self._info_text.delete("1.0", "end")

        lines = [
            f"Target: {state.target_label}",
            f"Found:  {'YES' if target.found else 'NO'}",
            f"Pos:    ({target.cx:.2f}, {target.cy:.2f})",
            f"Size:   {target.width:.2f} x {target.height:.2f}",
            f"Err:    ({state.error_x:+.3f}, {state.error_y:+.3f})",
            "",
            f"VLM:    {state.vlm_latency:.1f}s",
            f"FPS:    {state.fps:.0f}",
            f"Frames: {state.frame_count}",
            "",
            f"J1: {state.current_angles[0]:+6.1f}°  J4: {state.current_angles[3]:+6.1f}°",
            f"J2: {state.current_angles[1]:+6.1f}°  J5: {state.current_angles[4]:+6.1f}°",
            f"J3: {state.current_angles[2]:+6.1f}°  J6: {state.current_angles[5]:+6.1f}°",
        ]
        self._info_text.insert("1.0", "\n".join(lines))
        self._info_text.config(state="disabled")

        if target.found:
            self._status_label.config(text="TRACKING ●", fg=FANUC_GREEN)
        else:
            self._status_label.config(text="SEARCHING...", fg=FANUC_ORANGE)

    # ──────────── Cleanup ────────────

    def destroy(self):
        if self._is_tracking:
            self._stop_tracking()
        if self._camera_running:
            self._stop_camera()
        super().destroy()
