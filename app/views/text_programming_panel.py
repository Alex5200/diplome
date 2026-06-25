#!/usr/bin/env python3
"""TextProgrammingPanel — редактор текстовых робот-программ с панелью описания."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
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
from app.services.text_program_service import TextProgramService

_ACCENT = "#7dd3c0"
_ACCENT_H = "#5bb8a4"
_BORDER = "#e8e4e0"
_CARD_BG = FANUC_PANEL

_SYNTAX_HELP = """\
╔══════════════════════════════════════════╗
║         ROBOT SCRIPT — СИНТАКСИС        ║
╚══════════════════════════════════════════╝

═══ ДВИЖЕНИЕ ═══
MOVE_J(1, 90)      сустав 1 → 90°
MOVE_XYZ(200,0,300)  в точку XYZ мм
HOME()             все суставы в 0
CENTER()           все суставы в 2048

═══ НАСТРОЙКИ ═══
SPEED(50)          скорость 0-100%
TORQUE(1, ON)      момент ВКЛ (1-6, ALL)
GRIPPER(OPEN)      захват открыть
GRIPPER(CLOSE,80)  захват закрыть 80%

═══ ОЖИДАНИЕ ═══
WAIT(1.5)          пауза 1.5 сек
PRINT("text")      сообщение в лог

═══ ЦИКЛЫ ═══
FOR i = 1 TO 5
    ... код ...
END_FOR

WHILE i < 180
    ... код ...
END_WHILE

═══ УСЛОВИЯ ═══
IF position > 2000
    ... код ...
ELSE
    ... код ...
END_IF

═══ МЕТКИ / ПЕРЕХОДЫ ═══
LABEL(start)
GOTO(start)

═══ ПЕРЕМЕННЫЕ ═══
angle = 90
MOVE_J(1, angle)

═══ КОММЕНТАРИИ ═══
// это комментарий
"""


def _darken(hex_color: str, factor: float = 0.15) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _make_btn(parent, text, fg_color, command, width=None, height=32):
    kwargs = dict(
        text=text,
        fg_color=fg_color,
        hover_color=_darken(fg_color),
        text_color=contrast_text_color(fg_color),
        height=height,
        corner_radius=8,
        font=ctk.CTkFont("Segoe UI", 10, "bold"),
        command=command,
    )
    if width is not None:
        kwargs["width"] = width
    return ctk.CTkButton(parent, **kwargs)


class TextProgrammingPanel(ctk.CTkFrame):
    """Панель текстового программирования робота."""

    EXAMPLE_PROGRAMS = {
        "Pick & Place": """\
// Pick and Place — 3 цикла
SPEED(60)
FOR i = 1 TO 3
    // Move to object
    MOVE_XYZ(150, 0, 200)
    MOVE_XYZ(150, 0, 50)
    GRIPPER(CLOSE, 70)
    WAIT(0.5)
    // Lift
    MOVE_XYZ(150, 0, 200)
    // Move to drop zone
    MOVE_XYZ(-150, 0, 200)
    MOVE_XYZ(-150, 0, 50)
    GRIPPER(OPEN)
    WAIT(0.3)
    // Back up
    MOVE_XYZ(-150, 0, 200)
END_FOR
HOME()
PRINT("Pick & Place complete")
""",
        "Draw Circle": """\
// Draw circle — движение по окружности
SPEED(40)
CENTER()
WAIT(0.5)
MOVE_XYZ(150, 0, 150)
angle = 0
WHILE angle <= 360
    x = 150 + 50 * COS(angle)
    y = 50 * SIN(angle)
    z = 150
    MOVE_XYZ(x, y, z)
    angle = angle + 30
END_WHILE
HOME()
PRINT("Circle complete")
""",
        "Conditional Demo": """\
// Демонстрация условий
SPEED(50)
CENTER()
position = 2500
IF position > 2000
    MOVE_J(2, 45)
    MOVE_J(3, -30)
    PRINT("Position > 2000 — moving up")
