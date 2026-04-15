#!/usr/bin/env python3

"""
Block Programming Module — Расширенная версия с богатым набором блоков

Новые блоки:
- Движение по суставам (move_joint)
- Движение по XYZ координатам (move_xyz)
- Линейное перемещение (linear_move)
- Поворот ориентации (rotate)
- Дуговое движение (arc_move)
- Скорость (set_speed)
- Ускорение (set_accel)
- Цикл (loop)
- Условие if/else
- Логические операторы
- Захват/отпускание (gripper)
- Ожидание ввода (wait_input)
- Вывод сообщения (message)
- Переход к метке (goto/jump)
- Подпрограмма (subroutine)
"""

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass, field
from tkinter import messagebox, ttk

import customtkinter as ctk

from app.config.constants import (
    BLOCK_COLORS,
    DEFAULT_ACC,
    DEFAULT_SPEED,
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    FANUC_TEXT2,
    MAX_POSITION,
    MIN_POSITION,
)

# Drop indicator / accent colours
_DROP_COLOR = "#7dd3c0"  # teal — drop indicator & hover
_SELECTED_BORDER = "#8ab4f8"  # blue — selected block border

# Category accent strips
_CAT_ACCENTS = {
    "motion": "#a8e6cf",
    "control": "#b8d4e3",
    "wait": "#f8c471",
    "logic": "#f4d03f",
    "io": "#d7bde2",
}


@dataclass
class ProgramBlock:
    """Блок программы с расширенными параметрами."""

    id: int
    block_type: str
    params: dict = field(default_factory=dict)
    order: int = 0
    description: str = ""

    def __post_init__(self):
        if not self.description:
            self.description = self._generate_description()

    def _generate_description(self) -> str:
        """Генерация описания блока на основе параметров."""
        block_type = self.params.get("type", "unknown")

        descriptions = {
            "move_joint": lambda p: f"J{p.get('joint', 0) + 1} → {p.get('position', 2048)}",
            "move_xyz": lambda p: f"XYZ({p.get('x', 0)}, {p.get('y', 0)}, {p.get('z', 0)})",
            "linear_move": lambda p: f"Line → ({p.get('x', 0)}, {p.get('y', 0)}, {p.get('z', 0)})",
            "rotate": lambda p: (
                f"Rotate Rx:{p.get('rx', 0)} Ry:{p.get('ry', 0)} Rz:{p.get('rz', 0)}"
            ),
            "arc_move": lambda p: f"Arc → ({p.get('x', 0)}, {p.get('y', 0)}, {p.get('z', 0)})",
            "home": lambda p: (
                "Home All" if p.get("joint") == "all" else f"Home J{int(p.get('joint', 0)) + 1}"
            ),
            "center": lambda p: (
                "Center All" if p.get("joint") == "all" else f"Center J{int(p.get('joint', 0)) + 1}"
            ),
            "set_speed": lambda p: f"Speed: {p.get('speed', DEFAULT_SPEED)}",
            "set_accel": lambda p: f"Accel: {p.get('accel', DEFAULT_ACC)}",
            "wait_time": lambda p: f"Wait {p.get('seconds', 1)}s",
            "wait_input": lambda p: f"Wait Input #{p.get('input', 1)}",
            "torque_on": lambda p: f"Torque ON J{p.get('joint', 0) + 1}",
            "torque_off": lambda p: f"Torque OFF J{p.get('joint', 0) + 1}",
            "gripper": lambda p: (
                f"Gripper {'Close' if p.get('close', True) else 'Open'} ({p.get('force', 50)}%)"
            ),
            "message": lambda p: f"MSG: {p.get('text', '')[:20]}",
            "loop_start": lambda p: f"Loop x{p.get('count', 1)}",
            "loop_end": lambda p: "End Loop",
            "if": lambda p: f"If {p.get('condition', 'true')}",
            "else": lambda p: "Else",
            "endif": lambda p: "End If",
            "goto": lambda p: f"GoTo {p.get('label', 'LBL_1')}",
            "label": lambda p: f"Label: {p.get('name', 'LBL_1')}",
            "subroutine": lambda p: f"Call {p.get('name', 'SUB_1')}",
            "return": lambda p: "Return",
        }

        if block_type in descriptions:
            return descriptions[block_type](self.params)
        return f"Block {block_type}"


