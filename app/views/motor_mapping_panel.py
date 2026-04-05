#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor Mapping Panel Module

Панель настройки соответствия моторов суставам робота.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, List, Optional

from app.controllers.motor_controller import MotorController
from app.config.constants import JOINT_NAMES, DEFAULT_MOTOR_MAPPING
from app.models.motor_data import MotorData


class MotorMappingPanel(ttk.Frame):
    """
    Панель настройки соответствия моторов суставам.

    Позволяет:
        - Назначать физические ID моторов логическим суставам
        - Задавать отображаемые имена суставов
        - Автоматически определять подключенные моторы
        - Проверять состояние каждого мотора

    Пример использования:
        panel = MotorMappingPanel(parent, controller, log_callback)
        panel.pack(fill='both', expand=True)
    """

    def __init__(
        self,
        parent: tk.Misc,
        controller: MotorController,
        log_callback: Callable[[str, str], None]
    ):
        """
        Инициализация панели настройки моторов.

        Args:
            parent: Родительский виджет
            controller: Контроллер моторов
            log_callback: Функция для логирования событий
        """
        super().__init__(parent)
        self.controller = controller
        self.log = log_callback

        # Переменные для хранения настроек
        self.mapping_vars: Dict[int, tk.IntVar] = {}
        self.name_vars: Dict[int, tk.StringVar] = {}
        self.mapping_widgets: Dict[int, Dict[str, any]] = {}

        self._create_widgets()
        self._load_current_mapping()

    def _create_widgets(self) -> None:
        """Создание виджетов панели."""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # === Заголовок ===
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=10)

        ttk.Label(
            header_frame, text="⚙️ Настройка соответствия моторов",
            font=('Arial', 14, 'bold')
        ).pack(side='left')

        ttk.Button(
            header_frame, text="💾 Сохранить", command=self._save_mapping
        ).pack(side='right', padx=5)

        ttk.Button(
            header_frame, text="🔄 Сбросить", command=self._reset_mapping
        ).pack(side='right', padx=5)

        # === Информация ===
        info_frame = ttk.LabelFrame(main_frame, text="ℹ️ Информация")
        info_frame.pack(fill='x', pady=10)

        info_text = """
        Здесь вы можете указать, какой физический ID мотора соответствует каждому суставу робота.
        • Суставы: логические части робота (База, Плечо, Локоть, Кисть)
        • ID мотора: физический адрес мотора на шине (1-253)
        • Название: отображаемое имя сустава
        """
        ttk.Label(info_frame, text=info_text, justify='left').pack(padx=10, pady=10)

        # === Таблица соответствия ===
        mapping_frame = ttk.LabelFrame(main_frame, text="🔗 Соответствие суставов и моторов")
        mapping_frame.pack(fill='both', expand=True, pady=10)

        headers = ['Сустав', 'ID мотора', 'Название', 'Текущая позиция']
        for col, header in enumerate(headers):
            ttk.Label(
                mapping_frame, text=header, font=('Arial', 10, 'bold')
            ).grid(row=0, column=col, padx=10, pady=5, sticky='w')

        for joint_idx in range(6):
            self._create_mapping_row(mapping_frame, joint_idx)

        # === Кнопки действий ===
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill='x', pady=10)

        ttk.Button(
            action_frame, text="🔍 Автоопределение", command=self._auto_detect
        ).pack(side='left', padx=5)

        ttk.Button(
            action_frame, text="📊 Проверить все", command=self._check_all_motors
        ).pack(side='left', padx=5)

    def _create_mapping_row(self, parent: ttk.Widget, joint_idx: int) -> None:
        """
        Создание строки таблицы соответствия.

        Args:
            parent: Родительский виджет
            joint_idx: Индекс сустава (0-5)
        """
        row = joint_idx + 1

        joint_name = JOINT_NAMES[joint_idx] if joint_idx < len(JOINT_NAMES) else f'Сустав {joint_idx}'
        ttk.Label(parent, text=joint_name, font=('Arial', 10)).grid(
            row=row, column=0, padx=10, pady=5, sticky='w'
        )

        # Переменная для ID мотора
        motor_id_var = tk.IntVar(value=joint_idx + 1)
        self.mapping_vars[joint_idx] = motor_id_var

        # Выпадающий список ID мотора
        motor_combo = ttk.Combobox(
            parent, textvariable=motor_id_var, width=10, state='readonly'
        )
        motor_combo['values'] = list(range(1, 254))
        motor_combo.grid(row=row, column=1, padx=10, pady=5)

        # Переменная для имени
        name_var = tk.StringVar(value=joint_name)
        self.name_vars[joint_idx] = name_var

        # Поле ввода имени
        name_entry = ttk.Entry(parent, textvariable=name_var, width=20)
        name_entry.grid(row=row, column=2, padx=10, pady=5)

        # Метка позиции
        pos_label = ttk.Label(parent, text="--", font=('Consolas', 10))
        pos_label.grid(row=row, column=3, padx=10, pady=5)

        self.mapping_widgets[joint_idx] = {
            'combo': motor_combo,
            'name': name_entry,
            'pos': pos_label
        }

    def _load_current_mapping(self) -> None:
        """Загрузка текущей конфигурации соответствия."""
        mapping = self.controller.get_motor_mapping()

        for joint_idx in range(6):
            key = f'joint_{joint_idx}'
            if key in mapping:
                motor_id = mapping[key].get('motor_id', joint_idx + 1)
                name = mapping[key].get(
                    'name',
                    JOINT_NAMES[joint_idx] if joint_idx < len(JOINT_NAMES) else f'Сустав {joint_idx}'
                )

                if joint_idx in self.mapping_vars:
                    self.mapping_vars[joint_idx].set(motor_id)
                if joint_idx in self.name_vars:
                    self.name_vars[joint_idx].set(name)

    def _save_mapping(self) -> None:
        """Сохранение настроек соответствия."""
        for joint_idx in range(6):
            if joint_idx in self.mapping_vars:
                motor_id = self.mapping_vars[joint_idx].get()
                name = self.name_vars[joint_idx].get()
                self.controller.update_motor_mapping(joint_idx, motor_id, name)

        self.controller.save_config()
        self.log("💾 Соответствие моторов сохранено", 'success')
        messagebox.showinfo("Успех", "Соответствие моторов сохранено!")

    def _reset_mapping(self) -> None:
        """Сброс настроек к значениям по умолчанию."""
        if messagebox.askyesno("Подтверждение", "Сбросить все настройки к умолчанию?"):
            self.controller.motor_mapping = DEFAULT_MOTOR_MAPPING.copy()
            self._load_current_mapping()
            self.log("🔄 Настройки сброшены", 'info')

    def _auto_detect(self) -> None:
        """Автоматическое определение подключенных моторов."""
        if not self.controller.connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь к роботу!")
            return

        self.log("🔍 Автоопределение моторов...", 'info')
        found_servos = self.controller.scan_servos()

        if found_servos:
            self.log(f"✅ Найдено моторов: {found_servos}", 'success')
            for joint_idx in range(min(6, len(found_servos))):
                if joint_idx in self.mapping_vars:
                    self.mapping_vars[joint_idx].set(found_servos[joint_idx])
            self.log("🔗 Моторы назначены автоматически", 'info')
        else:
            self.log("⚠️ Моторы не найдены", 'warning')
            messagebox.showinfo("Информация", "Моторы не найдены.\nПроверьте подключение.")

    def _check_all_motors(self) -> None:
        """Проверка состояния всех моторов."""
        if not self.controller.connected:
            messagebox.showwarning("Предупреждение", "Сначала подключитесь!")
            return

        self.log("📊 Проверка всех моторов...", 'info')

        for joint_idx in range(6):
            if joint_idx in self.mapping_vars:
                motor_id = self.mapping_vars[joint_idx].get()
                data = self.controller.read_motor_data(motor_id)

                if data.get('position') is not None:
                    pos_text = str(data['position'])
                    color = 'green'
                else:
                    pos_text = "Нет ответа"
                    color = 'red'

                if joint_idx in self.mapping_widgets:
                    self.mapping_widgets[joint_idx]['pos'].config(
                        text=pos_text, foreground=color
                    )

        self.log("✅ Проверка завершена", 'success')

    def update_positions(self, motor_data_dict: Dict[int, MotorData]) -> None:
        """
        Обновление отображения позиций моторов.

        Args:
            motor_data_dict: Словарь данных моторов {motor_id: MotorData}
        """
        for joint_idx in range(6):
            if joint_idx in self.mapping_vars:
                motor_id = self.mapping_vars[joint_idx].get()
                if motor_id in motor_data_dict:
                    data = motor_data_dict[motor_id]
                    if data.position is not None:
                        if joint_idx in self.mapping_widgets:
                            self.mapping_widgets[joint_idx]['pos'].config(
                                text=str(data.position), foreground='green'
                            )
