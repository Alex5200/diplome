#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Block Programming Module

Панель блочного программирования движений робота.
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Optional
from dataclasses import dataclass

from app.config.constants import BLOCK_COLORS


@dataclass
class ProgramBlock:
    """Блок программы."""
    id: int
    block_type: str
    params: dict
    order: int


class BlockPalette(ttk.Frame):
    """
    Палитра блоков для программирования.

    Содержит категории блоков:
        - Движение (motion): move_to, home
        - Ожидание (wait): wait_time
        - Управление (control): torque_on, torque_off

    Пример использования:
        palette = BlockPalette(parent, program_canvas)
        palette.pack(side='left', fill='y')
    """

    def __init__(self, parent: tk.Misc, canvas: 'ProgramCanvas'):
        """
        Инициализация палитры блоков.

        Args:
            parent: Родительский виджет
            canvas: Холст программы для добавления блоков
        """
        super().__init__(parent, width=200)
        self.canvas = canvas
        self.block_id_counter = 0

        self._create_categories()

    def _create_categories(self) -> None:
        """Создание категорий блоков."""
        ttk.Label(
            self, text="📦 Блоки", font=('Arial', 11, 'bold')
        ).pack(pady=5)

        categories = [
            ("🔄 Движение", 'motion', [
                ("Движение", {'type': 'move_to', 'joint': 0, 'position': 2048}),
                ("Home", {'type': 'home', 'joint': 'all'}),
            ]),
            ("⏱ Ожидание", 'wait', [
                ("Ждать", {'type': 'wait_time', 'seconds': 1.0}),
            ]),
            ("💪 Момент", 'control', [
                ("ВКЛ", {'type': 'torque_on', 'joint': 0}),
                ("ВЫКЛ", {'type': 'torque_off', 'joint': 0}),
            ]),
        ]

        for category_name, category_type, blocks in categories:
            frame = ttk.LabelFrame(self, text=category_name)
            frame.pack(fill='x', padx=5, pady=5)

            for block_name, params in blocks:
                btn = tk.Button(
                    frame,
                    text=block_name,
                    bg=BLOCK_COLORS.get(category_type, '#999999'),
                    fg='white',
                    font=('Arial', 9),
                    command=lambda p=params, t=category_type: self._add_block(p, t)
                )
                btn.pack(fill='x', padx=3, pady=2)

    def _add_block(self, params: dict, block_type: str) -> None:
        """
        Добавление блока на холст программы.

        Args:
            params: Параметры блока
            block_type: Тип блока (motion, wait, control)
        """
        self.block_id_counter += 1
        block = ProgramBlock(
            id=self.block_id_counter,
            block_type=block_type,
            params=params,
            order=self.canvas.get_block_count() if self.canvas else 0
        )
        if self.canvas:
            self.canvas.add_block(block)


class ProgramCanvas(tk.Canvas):
    """
    Холст программы для блочного программирования.

    Позволяет:
        - Добавлять блоки из палитры
        - Удалять блоки
        - Очищать всю программу
        - Получать программу для выполнения

    Пример использования:
        canvas = ProgramCanvas(parent)
        canvas.pack(fill='both', expand=True)
        canvas.add_block(block)
        program = canvas.get_program()
    """

    def __init__(self, parent: tk.Misc):
        """
        Инициализация холста программы.

        Args:
            parent: Родительский виджет
        """
        super().__init__(parent, bg='#f5f5f5', highlightthickness=0)
        self.blocks: List[ProgramBlock] = []
        self.block_widgets: Dict[int, tk.Frame] = {}
        self.y_offset = 10

        self.bind('<Configure>', self._on_resize)

    def get_block_count(self) -> int:
        """
        Получение количества блоков.

        Returns:
            Количество блоков на холсте
        """
        return len(self.blocks)

    def add_block(self, block: ProgramBlock) -> None:
        """
        Добавление блока на холст.

        Args:
            block: Блок программы для добавления
        """
        self.blocks.append(block)
        self._create_block_widget(block)
        self._update_blocks_display()

    def remove_block(self, block_id: int) -> None:
        """
        Удаление блока с холста.

        Args:
            block_id: ID блока для удаления
        """
        self.blocks = [b for b in self.blocks if b.id != block_id]
        if block_id in self.block_widgets:
            self.block_widgets[block_id].destroy()
            del self.block_widgets[block_id]
        self._update_blocks_display()

    def clear_all(self) -> None:
        """Очистка всех блоков с холста."""
        for widget in self.block_widgets.values():
            widget.destroy()
        self.block_widgets.clear()
        self.blocks.clear()
        self.y_offset = 10

    def _create_block_widget(self, block: ProgramBlock) -> None:
        """
        Создание виджета блока.

        Args:
            block: Блок программы для создания виджета
        """
        frame = tk.Frame(
            self, bg=BLOCK_COLORS.get(block.block_type, '#999999'),
            relief='raised', bd=2
        )

        title_frame = tk.Frame(frame, bg=BLOCK_COLORS.get(block.block_type, '#999999'))
        title_frame.pack(fill='x', padx=5, pady=3)

        # Названия блоков
        block_names = {
            'move_to': '🔄 Движение',
            'home': '🏠 Home',
            'wait_time': '⏱ Ждать',
            'torque_on': '💪 ВКЛ',
            'torque_off': '💪 ВЫКЛ',
        }

        tk.Label(
            title_frame,
            text=block_names.get(block.params.get('type', ''), 'Блок'),
            bg=BLOCK_COLORS.get(block.block_type, '#999999'),
            fg='white',
            font=('Arial', 10, 'bold')
        ).pack(side='left')

        tk.Button(
            title_frame, text='✕',
            bg=BLOCK_COLORS.get(block.block_type, '#999999'),
            fg='white', bd=0,
            command=lambda bid=block.id: self.remove_block(bid)
        ).pack(side='right')

        self.block_widgets[block.id] = frame

    def _update_blocks_display(self) -> None:
        """Обновление отображения всех блоков."""
        self.delete('all')
        self.y_offset = 10

        for block in self.blocks:
            if block.id in self.block_widgets:
                self.create_window(
                    10, self.y_offset,
                    window=self.block_widgets[block.id],
                    anchor='nw'
                )
                self.y_offset += self.block_widgets[block.id].winfo_reqheight() + 10

        self.configure(scrollregion=self.bbox('all'))

    def _on_resize(self, event: tk.Event) -> None:
        """
        Обработчик изменения размера холста.

        Args:
            event: Событие изменения размера
        """
        self.configure(scrollregion=self.bbox('all'))

    def get_program(self) -> List[dict]:
        """
        Получение программы для выполнения.

        Returns:
            Список словарей с параметрами блоков
        """
        return [b.__dict__ for b in self.blocks]