class BlockConfigDialog(ctk.CTkToplevel):
    """Диалог настройки параметров блока — CTk версия."""

    def __init__(
        self,
        parent: tk.Misc,
        block_type: str,
        params: dict,
        callback: Callable[[dict], None],
    ):
        super().__init__(parent)
        self.title(f"Configure — {block_type.replace('_', ' ').title()}")
        self.geometry("440x530")
        self.resizable(False, False)

        self.block_type = block_type
        self.params = params.copy()
        self.callback = callback

        self._create_widgets()
        self._load_params()

        self.transient(parent)
        self.grab_set()
        self.focus_set()
        self.lift()

    def _create_widgets(self):
        self.configure(fg_color=FANUC_BG)

        # Header
        header = ctk.CTkFrame(self, fg_color=FANUC_PANEL, corner_radius=0, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=self.block_type.replace("_", " ").upper(),
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=FANUC_TEXT,
        ).pack(expand=True)

        # Separator
        ctk.CTkFrame(self, fg_color="#e8e4e0", height=1, corner_radius=0).pack(fill="x")

        # Params area
        self.params_frame = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        self.params_frame.pack(fill="both", expand=True, padx=24, pady=14)

        self.input_vars: dict = {}
        self._create_input_fields()

        # Separator
        ctk.CTkFrame(self, fg_color="#e8e4e0", height=1, corner_radius=0).pack(fill="x")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color=FANUC_BG, corner_radius=0)
        btn_frame.pack(fill="x", padx=20, pady=14)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            font=ctk.CTkFont("Segoe UI", 10),
            fg_color=FANUC_PANEL,
            text_color=FANUC_TEXT,
            hover_color="#e8e4e0",
            border_width=1,
            border_color="#d0ccc8",
            width=100,
            height=34,
            corner_radius=8,
            command=self.destroy,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame,
            text="OK",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            fg_color=_DROP_COLOR,
            text_color=FANUC_TEXT,
            hover_color="#5bb8a4",
            width=100,
            height=34,
            corner_radius=8,
            command=self._on_ok,
        ).pack(side="right", padx=4)

    def _create_input_fields(self):
        """Создание полей ввода для конкретного типа блока."""
        field_configs = {
            "move_joint": [
                ("Joint:", "joint", 0, "int", (0, 5)),
                ("Position:", "position", 2048, "int", (MIN_POSITION, MAX_POSITION)),
                ("Speed:", "speed", DEFAULT_SPEED, "int", (100, 5000)),
            ],
            "move_xyz": [
                ("X (mm):", "x", 0.0, "float", (-500, 500)),
                ("Y (mm):", "y", 0.0, "float", (-500, 500)),
                ("Z (mm):", "z", 200.0, "float", (0, 500)),
                ("Speed:", "speed", DEFAULT_SPEED, "int", (100, 5000)),
            ],
            "linear_move": [
                ("X (mm):", "x", 0.0, "float", (-500, 500)),
                ("Y (mm):", "y", 0.0, "float", (-500, 500)),
                ("Z (mm):", "z", 200.0, "float", (0, 500)),
                ("Speed:", "speed", DEFAULT_SPEED, "int", (100, 5000)),
            ],
            "rotate": [
                ("Rx (deg):", "rx", 0.0, "float", (-180, 180)),
                ("Ry (deg):", "ry", 0.0, "float", (-180, 180)),
                ("Rz (deg):", "rz", 0.0, "float", (-180, 180)),
                ("Speed:", "speed", DEFAULT_SPEED, "int", (100, 5000)),
            ],
            "arc_move": [
                ("End X (mm):", "x", 0.0, "float", (-500, 500)),
                ("End Y (mm):", "y", 0.0, "float", (-500, 500)),
                ("End Z (mm):", "z", 200.0, "float", (0, 500)),
                ("Via X (mm):", "via_x", 50.0, "float", (-500, 500)),
                ("Via Y (mm):", "via_y", 50.0, "float", (-500, 500)),
                ("Via Z (mm):", "via_z", 200.0, "float", (0, 500)),
            ],
            "home": [
                (
                    "Joint:",
                    "joint",
                    "all",
                    "choice",
                    ["all", "0", "1", "2", "3", "4", "5"],
                ),
            ],
            "center": [
                (
                    "Joint:",
                    "joint",
                    "all",
                    "choice",
                    ["all", "0", "1", "2", "3", "4", "5"],
                ),
            ],
            "set_speed": [
                ("Speed:", "speed", DEFAULT_SPEED, "int", (100, 5000)),
            ],
            "set_accel": [
                ("Acceleration:", "accel", DEFAULT_ACC, "int", (1, 100)),
            ],
            "wait_time": [
                ("Seconds:", "seconds", 1.0, "float", (0.01, 60)),
            ],
            "wait_input": [
                ("Input #:", "input", 1, "int", (1, 8)),
                ("State:", "state", 1, "choice", [("High", 1), ("Low", 0)]),
                ("Timeout (s):", "timeout", 30.0, "float", (0.1, 300)),
            ],
            "torque_on": [
                ("Joint:", "joint", 0, "int", (0, 5)),
            ],
            "torque_off": [
                ("Joint:", "joint", 0, "int", (0, 5)),
            ],
            "gripper": [
                (
                    "Action:",
                    "close",
                    True,
                    "choice",
                    [("Close", True), ("Open", False)],
                ),
                ("Force (%):", "force", 50, "int", (0, 100)),
                ("Position:", "position", 2048, "int", (MIN_POSITION, MAX_POSITION)),
            ],
            "message": [
                ("Message:", "text", "Hello!", "text", None),
                (
                    "Type:",
                    "msg_type",
                    "info",
                    "choice",
                    [("Info", "info"), ("Warning", "warning"), ("Error", "error")],
                ),
            ],
            "loop_start": [
                ("Count:", "count", 3, "int", (1, 1000)),
                ("Name:", "name", "loop_1", "text", None),
            ],
            "loop_end": [],
            "if": [
                (
                    "Condition:",
                    "condition",
                    "true",
                    "choice",
                    [
                        ("Always True", "true"),
                        ("Input 1 High", "input_1_high"),
                        ("Input 1 Low", "input_1_low"),
                        ("Connected", "connected"),
                        ("Not Connected", "not_connected"),
                    ],
                ),
            ],
            "else": [],
            "endif": [],
            "goto": [
                ("Label:", "label", "LBL_1", "text", None),
            ],
            "label": [
                ("Name:", "name", "LBL_1", "text", None),
            ],
            "subroutine": [
                ("Name:", "name", "SUB_1", "text", None),
            ],
            "return": [],
        }

        fields = field_configs.get(self.block_type, [])

        if not fields:
            ctk.CTkLabel(
                self.params_frame,
                text="No parameters required.",
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=FANUC_TEXT2,
            ).pack(pady=20)
            return

        for i, (label, key, default, field_type, range_or_choices) in enumerate(fields):
            row = ctk.CTkFrame(self.params_frame, fg_color=FANUC_BG, corner_radius=0)
            row.pack(fill="x", pady=6)

            ctk.CTkLabel(
                row,
                text=label,
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=FANUC_TEXT2,
                width=110,
                anchor="w",
            ).pack(side="left")

            if field_type == "choice":
                var = tk.StringVar(value=str(default))
                self.input_vars[key] = var

                if isinstance(range_or_choices[0], tuple):
                    choices = [c[0] for c in range_or_choices]
                    var.set(
                        next(
                            (c[0] for c in range_or_choices if c[1] == default),
                            range_or_choices[0][0],
                        )
                    )
                else:
                    choices = range_or_choices

                ctk.CTkComboBox(
                    row,
                    variable=var,
                    values=choices,
                    width=200,
                    state="readonly",
                    fg_color=FANUC_PANEL,
                    text_color=FANUC_TEXT,
                    button_color=_DROP_COLOR,
                    button_hover_color="#5bb8a4",
                    border_color="#d0ccc8",
                ).pack(side="left", padx=5)
            elif field_type == "text":
                var = tk.StringVar(value=str(default))
                self.input_vars[key] = var
                ctk.CTkEntry(
                    row,
                    textvariable=var,
                    font=ctk.CTkFont("Segoe UI", 10),
                    width=200,
                    fg_color=FANUC_PANEL,
                    text_color=FANUC_TEXT,
                    border_color="#d0ccc8",
                ).pack(side="left", padx=5)
            else:
                var = (
                    tk.DoubleVar(value=float(default))
                    if field_type == "float"
                    else tk.IntVar(value=int(default))
                )
                self.input_vars[key] = var
                min_val, max_val = range_or_choices or (0, 100)
                ttk.Spinbox(row, from_=min_val, to=max_val, textvariable=var, width=22).pack(
                    side="left", padx=5
                )

    def _load_params(self):
        """Загрузка текущих параметров."""
        for key, value in self.params.items():
            if key in self.input_vars:
                if isinstance(self.input_vars[key], tk.BooleanVar):
                    self.input_vars[key].set(bool(value))
                else:
                    self.input_vars[key].set(value)

    def _on_ok(self):
        """Обработка нажатия OK."""
        try:
            result = {"type": self.block_type}

            for key, var in self.input_vars.items():
                value = var.get()
                if self.block_type == "wait_input" and key == "state":
                    value = int(value)
                elif self.block_type == "gripper" and key == "close":
                    value = value == "True" or value is True
                result[key] = value

            self.callback(result)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input: {e}")