ELSE
    MOVE_J(2, -45)
    MOVE_J(3, 30)
    PRINT("Position <= 2000 — moving down")
END_IF
WAIT(1)
HOME()
PRINT("Conditional demo done")
""",
        "Screw Insertion": """\
// Screw insertion sequence
SPEED(30)
FOR attempt = 1 TO 3
    // Approach
    MOVE_XYZ(100, 0, 150)
    MOVE_XYZ(100, 0, 80)
    GRIPPER(CLOSE, 50)
    WAIT(0.3)
    // Screw in (rotate wrist)
    MOVE_J(5, 180)
    WAIT(0.2)
    MOVE_J(5, 90)
    WAIT(0.2)
    MOVE_J(5, 0)
    WAIT(0.2)
    // Release
    GRIPPER(OPEN)
    WAIT(0.3)
    // Retract
    MOVE_XYZ(100, 0, 200)
    MOVE_XYZ(0, 0, 200)
END_FOR
PRINT("Screw insertion done")
""",
    }

    def __init__(self, parent, robot_service, kinematics_service, log_callback):
        super().__init__(parent, fg_color=FANUC_BG, corner_radius=0)
        self.robot_service = robot_service
        self.kinematics_service = kinematics_service
        self.log_cb = log_callback

        # Сервис
        controller = getattr(robot_service, "_MotorController__controller", None) or getattr(robot_service, "controller", None)
        self.text_prog = TextProgramService(controller)

        self._running = False
        self._thread: threading.Thread | None = None

        self._create_widgets()

    def _log(self, msg: str, level: str = "info"):
        if self.log_cb:
            self.log_cb(msg, level)
        else:
            print(f"[{level}] {msg}")

    def _create_widgets(self):
        main = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        main.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Header ──
        hdr = ctk.CTkFrame(main, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        hdr.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            hdr, text="TEXT PROGRAMMING — ROBOT SCRIPT",
            font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=_ACCENT,
        ).pack(side="left", padx=14, pady=8)

        # ── Paned: editor | help ──
        paned = ctk.CTkFrame(main, fg_color=FANUC_BG, corner_radius=0)
        paned.pack(fill="both", expand=True)

        # == LEFT: Code editor ==
        left = ctk.CTkFrame(paned, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        ctk.CTkLabel(
            left, text="EDITOR", font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=_ACCENT,
        ).pack(anchor="w", padx=10, pady=(6, 2))

        editor_frame = ctk.CTkFrame(left, fg_color="#1e1e2e", corner_radius=6)
        editor_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.code_text = tk.Text(
            editor_frame,
            wrap="none",
            font=("Consolas", 11),
            bg="#1e1e2e",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            selectbackground="#45475a",
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=6,
            undo=True,
            height=20,
        )
        self.code_text.pack(side="left", fill="both", expand=True)

        sb_y = ctk.CTkScrollbar(editor_frame, command=self.code_text.yview,
                                 button_color=_ACCENT, button_hover_color=_ACCENT_H)
        sb_y.pack(side="right", fill="y")
        self.code_text.configure(yscrollcommand=sb_y.set)

        sb_x = ctk.CTkScrollbar(left, orientation="horizontal", command=self.code_text.xview,
                                 button_color=_ACCENT, button_hover_color=_ACCENT_H)
        sb_x.pack(fill="x", padx=8, pady=(0, 8))
        self.code_text.configure(xscrollcommand=sb_x.set)

        # Default example
        self.code_text.insert("1.0", self.EXAMPLE_PROGRAMS["Pick & Place"])

        # == RIGHT: Help panel ==
        right = ctk.CTkFrame(paned, fg_color=_CARD_BG, corner_radius=10, border_width=1, border_color=_BORDER)
        right.pack(side="right", fill="y", padx=(4, 0))

        ctk.CTkLabel(
            right, text="SYNTAX REFERENCE",
            font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=_ACCENT,
        ).pack(anchor="w", padx=10, pady=(6, 2))

        help_text = tk.Text(
            right,
            wrap="word",
            font=("Consolas", 8),
            bg="#1e1e2e",
            fg="#a6adc8",
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=4,
            width=42,
            height=22,
            state="normal",
        )
        help_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        help_text.insert("1.0", _SYNTAX_HELP)
        help_text.configure(state="disabled")

        # ── Action bar ──
        bar = ctk.CTkFrame(main, fg_color=FANUC_BG, corner_radius=0)
        bar.pack(fill="x", pady=(6, 0))

        actions = [
            ("RUN",     self._run,      FANUC_GREEN),
            ("STOP",    self._stop,     FANUC_RED),
            ("CLEAR",   self._clear,    FANUC_ORANGE),
            ("SAVE",    self._save,     FANUC_BLUE),
            ("LOAD",    self._load,     FANUC_GRAY),
        ]
        for txt, cmd, fg in actions:
            _make_btn(bar, txt, fg, cmd, width=72).pack(side="left", padx=2)

        # Example dropdown
        ctk.CTkLabel(bar, text="Examples:", font=ctk.CTkFont("Segoe UI", 9), text_color=FANUC_TEXT2
                     ).pack(side="left", padx=(16, 4))

        self.example_var = tk.StringVar(value="Pick & Place")
        example_menu = ctk.CTkOptionMenu(
            bar,
            variable=self.example_var,
            values=list(self.EXAMPLE_PROGRAMS.keys()),
            fg_color=_CARD_BG,
            button_color=_ACCENT,
            button_hover_color=_ACCENT_H,
            text_color=FANUC_TEXT,
            font=ctk.CTkFont("Segoe UI", 9),
            command=self._load_example,
            width=140,
        )
        example_menu.pack(side="left")

        # Status
        self.status_lbl = ctk.CTkLabel(
            bar, text="Ready", font=ctk.CTkFont("Consolas", 9), text_color=FANUC_GRAY,
        )
        self.status_lbl.pack(side="right", padx=8)

    def _load_example(self, name: str):
        code = self.EXAMPLE_PROGRAMS.get(name, "")
        self.code_text.delete("1.0", "end")
        self.code_text.insert("1.0", code)
        self.status_lbl.configure(text=f"Loaded: {name}")

    def _get_code(self) -> str:
        return self.code_text.get("1.0", "end-1c").strip()

    def _run(self):
        code = self._get_code()
        if not code:
            messagebox.showwarning("Warning", "Code is empty!")
            return
        if self._running:
            return
        self._running = True
        self.status_lbl.configure(text="Running...", text_color=_ACCENT)
        self._thread = threading.Thread(target=self._execute, args=(code,), daemon=True)
        self._thread.start()

    def _execute(self, code: str):
        try:
            self.text_prog.execute(code, log_callback=self._log)
        except Exception as e:
            self._log(f"Execution error: {e}", "error")
        finally:
            self._running = False
            self.after(0, lambda: self.status_lbl.configure(text="Completed", text_color=FANUC_GREEN))

    def _stop(self):
        self.text_prog.stop()
        self._running = False
        self.status_lbl.configure(text="Stopped", text_color=FANUC_RED)

    def _clear(self):
        self.code_text.delete("1.0", "end")
        self.status_lbl.configure(text="Cleared")

    def _save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".rbt",
            filetypes=[("Robot Script", "*.rbt"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Robot Script",
        )
        if path:
            Path(path).write_text(self._get_code(), encoding="utf-8")
            self._log(f"Saved to {path}", "success")
            self.status_lbl.configure(text=f"Saved: {Path(path).name}")

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("Robot Script", "*.rbt"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Load Robot Script",
        )
        if path:
            code = Path(path).read_text(encoding="utf-8")
            self.code_text.delete("1.0", "end")
            self.code_text.insert("1.0", code)
            self._log(f"Loaded from {path}", "success")
            self.status_lbl.configure(text=f"Loaded: {Path(path).name}")
