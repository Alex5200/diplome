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

from app.config.constants import (
    BLOCK_COLORS,
    DEFAULT_ACC,
    DEFAULT_SPEED,
    FANUC_BG,
    FANUC_GRAY,
    FANUC_GREEN,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    FANUC_TEXT2,
    MAX_POSITION,
    MIN_POSITION,
)


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
                f"Home {'All' if p.get('joint') == 'all' else f'J{int(p.get("joint", 0)) + 1}'}"
            ),
            "center": lambda p: (
                f"Center {'All' if p.get('joint') == 'all' else f'J{int(p.get("joint", 0)) + 1}'}"
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
            "message": lambda p: f"MSG: {p.get('text', '')[:20]}...",
            "loop_start": lambda p: f"Loop ×{p.get('count', 1)}",
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


class BlockConfigDialog(tk.Toplevel):
    """Диалог настройки параметров блока."""

    def __init__(
        self,
        parent: tk.Misc,
        block_type: str,
        params: dict,
        callback: Callable[[dict], None],
    ):
        super().__init__(parent)
        self.title(f"Configure {block_type.replace('_', ' ').title()}")
        self.geometry("400x500")
        self.resizable(False, False)

        self.block_type = block_type
        self.params = params.copy()
        self.callback = callback
        self.result = None

        self._create_widgets()
        self._load_params()

        self.transient(parent)
        self.grab_set()
        self.focus_set()

    def _create_widgets(self):
        """Создание виджетов диалога."""
        self.configure(bg=FANUC_BG)

        # Заголовок
        header = tk.Frame(self, bg=FANUC_PANEL, height=50)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)

        tk.Label(
            header,
            text=self.block_type.replace("_", " ").upper(),
            font=("SF Pro", 14, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
        ).pack(expand=True)

        # Фрейм с параметрами
        self.params_frame = tk.Frame(self, bg=FANUC_BG)
        self.params_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Создаем поля ввода в зависимости от типа блока
        self.input_vars = {}
        self._create_input_fields()

        # Кнопки
        btn_frame = tk.Frame(self, bg=FANUC_BG)
        btn_frame.pack(fill="x", padx=20, pady=15)

        tk.Button(
            btn_frame,
            text="Cancel",
            font=("SF Pro", 11),
            bg=FANUC_GRAY,
            fg=FANUC_TEXT,
            width=10,
            command=self.destroy,
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="OK",
            font=("SF Pro", 11, "bold"),
            bg=FANUC_GREEN,
            fg=FANUC_TEXT,
            width=10,
            command=self._on_ok,
        ).pack(side="right", padx=5)

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

        for i, (label, key, default, field_type, range_or_choices) in enumerate(fields):
            row = tk.Frame(self.params_frame, bg=FANUC_BG)
            row.pack(fill="x", pady=5)

            tk.Label(
                row,
                text=label,
                font=("SF Pro", 10),
                bg=FANUC_BG,
                fg=FANUC_TEXT2,
                width=12,
                anchor="w",
            ).pack(side="left")

            if field_type == "choice":
                var = tk.StringVar(value=str(default))
                self.input_vars[key] = var

                if isinstance(range_or_choices[0], tuple):
                    # (display, value) pairs
                    choices = [c[0] for c in range_or_choices]
                    var.set(
                        next(
                            (c[0] for c in range_or_choices if c[1] == default),
                            range_or_choices[0][0],
                        )
                    )
                else:
                    choices = range_or_choices

                combo = ttk.Combobox(
                    row, textvariable=var, values=choices, width=25, state="readonly"
                )
                combo.pack(side="left", padx=5)
            elif field_type == "text":
                var = tk.StringVar(value=str(default))
                self.input_vars[key] = var
                tk.Entry(row, textvariable=var, font=("SF Pro", 10), width=28).pack(
                    side="left", padx=5
                )
            else:  # int или float
                var = (
                    tk.DoubleVar(value=float(default))
                    if field_type == "float"
                    else tk.IntVar(value=int(default))
                )
                self.input_vars[key] = var

                min_val, max_val = range_or_choices or (0, 100)
                spin = ttk.Spinbox(row, from_=min_val, to=max_val, textvariable=var, width=25)
                spin.pack(side="left", padx=5)

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
                # Преобразование для choice
                if self.block_type == "wait_input" and key == "state":
                    value = int(value)
                elif self.block_type == "gripper" and key == "close":
                    value = value == "True" or value == True
                result[key] = value

            self.callback(result)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input: {e}")


class BlockPalette(ttk.Frame):
    """Расширенная палитра блоков для программирования."""

    def __init__(self, parent: tk.Misc, canvas: "ProgramCanvas"):
        super().__init__(parent, width=220, style="Dark.TFrame")
        self.canvas = canvas
        self.block_id_counter = 0

        self._create_categories()

    def _create_categories(self) -> None:
        """Создание категорий блоков."""
        # Заголовок
        header = tk.Frame(self, bg=FANUC_PANEL, height=40)
        header.pack(fill="x", pady=(0, 5))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="BLOCK PALETTE",
            font=("SF Pro", 11, "bold"),
            bg=FANUC_PANEL,
            fg=FANUC_TEXT,
        ).pack(expand=True)

        # Canvas для прокрутки
        scroll_canvas = tk.Canvas(self, bg=FANUC_BG, highlightthickness=0)
        scroll_canvas.pack(fill="both", expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(scroll_canvas, orient="vertical", command=scroll_canvas.yview)
        scrollbar.pack(side="right", fill="y")

        scroll_canvas.configure(yscrollcommand=scrollbar.set)

        content_frame = tk.Frame(scroll_canvas, bg=FANUC_BG)
        scroll_canvas.create_window((0, 0), window=content_frame, anchor="nw")

        # Категории блоков
        categories = [
            (
                "🏃 Motion",
                "motion",
                [
                    (
                        "Move Joint",
                        "move_joint",
                        {
                            "type": "move_joint",
                            "joint": 0,
                            "position": 2048,
                            "speed": DEFAULT_SPEED,
                        },
                    ),
                    (
                        "Move XYZ",
                        "move_xyz",
                        {
                            "type": "move_xyz",
                            "x": 0,
                            "y": 0,
                            "z": 200,
                            "speed": DEFAULT_SPEED,
                        },
                    ),
                    (
                        "Linear Move",
                        "linear_move",
                        {
                            "type": "linear_move",
                            "x": 0,
                            "y": 0,
                            "z": 200,
                            "speed": DEFAULT_SPEED,
                        },
                    ),
                    (
                        "Rotate",
                        "rotate",
                        {
                            "type": "rotate",
                            "rx": 0,
                            "ry": 0,
                            "rz": 0,
                            "speed": DEFAULT_SPEED,
                        },
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
                "⚙️ Settings",
                "control",
                [
                    (
                        "Set Speed",
                        "set_speed",
                        {"type": "set_speed", "speed": DEFAULT_SPEED},
                    ),
                    (
                        "Set Accel",
                        "set_accel",
                        {"type": "set_accel", "accel": DEFAULT_ACC},
                    ),
                    ("Torque On", "torque_on", {"type": "torque_on", "joint": 0}),
                    ("Torque Off", "torque_off", {"type": "torque_off", "joint": 0}),
                    (
                        "Gripper",
                        "gripper",
                        {
                            "type": "gripper",
                            "close": True,
                            "force": 50,
                            "position": 2048,
                        },
                    ),
                ],
            ),
            (
                "⏱️ Timing",
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
                "🔀 Logic",
                "logic",
                [
                    (
                        "Loop Start",
                        "loop_start",
                        {"type": "loop_start", "count": 3, "name": "loop_1"},
                    ),
                    ("Loop End", "loop_end", {"type": "loop_end"}),
                    ("If", "if", {"type": "if", "condition": "true"}),
                    ("Else", "else", {"type": "else"}),
                    ("End If", "endif", {"type": "endif"}),
                ],
            ),
            (
                "🏷️ Flow",
                "io",
                [
                    ("Label", "label", {"type": "label", "name": "LBL_1"}),
                    ("GoTo", "goto", {"type": "goto", "label": "LBL_1"}),
                    (
                        "Subroutine",
                        "subroutine",
                        {"type": "subroutine", "name": "SUB_1"},
                    ),
                    ("Return", "return", {"type": "return"}),
                    (
                        "Message",
                        "message",
                        {"type": "message", "text": "Hello!", "msg_type": "info"},
                    ),
                ],
            ),
        ]

        for category_name, category_type, blocks in categories:
            frame = tk.LabelFrame(
                content_frame,
                text=f"  {category_name}  ",
                font=("SF Pro", 9, "bold"),
                bg=FANUC_BG,
                fg=FANUC_TEXT2,
                relief="flat",
                bd=1,
                highlightbackground=FANUC_GRAY,
                highlightthickness=1,
            )
            frame.pack(fill="x", padx=5, pady=5)
            frame.configure(background=FANUC_BG)

            for block_name, block_type, params in blocks:
                btn = tk.Button(
                    frame,
                    text=f"  {block_name} + {block_type}",
                    bg=BLOCK_COLORS.get(category_type, FANUC_PANEL),
                    fg=FANUC_TEXT,
                    font=("SF Pro", 9),
                    relief="flat",
                    anchor="w",
                    padx=5,
                    pady=3,
                    command=lambda p=params, t=category_type: self._add_block(p, t),
                )
                btn.pack(fill="x", padx=3, pady=2)

        content_frame.update_idletasks()
        scroll_canvas.config(scrollregion=scroll_canvas.bbox("all"))

    def _add_block(self, params: dict, block_type: str):
        """Добавление блока с открытием диалога настройки."""

        def on_configured(configured_params):
            self.canvas.add_block_from_palette(configured_params, block_type)

        # Открываем диалог настройки
        BlockConfigDialog(self, params.get("type"), params, on_configured)


class ProgramCanvas(tk.Canvas):
    """Расширенный холст программы с редактированием блоков."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent, bg=FANUC_BG, highlightthickness=0, relief="flat")
        self.blocks: list[ProgramBlock] = []
        self.block_widgets: dict[int, tk.Frame] = {}
        self.y_offset = 10
        self.block_id_counter = 0
        self.selected_block_id: int | None = None

        self.bind("<Configure>", self._on_resize)
        self.bind("<Button-1>", self._on_canvas_click)

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

    def _create_block_widget(self, block: ProgramBlock) -> None:
        """Создание виджета блока."""
        color = BLOCK_COLORS.get(block.block_type, FANUC_PANEL)

        frame = tk.Frame(
            self,
            bg=color,
            relief="flat",
            bd=1,
            highlightbackground=FANUC_GRAY,
            highlightthickness=1,
        )
        frame.bind("<Button-1>", lambda e, bid=block.id: self._select_block(bid))

        # Верхняя панель с типом и кнопками
        title_frame = tk.Frame(frame, bg=color)
        title_frame.pack(fill="x", padx=4, pady=2)
        title_frame.bind("<Button-1>", lambda e, bid=block.id: self._select_block(bid))

        # Иконка типа
        type_icons = {
            "move_joint": "🔄",
            "move_xyz": "📍",
            "linear_move": "➡️",
            "rotate": "🔄",
            "arc_move": "🌈",
            "home": "🏠",
            "center": "⚫",
            "set_speed": "⚡",
            "set_accel": "🚀",
            "wait_time": "⏱️",
            "wait_input": "🔌",
            "torque_on": "💪",
            "torque_off": "🚫",
            "gripper": "✋",
            "message": "💬",
            "loop_start": "🔁",
            "loop_end": "⏹️",
            "if": "❓",
            "else": "↪️",
            "endif": "✓",
            "goto": "🏃",
            "label": "🏷️",
            "subroutine": "📞",
            "return": "↩️",
        }

        icon = type_icons.get(block.params.get("type"), "🔷")

        tk.Label(
            title_frame,
            text=f"{icon} {block.params.get('type', 'block').replace('_', ' ').title()}",
            bg=color,
            fg=FANUC_TEXT,
            font=("SF Pro", 9, "bold"),
        ).pack(side="left")

        # Кнопки управления
        btn_frame = tk.Frame(title_frame, bg=color)
        btn_frame.pack(side="right")

        tk.Button(
            btn_frame,
            text="✏️",
            bg=color,
            fg=FANUC_TEXT,
            bd=0,
            font=("SF Pro", 8),
            command=lambda bid=block.id: self.edit_block(bid),
        ).pack(side="left", padx=1)

        tk.Button(
            btn_frame,
            text="✕",
            bg=color,
            fg=FANUC_RED,
            bd=0,
            font=("SF Pro", 8),
            command=lambda bid=block.id: self.remove_block(bid),
        ).pack(side="left", padx=1)

        # Описание параметров
        desc = block.description
        if len(desc) > 35:
            desc = desc[:32] + "..."

        tk.Label(
            frame,
            text=f"  {desc}",
            bg=color,
            fg=FANUC_TEXT2,
            font=("SF Pro", 8),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=4, pady=(0, 3))

        self.block_widgets[block.id] = frame

    def _recreate_block_widget(self, block: ProgramBlock):
        """Пересоздание виджета блока."""
        if block.id in self.block_widgets:
            self.block_widgets[block.id].destroy()
        self._create_block_widget(block)

    def _select_block(self, block_id: int):
        """Выбор блока."""
        self.selected_block_id = block_id
        for bid, widget in self.block_widgets.items():
            color = BLOCK_COLORS.get(
                self.blocks[[b.id for b in self.blocks].index(bid)].block_type,
                FANUC_PANEL,
            )
            if bid == block_id:
                widget.configure(highlightbackground=FANUC_GREEN, highlightthickness=2)
            else:
                widget.configure(highlightbackground=FANUC_GRAY, highlightthickness=1)

    def _on_canvas_click(self, event):
        """Клик по холсту - снять выделение."""
        self.selected_block_id = None
        for widget in self.block_widgets.values():
            widget.configure(highlightbackground=FANUC_GRAY, highlightthickness=1)

    def _update_blocks_display(self) -> None:
        """Обновление отображения блоков."""
        self.delete("all")
        self.y_offset = 10

        for block in self.blocks:
            if block.id in self.block_widgets:
                self.create_window(
                    10, self.y_offset, window=self.block_widgets[block.id], anchor="nw"
                )
                self.y_offset += self.block_widgets[block.id].winfo_reqheight() + 8

        self.configure(scrollregion=self.bbox("all"))

    def _on_resize(self, event: tk.Event) -> None:
        """Обработка изменения размера."""
        self.configure(scrollregion=self.bbox("all"))

    def get_program(self) -> list[dict]:
        """Получение программы для выполнения."""
        return [b.__dict__ for b in self.blocks]

    def move_block_up(self, block_id: int):
        """Перемещение блока вверх."""
        idx = next((i for i, b in enumerate(self.blocks) if b.id == block_id), -1)
        if idx > 0:
            self.blocks[idx], self.blocks[idx - 1] = (
                self.blocks[idx - 1],
                self.blocks[idx],
            )
            self._update_blocks_display()

    def move_block_down(self, block_id: int):
        """Перемещение блока вниз."""
        idx = next((i for i, b in enumerate(self.blocks) if b.id == block_id), -1)
        if idx >= 0 and idx < len(self.blocks) - 1:
            self.blocks[idx], self.blocks[idx + 1] = (
                self.blocks[idx + 1],
                self.blocks[idx],
            )
            self._update_blocks_display()