class BlockPalette(ctk.CTkFrame):
    """Палитра блоков программирования — CTkScrollableFrame edition."""

    _CATEGORIES = [
        (
            "Motion",
            "motion",
            [
                (
                    "Move Joint",
                    "move_joint",
                    {"type": "move_joint", "joint": 0, "position": 2048, "speed": DEFAULT_SPEED},
                ),
                (
                    "Move XYZ",
                    "move_xyz",
                    {"type": "move_xyz", "x": 0, "y": 0, "z": 200, "speed": DEFAULT_SPEED},
                ),
                (
                    "Linear Move",
                    "linear_move",
                    {"type": "linear_move", "x": 0, "y": 0, "z": 200, "speed": DEFAULT_SPEED},
                ),
                (
                    "Rotate",
                    "rotate",
                    {"type": "rotate", "rx": 0, "ry": 0, "rz": 0, "speed": DEFAULT_SPEED},
                ),
                (
                    "Arc Move",
                    "arc_move",
                    {
                        "type": "arc_move",
                        "x": 0,
                        "y": 0,
                        "z": 200,
                        "via_x": 50,
                        "via_y": 50,
                        "via_z": 200,
                    },
                ),
                ("Home", "home", {"type": "home", "joint": "all"}),
                ("Center", "center", {"type": "center", "joint": "all"}),
            ],
        ),
        (
            "Settings",
            "control",
            [
                ("Set Speed", "set_speed", {"type": "set_speed", "speed": DEFAULT_SPEED}),
                ("Set Accel", "set_accel", {"type": "set_accel", "accel": DEFAULT_ACC}),
                ("Torque On", "torque_on", {"type": "torque_on", "joint": 0}),
                ("Torque Off", "torque_off", {"type": "torque_off", "joint": 0}),
                (
                    "Gripper",
                    "gripper",
                    {"type": "gripper", "close": True, "force": 50, "position": 2048},
                ),
            ],
        ),
        (
            "Timing",
            "wait",
            [
                ("Delay", "wait_time", {"type": "wait_time", "seconds": 1.0}),
                (
                    "Wait Input",
                    "wait_input",
                    {"type": "wait_input", "input": 1, "state": 1, "timeout": 30},
                ),
            ],
        ),
        (
            "Logic",
            "logic",
            [
                ("Loop Start", "loop_start", {"type": "loop_start", "count": 3, "name": "loop_1"}),
                ("Loop End", "loop_end", {"type": "loop_end"}),
                ("If", "if", {"type": "if", "condition": "true"}),
                ("Else", "else", {"type": "else"}),
                ("End If", "endif", {"type": "endif"}),
            ],
        ),
        (
            "Flow",
            "io",
            [
                ("Label", "label", {"type": "label", "name": "LBL_1"}),
                ("GoTo", "goto", {"type": "goto", "label": "LBL_1"}),
                ("Subroutine", "subroutine", {"type": "subroutine", "name": "SUB_1"}),
                ("Return", "return", {"type": "return"}),
                ("Message", "message", {"type": "message", "text": "Hello!", "msg_type": "info"}),
            ],
        ),
    ]

    def __init__(self, parent: tk.Misc, canvas: "ProgramCanvas"):
        super().__init__(parent, fg_color=FANUC_BG, corner_radius=0)
        self.canvas = canvas
        self._create_ui()

    def _create_ui(self) -> None:
        # ── Header ──────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=FANUC_PANEL, corner_radius=0, height=46)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="BLOCK PALETTE",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=FANUC_TEXT,
        ).pack(expand=True)

        ctk.CTkFrame(self, fg_color="#e8e4e0", height=1, corner_radius=0).pack(fill="x")

        # ── Scrollable content area (replaces manual Canvas + Scrollbar) ────
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=FANUC_BG,
            corner_radius=0,
            scrollbar_button_color=_DROP_COLOR,
            scrollbar_button_hover_color="#5bb8a4",
        )
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        for cat_name, cat_type, blocks in self._CATEGORIES:
            accent = _CAT_ACCENTS.get(cat_type, FANUC_PANEL)
            block_bg = BLOCK_COLORS.get(cat_type, FANUC_PANEL)

            # Category strip
            strip = ctk.CTkFrame(scroll, fg_color=accent, corner_radius=4, height=26)
            strip.pack(fill="x", pady=(8, 0))
            strip.pack_propagate(False)

            ctk.CTkLabel(
                strip,
                text=cat_name.upper(),
                font=ctk.CTkFont("Segoe UI", 8, "bold"),
                text_color=FANUC_TEXT,
                anchor="w",
            ).pack(side="left", padx=8, fill="y")

            # Block buttons
            for block_name, block_type, params in blocks:
                btn = tk.Button(
                    scroll,
                    text=f"  {block_name} + {block_type}",
                    bg=BLOCK_COLORS.get(block_type, FANUC_PANEL),
                    fg=FANUC_TEXT,
                    font=("SF Pro", 9),
                    relief="flat",
                )
                ctk.CTkButton(
                    scroll,
                    text=f"+ {block_name}",
                    font=ctk.CTkFont("Segoe UI", 9),
                    fg_color=block_bg,
                    text_color=FANUC_TEXT,
                    hover_color=accent,
                    anchor="w",
                    height=30,
                    corner_radius=4,
                    command=lambda p=params, t=cat_type: self._add_block(p, t),
                ).pack(fill="x", padx=2, pady=1)

    def _add_block(self, params: dict, block_type: str) -> None:
        """Open config dialog then push block to canvas."""

        def on_configured(configured_params):
            self.canvas.add_block_from_palette(configured_params, block_type)

        BlockConfigDialog(self, params.get("type"), params, on_configured)


