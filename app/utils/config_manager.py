#!/usr/bin/env python3

"""
Configuration Manager Module

Менеджер конфигурации приложения для загрузки и сохранения настроек.
Поддерживает валидацию, резервное копирование и историю изменений.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config.constants import (
    CONFIG_FILE,
    DEFAULT_MOTOR_CONFIG,
    DEFAULT_MOTOR_MAPPING,
    MAX_POSITION,
    MIN_POSITION,
    PROGRAM_FILE,
)


class ConfigValidationError(Exception):
    """Исключение валидации конфигурации."""

    pass


class ConfigManager:
    """
    Менеджер конфигурации приложения.

    Управляет загрузкой и сохранением:
        - Конфигурации моторов
        - Соответствия моторов суставам
        - Программ блочного программирования
        - Настроек приложения

    Возможности:
        - Валидация данных при загрузке/сохранении
        - Автоматическое резервное копирование
        - История изменений (до 5 версий)
        - Кэширование загруженных конфигураций

    Пример использования:
        config = ConfigManager()
        config.load_config('robot_config.json')
        config.save_config('robot_config.json', data)
    """

    def __init__(self, config_dir: str | None = None, max_history: int = 5):
        """
        Инициализация менеджера конфигурации.

        Args:
            config_dir: Директория для хранения конфигурации
            max_history: Максимальное количество версий истории
        """
        self.config_dir = Path(config_dir) if config_dir else Path.cwd()
        self._config_cache: dict[str, Any] = {}
        self._max_history = max_history
        self._config_history: dict[str, list[str]] = {}

        # Создание директории если не существует
        self.config_dir.mkdir(parents=True, exist_ok=True)

    # ==================== Валидация ====================

    def validate_motor_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Валидация конфигурации моторов.

        Args:
            config: Конфигурация для проверки

        Returns:
            (success, список ошибок)
        """
        errors = []

        # Проверка motor_config
        if "motor_config" in config:
            for motor_id, motor_cfg in config["motor_config"].items():
                if not isinstance(motor_id, str) or not motor_id.startswith("motor_"):
                    errors.append(f"Неверный ID мотора: {motor_id}")
                    continue

                min_pos = motor_cfg.get("min_pos", 0)
                max_pos = motor_cfg.get("max_pos", MAX_POSITION)

                if min_pos < MIN_POSITION:
                    errors.append(f"{motor_id}: min_pos ({min_pos}) < {MIN_POSITION}")
                if max_pos > MAX_POSITION:
                    errors.append(f"{motor_id}: max_pos ({max_pos}) > {MAX_POSITION}")
                if min_pos > max_pos:
                    errors.append(f"{motor_id}: min_pos > max_pos")

        # Проверка motor_mapping
        if "motor_mapping" in config:
            for joint_key, mapping in config["motor_mapping"].items():
                if not joint_key.startswith("joint_"):
                    errors.append(f"Неверный ключ сустава: {joint_key}")
                    continue

                if "motor_id" not in mapping:
                    errors.append(f"{joint_key}: отсутствует motor_id")

        return len(errors) == 0, errors

    def validate_program(self, program: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        """
        Валидация программы.

        Args:
            program: Список блоков программы

        Returns:
            (success, список ошибок)
        """
        errors = []
        valid_types = {
            "move_to",
            "move_all",
            "wait_time",
            "torque_on",
            "torque_off",
            "home",
        }

        for i, block in enumerate(program):
            if "type" not in block:
                errors.append(f"Блок {i}: отсутствует тип")
                continue

            if block["type"] not in valid_types:
                errors.append(f"Блок {i}: неверный тип '{block['type']}'")

            if "params" not in block:
                errors.append(f"Блок {i}: отсутствуют параметры")

        return len(errors) == 0, errors

    # ==================== Загрузка/Сохранение ====================

    def load_config(self, filename: str = CONFIG_FILE, validate: bool = True) -> dict[str, Any]:
        """
        Загрузка конфигурации из файла.

        Args:
            filename: Имя файла конфигурации
            validate: Проверять валидность

        Returns:
            Словарь с конфигурацией

        Raises:
            ConfigValidationError: Если валидация не прошла
        """
        filepath = self.config_dir / filename

        if not filepath.exists():
            return self._get_default_config()

        with open(filepath, encoding="utf-8") as f:
            config = json.load(f)

        # Валидация
        if validate:
            is_valid, errors = self.validate_motor_config(config)
            if not is_valid:
                raise ConfigValidationError("Ошибка валидации конфигурации:\n" + "\n".join(errors))

        self._config_cache[filename] = config
        return config

    def save_config(
        self,
        filename: str = CONFIG_FILE,
        config: dict[str, Any] | None = None,
        backup: bool = True,
    ) -> bool:
        """
        Сохранение конфигурации в файл с резервным копированием.

        Args:
            filename: Имя файла конфигурации
            config: Словарь с конфигурацией
            backup: Создать резервную копию

        Returns:
            True если успешно
        """
        filepath = self.config_dir / filename

        if config is None:
            config = self._config_cache.get(filename, self._get_default_config())

        # Валидация перед сохранением
        is_valid, errors = self.validate_motor_config(config)
        if not is_valid:
            print(f"⚠️ Предупреждение валидации: {'; '.join(errors)}")

        # Резервное копирование
        if backup and filepath.exists():
            self._create_backup(filepath)

        # Добавляем метку времени
        config["last_modified"] = datetime.now().isoformat()

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # Обновление истории
            self._add_to_history(filename, str(filepath))
            self._config_cache[filename] = config
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения конфигурации: {e}")
            return False

    def _create_backup(self, filepath: Path) -> None:
        """Создание резервной копии файла."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = filepath.with_suffix(f".{timestamp}.bak")

        try:
            shutil.copy2(filepath, backup_path)
        except Exception as e:
            print(f"⚠️ Не удалось создать резервную копию: {e}")

    def _add_to_history(self, filename: str, filepath: str) -> None:
        """Добавление записи в историю."""
        if filename not in self._config_history:
            self._config_history[filename] = []

        self._config_history[filename].append(filepath)

        # Ограничение истории
        if len(self._config_history[filename]) > self._max_history:
            self._config_history[filename].pop(0)

    def load_program(self, filename: str = PROGRAM_FILE) -> list:
        """
        Загрузка программы блочного программирования.

        Args:
            filename: Имя файла программы

        Returns:
            Список блоков программы
        """
        filepath = self.config_dir / filename

        if not filepath.exists():
            return []

        try:
            with open(filepath, encoding="utf-8") as f:
                program = json.load(f)
            return program
        except Exception as e:
            print(f"❌ Ошибка загрузки программы: {e}")
            return []

    def save_program(self, filename: str = PROGRAM_FILE, program: list = None) -> bool:
        """
        Сохранение программы блочного программирования.

        Args:
            filename: Имя файла программы
            program: Список блоков программы

        Returns:
            True если успешно, False если ошибка
        """
        filepath = self.config_dir / filename

        if program is None:
            program = []

        program_data = {
            "blocks": program,
            "created": datetime.now().isoformat(),
            "version": "1.0",
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(program_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения программы: {e}")
            return False

    def get_motor_config(self, motor_id: int) -> dict[str, Any]:
        """
        Получение конфигурации конкретного мотора.

        Args:
            motor_id: ID мотора

        Returns:
            Словарь с конфигурацией мотора
        """
        config = self._config_cache.get(CONFIG_FILE, {})
        motor_config = config.get("motor_config", DEFAULT_MOTOR_CONFIG)
        key = f"motor_{motor_id}"
        return motor_config.get(key, {"min_pos": 0, "max_pos": 4095, "name": f"Мотор {motor_id}"})

    def get_motor_mapping(self) -> dict[str, Any]:
        """
        Получение соответствия моторов суставам.

        Returns:
            Словарь с соответствием моторов
        """
        config = self._config_cache.get(CONFIG_FILE, {})
        return config.get("motor_mapping", DEFAULT_MOTOR_MAPPING)

    def set_motor_config(self, motor_id: int, config: dict[str, Any]) -> None:
        """
        Установка конфигурации мотора.

        Args:
            motor_id: ID мотора
            config: Новая конфигурация
        """
        if CONFIG_FILE not in self._config_cache:
            self._config_cache[CONFIG_FILE] = self._get_default_config()

        motor_config = self._config_cache[CONFIG_FILE].setdefault("motor_config", {})
        key = f"motor_{motor_id}"
        motor_config[key] = config

    def set_motor_mapping(self, mapping: dict[str, Any]) -> None:
        """
        Установка соответствия моторов суставам.

        Args:
            mapping: Новое соответствие
        """
        if CONFIG_FILE not in self._config_cache:
            self._config_cache[CONFIG_FILE] = self._get_default_config()

        self._config_cache[CONFIG_FILE]["motor_mapping"] = mapping

    def set_port(self, port: str) -> None:
        """
        Установка COM порта.

        Args:
            port: Имя COM порта
        """
        if CONFIG_FILE not in self._config_cache:
            self._config_cache[CONFIG_FILE] = self._get_default_config()

        self._config_cache[CONFIG_FILE]["port"] = port

    def get_port(self) -> str:
        """
        Получение COM порта.

        Returns:
            Имя COM порта
        """
        config = self._config_cache.get(CONFIG_FILE, {})
        return config.get("port", "COM3")

    def _get_default_config(self) -> dict[str, Any]:
        """
        Получение конфигурации по умолчанию.

        Returns:
            Словарь с конфигурацией по умолчанию
        """
        return {
            "port": "COM3",
            "motor_config": DEFAULT_MOTOR_CONFIG,
            "motor_mapping": DEFAULT_MOTOR_MAPPING,
            "created": datetime.now().isoformat(),
        }

    def clear_cache(self) -> None:
        """Очистка кэша конфигурации."""
        self._config_cache.clear()

    def backup_config(self, backup_filename: str) -> bool:
        """
        Создание резервной копии конфигурации.

        Args:
            backup_filename: Имя файла резервной копии

        Returns:
            True если успешно, False если ошибка
        """
        config = self._config_cache.get(CONFIG_FILE, {})
        if not config:
            config = self.load_config()

        backup_path = self.config_dir / backup_filename

        try:
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Ошибка создания резервной копии: {e}")
            return False
