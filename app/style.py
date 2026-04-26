#!/usr/bin/env python3
"""
Style configuration — CTk + TTK hybrid theme.

CTk handles: CTkFrame, CTkButton, CTkLabel, CTkEntry, CTkSlider,
             CTkComboBox, CTkTextbox, CTkTabview, CTkScrollableFrame.

TTK handles: Treeview, Spinbox, PanedWindow, Scrollbar (for legacy code).
"""

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from app.config.constants import (
    FANUC_BG,
    FANUC_BLUE,
    FANUC_GRAY,
    FANUC_ORANGE,
    FANUC_PANEL,
    FANUC_RED,
    FANUC_TEXT,
    FANUC_TEXT2,
)

# ── Accent colours reused across the app ────────────────────────────────────
ACCENT       = "#7dd3c0"   # teal  — primary accent
ACCENT_HOVER = "#5bb8a4"   # darker teal for hover
LIGHT_BORDER = "#e8e4e0"


def setup_ctk():
    """Call ONCE before any CTk widget is created."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")


def config_styles(root: tk.Misc) -> None:
    """Configure ttk styles for widgets that CTk does not replace
    (Treeview, Spinbox, PanedWindow, legacy Scrollbar, etc.)."""

    style = ttk.Style(root)
    style.theme_use("clam")

    # ── Global ───────────────────────────────────────────────────────────────
    style.configure(
        ".",
        background=FANUC_BG,
        foreground=FANUC_TEXT,
        fieldbackground=FANUC_PANEL,
        bordercolor=LIGHT_BORDER,
        troughcolor="#e8e4e0",
        selectbackground=ACCENT,
        selectforeground=FANUC_TEXT,
        font=("Segoe UI", 10),
        relief="flat",
    )

    # ── Treeview ─────────────────────────────────────────────────────────────
    style.configure(
        "Treeview",
        background=FANUC_PANEL,
        foreground=FANUC_TEXT,
        rowheight=26,
        fieldbackground=FANUC_PANEL,
        borderwidth=0,
        font=("Segoe UI", 9),
    )
    style.configure(
        "Treeview.Heading",
        background=FANUC_BG,
        foreground=FANUC_TEXT,
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        borderwidth=0,
        padding=(6, 4),
    )
    style.map(
        "Treeview",
        background=[("selected", ACCENT)],
        foreground=[("selected", FANUC_TEXT)],
    )
    style.map("Treeview.Heading", background=[("active", "#e0e0e0")])

    # ── Spinbox ───────────────────────────────────────────────────────────────
    style.configure(
        "TSpinbox",
        fieldbackground=FANUC_PANEL,
        foreground=FANUC_TEXT,
        bordercolor=LIGHT_BORDER,
        arrowcolor=FANUC_TEXT2,
        insertcolor=FANUC_TEXT,
        padding=4,
    )
    style.map("TSpinbox", fieldbackground=[("readonly", FANUC_BG)])

    # ── Combobox ──────────────────────────────────────────────────────────────
    style.configure(
        "TCombobox",
        fieldbackground=FANUC_PANEL,
        background=FANUC_PANEL,
        foreground=FANUC_TEXT,
        arrowcolor=FANUC_TEXT2,
        selectbackground=ACCENT,
        selectforeground=FANUC_TEXT,
        bordercolor=LIGHT_BORDER,
        padding=4,
    )

    # ── Scrollbar ─────────────────────────────────────────────────────────────
    style.configure(
        "TScrollbar",
        background="#e8e4e0",
        troughcolor=FANUC_BG,
        arrowcolor=FANUC_TEXT2,
        bordercolor=LIGHT_BORDER,
        relief="flat",
        width=10,
    )
    style.map("TScrollbar", background=[("active", ACCENT)])

    # ── Progressbar ───────────────────────────────────────────────────────────
    style.configure(
        "TProgressbar",
        troughcolor="#e8e4e0",
        background=ACCENT,
        borderwidth=0,
    )

    # ── Frame / LabelFrame ────────────────────────────────────────────────────
    style.configure("TFrame", background=FANUC_BG, relief="flat", borderwidth=0)
    style.configure(
        "TLabelframe",
        background=FANUC_BG,
        foreground=FANUC_TEXT2,
        bordercolor=LIGHT_BORDER,
        relief="groove",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=FANUC_BG,
        foreground=ACCENT,
        font=("Segoe UI", 9, "bold"),
    )

    # ── PanedWindow ───────────────────────────────────────────────────────────
    style.configure("TPanedwindow", background=FANUC_BG)
    style.configure("Sash", sashrelief="flat", sashpad=4, sashthickness=6)

    # ── Notebook (for fallback, CTkTabview is preferred) ─────────────────────
    style.configure(
        "TNotebook",
        background=FANUC_BG,
        bordercolor=LIGHT_BORDER,
        tabmargins=[2, 5, 2, 0],
    )
    style.configure(
        "TNotebook.Tab",
        background="#e8e4e0",
        foreground=FANUC_TEXT2,
        padding=[12, 5],
        font=("Segoe UI", 9),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", FANUC_PANEL)],
        foreground=[("selected", ACCENT)],
        expand=[("selected", [1, 1, 1, 0])],
    )