class ProgramCanvas(tk.Canvas):
    """Расширенный холст программы с редактированием и перетаскиванием блоков."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent, bg=FANUC_BG, highlightthickness=0, relief="flat")
        self.blocks: list[ProgramBlock] = []
        self.block_widgets: dict[int, tk.Frame] = {}
        self.y_offset = 10
        self.block_id_counter = 0
        self.selected_block_id: int | None = None

        # Drag state
        self._drag_block_id: int | None = None
        self._drag_start_y_root: int = 0
        self._drop_line_id: int | None = None
        self._drop_target_idx: int = 0

        self.bind("<Configure>", self._on_resize)
        self.bind("<Button-1>", self._on_canvas_click)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_block_from_palette(self, params: dict, block_type: str):
        """Добавление блока из палитры."""
        self.block_id_counter += 1
        block = ProgramBlock(
            id=self.block_id_counter,
            block_type=block_type,
            params=params,
            order=len(self.blocks),
        )
        self.add_block(block)

    def add_block(self, block: ProgramBlock) -> None:
        """Добавление блока на холст."""
        self.blocks.append(block)
        self._create_block_widget(block)
        self._update_blocks_display()

    def remove_block(self, block_id: int) -> None:
        """Удаление блока с холста."""
        self.blocks = [b for b in self.blocks if b.id != block_id]
        if block_id in self.block_widgets:
            self.block_widgets[block_id].destroy()
            del self.block_widgets[block_id]
        self._update_blocks_display()

    def edit_block(self, block_id: int):
        """Редактирование блока."""
        block = next((b for b in self.blocks if b.id == block_id), None)
        if block:

            def on_configured(params):
                block.params = params
                block.description = block._generate_description()
                self._recreate_block_widget(block)
                self._update_blocks_display()

            BlockConfigDialog(self, block.params.get("type"), block.params, on_configured)

    def clear_all(self) -> None:
        """Очистка всех блоков."""
        for widget in self.block_widgets.values():
            widget.destroy()
        self.block_widgets.clear()
        self.blocks.clear()
        self.y_offset = 10
        self.block_id_counter = 0

    def get_program(self) -> list[dict]:
        """Получение программы для выполнения."""
        return [b.__dict__ for b in self.blocks]

    def move_block_up(self, block_id: int):
        """Перемещение блока вверх."""
        idx = next((i for i, b in enumerate(self.blocks) if b.id == block_id), -1)
        if idx > 0:
            self.blocks[idx], self.blocks[idx - 1] = self.blocks[idx - 1], self.blocks[idx]
            self._update_blocks_display()

    def move_block_down(self, block_id: int):
        """Перемещение блока вниз."""
        idx = next((i for i, b in enumerate(self.blocks) if b.id == block_id), -1)
        if 0 <= idx < len(self.blocks) - 1:
            self.blocks[idx], self.blocks[idx + 1] = self.blocks[idx + 1], self.blocks[idx]
            self._update_blocks_display()

    # ── Drag-and-drop ─────────────────────────────────────────────────────────

    def _start_drag(self, event: tk.Event, block_id: int) -> None:
        """Начало перетаскивания блока."""
        self._drag_block_id = block_id
        self._drag_start_y_root = event.y_root
        self._select_block(block_id)
        # Visually mark the dragged block
        widget = self.block_widgets.get(block_id)
        if widget:
            widget.configure(highlightbackground=_DROP_COLOR, highlightthickness=2)

    def _on_drag(self, event: tk.Event) -> None:
        """Обновление индикатора перетаскивания."""
        if self._drag_block_id is None:
            return
        canvas_y = self._root_y_to_canvas_y(event.y_root)
        idx = self._get_drop_index(canvas_y)
        self._drop_target_idx = idx
        self._draw_drop_indicator(idx)

    def _end_drag(self, event: tk.Event) -> None:
        """Завершение перетаскивания — перестановка блока."""
        if self._drag_block_id is None:
            return
        canvas_y = self._root_y_to_canvas_y(event.y_root)
        new_idx = self._get_drop_index(canvas_y)
        self._reorder_block(self._drag_block_id, new_idx)
        self._drag_block_id = None
        if self._drop_line_id is not None:
            self.delete(self._drop_line_id)
            self._drop_line_id = None
        self._update_blocks_display()

    def _root_y_to_canvas_y(self, y_root: int) -> float:
        """Перевод экранных координат в координаты холста (с учётом прокрутки)."""
        window_y = y_root - self.winfo_rooty()
        return self.canvasy(window_y)

    def _get_drop_index(self, canvas_y: float) -> int:
        """Определение индекса вставки по y-координате холста."""
        cumulative = 10
        for i, block in enumerate(self.blocks):
            widget = self.block_widgets.get(block.id)
            if widget is None:
                continue
            h = widget.winfo_reqheight()
            if canvas_y < cumulative + h / 2:
                return i
            cumulative += h + 8
        return len(self.blocks)

    def _draw_drop_indicator(self, idx: int) -> None:
        """Рисование горизонтальной линии — индикатора места вставки."""
        if self._drop_line_id is not None:
            self.delete(self._drop_line_id)

        y = 10
        for i, block in enumerate(self.blocks):
            if i == idx:
                break
            widget = self.block_widgets.get(block.id)
            if widget:
                y += widget.winfo_reqheight() + 8

        w = max(self.winfo_width() - 20, 100)
        self._drop_line_id = self.create_line(
            10, y - 3, w, y - 3, fill=_DROP_COLOR, width=3, dash=(6, 3)
        )

    def _reorder_block(self, block_id: int, new_idx: int) -> None:
        """Перестановка блока на новую позицию."""
        old_idx = next((i for i, b in enumerate(self.blocks) if b.id == block_id), -1)
        if old_idx == -1:
            return
        block = self.blocks.pop(old_idx)
        # Adjust index after removal
        if new_idx > old_idx:
            new_idx -= 1
        new_idx = max(0, min(new_idx, len(self.blocks)))
        self.blocks.insert(new_idx, block)

    # ── Widget creation ───────────────────────────────────────────────────────

    def _create_block_widget(self, block: ProgramBlock) -> None:
        """Создание виджета блока."""
        color = BLOCK_COLORS.get(block.block_type, FANUC_PANEL)

        frame = tk.Frame(
            self,
            bg=color,
            relief="flat",
            bd=0,
            highlightbackground=FANUC_GRAY,
            highlightthickness=1,
        )
        frame.bind("<Button-1>", lambda e, bid=block.id: self._select_block(bid))

        # ── Title row ──────────────────────────────────────────────────────
        title_frame = tk.Frame(frame, bg=color)
        title_frame.pack(fill="x", padx=4, pady=(4, 2))

        # Drag handle — bindings go here so edit/delete buttons still work
        drag_handle = tk.Label(
            title_frame,
            text=":",  # Simpler drag indicator (no emoji dependency)
            bg=color,
            fg=FANUC_GRAY,
            font=("Segoe UI", 14, "bold"),
            cursor="fleur",
            padx=2,
        )
        drag_handle.pack(side="left")
        drag_handle.bind("<ButtonPress-1>", lambda e, bid=block.id: self._start_drag(e, bid))
        drag_handle.bind("<B1-Motion>", self._on_drag)
        drag_handle.bind("<ButtonRelease-1>", self._end_drag)
        # Clicking handle also selects the block
        drag_handle.bind("<Button-1>", lambda e, bid=block.id: self._select_block(bid))

        type_labels = {
            "move_joint": "Move Joint",
            "move_xyz": "Move XYZ",
            "linear_move": "Linear Move",
            "rotate": "Rotate",
            "arc_move": "Arc Move",
            "home": "Home",
            "center": "Center",
            "set_speed": "Set Speed",
            "set_accel": "Set Accel",
            "wait_time": "Delay",
            "wait_input": "Wait Input",
            "torque_on": "Torque ON",
            "torque_off": "Torque OFF",
            "gripper": "Gripper",
            "message": "Message",
            "loop_start": "Loop Start",
            "loop_end": "Loop End",
            "if": "If",
            "else": "Else",
            "endif": "End If",
            "goto": "GoTo",
            "label": "Label",
            "subroutine": "Subroutine",
            "return": "Return",
        }

        block_type_key = block.params.get("type", "")
        label_text = type_labels.get(block_type_key, block_type_key.replace("_", " ").title())

        tk.Label(
            title_frame,
            text=label_text,
            bg=color,
            fg=FANUC_TEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(2, 0))

        # ── Control buttons (right side) ───────────────────────────────────
        btn_frame = tk.Frame(title_frame, bg=color)
        btn_frame.pack(side="right")

        _btn_cfg = dict(bg=color, relief="flat", bd=0, font=("Segoe UI", 9), cursor="hand2")

        tk.Button(
            btn_frame,
            text="^",
            fg=FANUC_TEXT2,
            **_btn_cfg,
            command=lambda bid=block.id: self.move_block_up(bid),
        ).pack(side="left", padx=1)

        tk.Button(
            btn_frame,
            text="v",
            fg=FANUC_TEXT2,
            **_btn_cfg,
            command=lambda bid=block.id: self.move_block_down(bid),
        ).pack(side="left", padx=1)

        tk.Button(
            btn_frame,
            text="Edit",
            fg=FANUC_TEXT,
            font=("Segoe UI", 8),
            bg=color,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda bid=block.id: self.edit_block(bid),
        ).pack(side="left", padx=2)

        tk.Button(
            btn_frame,
            text="X",
            fg=FANUC_RED,
            font=("Segoe UI", 9, "bold"),
            bg=color,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda bid=block.id: self.remove_block(bid),
        ).pack(side="left", padx=1)

        # ── Description row ────────────────────────────────────────────────
        desc = block.description
        if len(desc) > 40:
            desc = desc[:37] + "..."

        tk.Label(
            frame,
            text=f"  {desc}",
            bg=color,
            fg=FANUC_TEXT2,
            font=("Segoe UI", 8),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=4, pady=(0, 4))

        self.block_widgets[block.id] = frame

    def _recreate_block_widget(self, block: ProgramBlock):
        """Пересоздание виджета блока."""
        if block.id in self.block_widgets:
            self.block_widgets[block.id].destroy()
        self._create_block_widget(block)

    # ── Selection ─────────────────────────────────────────────────────────────

    def _select_block(self, block_id: int):
        """Выбор блока."""
        self.selected_block_id = block_id
        for bid, widget in self.block_widgets.items():
            if bid == block_id:
                widget.configure(highlightbackground=_SELECTED_BORDER, highlightthickness=2)
            else:
                widget.configure(highlightbackground=FANUC_GRAY, highlightthickness=1)

    def _on_canvas_click(self, event):
        """Клик по холсту — снять выделение."""
        self.selected_block_id = None
        for widget in self.block_widgets.values():
            widget.configure(highlightbackground=FANUC_GRAY, highlightthickness=1)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _update_blocks_display(self) -> None:
        """Обновление отображения блоков."""
        self.delete("all")
        self.y_offset = 10
        canvas_width = self.winfo_width()

        for block in self.blocks:
            widget = self.block_widgets.get(block.id)
            if widget is None:
                continue
            # Stretch block to canvas width with margin
            block_width = max(canvas_width - 20, 200)
            self.create_window(
                10,
                self.y_offset,
                window=widget,
                anchor="nw",
                width=block_width,
            )
            self.y_offset += widget.winfo_reqheight() + 8

        # Re-draw drop indicator if drag is in progress
        if self._drop_line_id is not None:
            self._draw_drop_indicator(self._drop_target_idx)

        self.configure(scrollregion=self.bbox("all") or (0, 0, 400, 400))

    def _on_resize(self, event: tk.Event) -> None:
        """Обработка изменения размера."""
        self._update_blocks_display()
