import tkinter as tk
from tkinter import ttk

from config.constants import (
    LIGHT_ACCENT,
    LIGHT_BG,
    LIGHT_BLUE,
    LIGHT_BORDER,
    LIGHT_HOVER,
    LIGHT_PANEL,
    LIGHT_RED,
    LIGHT_SELECT,
    LIGHT_TEXT,
    LIGHT_TEXT2,
)


def config_styles(root: tk.Tk) -> tk.Tk:
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(
        ".",
        background=LIGHT_BG,
        foreground=LIGHT_TEXT,
        fieldbackground=LIGHT_PANEL,
        bordercolor=LIGHT_BORDER,
        troughcolor=LIGHT_HOVER,
        selectbackground=LIGHT_SELECT,
        selectforeground=LIGHT_TEXT,
        font=("Segoe UI", 10),
    )

    style.configure("TFrame", background=LIGHT_BG)
    style.configure("TLabel", background=LIGHT_BG, foreground=LIGHT_TEXT)
    style.configure(
        "TLabelframe",
        background=LIGHT_BG,
        foreground=LIGHT_TEXT2,
        bordercolor=LIGHT_BORDER,
        relief="groove",
    )
    style.configure(
        "TLabelframe.Label",
        background=LIGHT_BG,
        foreground=LIGHT_ACCENT,
        font=("Segoe UI", 9, "bold"),
    )

    style.configure(
        "TNotebook",
        background=LIGHT_BG,
        bordercolor=LIGHT_BORDER,
        tabmargins=[2, 5, 2, 0],
    )
    style.configure(
        "TNotebook.Tab",
        background=LIGHT_HOVER,
        foreground=LIGHT_TEXT2,
        padding=[12, 5],
        font=("Segoe UI", 9),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", LIGHT_PANEL)],
        foreground=[("selected", LIGHT_ACCENT)],
        expand=[("selected", [1, 1, 1, 0])],
    )

    style.configure(
        "TButton",
        background=LIGHT_PANEL,
        foreground=LIGHT_TEXT,
        bordercolor=LIGHT_BORDER,
        relief="flat",
        padding=[10, 5],
        font=("Segoe UI", 9),
    )
    style.map(
        "TButton",
        background=[("active", LIGHT_HOVER), ("pressed", LIGHT_SELECT)],
    )

    style.configure(
        "Accent.TButton",
        background=LIGHT_ACCENT,
        foreground="#ffffff",
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("active", LIGHT_BLUE)],
    )

    style.configure(
        "Danger.TButton",
        background=LIGHT_RED,
        foreground="#ffffff",
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#9a0007")],
    )

    style.configure(
        "TEntry",
        fieldbackground=LIGHT_PANEL,
        foreground=LIGHT_TEXT,
        bordercolor=LIGHT_BORDER,
        insertcolor=LIGHT_TEXT,
    )
    style.configure(
        "TSpinbox",
        fieldbackground=LIGHT_PANEL,
        foreground=LIGHT_TEXT,
        bordercolor=LIGHT_BORDER,
        arrowcolor=LIGHT_TEXT2,
    )
    style.configure(
        "TCombobox",
        fieldbackground=LIGHT_PANEL,
        foreground=LIGHT_TEXT,
        selectbackground=LIGHT_SELECT,
        arrowcolor=LIGHT_TEXT2,
    )
    style.configure(
        "TScrollbar",
        background=LIGHT_HOVER,
        troughcolor=LIGHT_BG,
        arrowcolor=LIGHT_TEXT2,
        bordercolor=LIGHT_BORDER,
    )
    style.configure(
        "TScale",
        background=LIGHT_BG,
        troughcolor=LIGHT_HOVER,
        sliderrelief="flat",
    )
    style.configure(
        "TCheckbutton",
        background=LIGHT_BG,
        foreground=LIGHT_TEXT,
        indicatorcolor=LIGHT_PANEL,
        indicatordiameter=14,
    )
    style.configure(
        "TRadiobutton",
        background=LIGHT_BG,
        foreground=LIGHT_TEXT,
    )
    style.configure("TSeparator", background=LIGHT_BORDER)
    style.configure(
        "TProgressbar",
        troughcolor=LIGHT_HOVER,
        background=LIGHT_ACCENT,
    )
    return root
