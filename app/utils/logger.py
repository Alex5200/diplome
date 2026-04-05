#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Application Logger Module

Модуль логирования событий приложения с поддержкой уровней и цветного вывода.
"""

import logging
import sys
from datetime import datetime
from typing import Optional
from enum import Enum


class LogLevel(Enum):
    """Уровни логирования."""
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    SUCCESS = 'success'
    DEBUG = 'debug'


class AppLogger:
    """
    Класс логгера приложения.

    Поддерживает:
        - Вывод в консоль с цветными метками
        - Вывод в файл
        - Уровни логирования
        - Форматирование с временными метками

    Пример использования:
        logger = AppLogger('robot_app')
        logger.info('Приложение запущено')
        logger.success('Подключение успешно')
        logger.warning('Предупреждение о температуре')
        logger.error('Ошибка подключения')
    """

    # Цвета для консольного вывода
    COLORS = {
        'INFO': '\033[94m',      # Синий
        'WARNING': '\033[93m',   # Желтый
        'ERROR': '\033[91m',     # Красный
        'SUCCESS': '\033[92m',   # Зеленый
        'DEBUG': '\033[90m',     # Серый
        'RESET': '\033[0m'       # Сброс
    }

    def __init__(self, name: str = 'robot_app', log_file: Optional[str] = None, level: LogLevel = LogLevel.INFO):
        """
        Инициализация логгера.

        Args:
            name: Имя логгера
            log_file: Путь к файлу логов (опционально)
            level: Минимальный уровень логирования
        """
        self.name = name
        self.level = level
        self.log_file = log_file
        self._file_handler: Optional[logging.FileHandler] = None
        self._setup_logger()

    def _setup_logger(self):
        """Настройка обработчиков логгера."""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)  # Внутренне используем DEBUG для всех уровней

        # Очищаем существующие обработчики
        self.logger.handlers.clear()

        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                              datefmt='%H:%M:%S')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # Файловый обработчик (если указан файл)
        if self.log_file:
            try:
                self._file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
                self._file_handler.setLevel(logging.DEBUG)
                file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                self._file_handler.setFormatter(file_formatter)
                self.logger.addHandler(self._file_handler)
            except Exception as e:
                print(f"⚠️ Не удалось создать файл логов: {e}")

    def _log(self, level: str, message: str):
        """
        Внутренний метод логирования.

        Args:
            level: Уровень логирования
            message: Сообщение
        """
        level_map = {
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'SUCCESS': logging.INFO,  # SUCCESS мапим на INFO
            'DEBUG': logging.DEBUG,
        }

        log_level = level_map.get(level, logging.INFO)

        if self.logger.isEnabledFor(log_level):
            # Для консольного вывода с цветом
            timestamp = datetime.now().strftime('%H:%M:%S')
            color = self.COLORS.get(level, self.COLORS['RESET'])
            reset = self.COLORS['RESET']

            # Проверяем, является ли вывод терминалом
            if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
                print(f"{color}[{timestamp}] {level}: {message}{reset}")
            else:
                print(f"[{timestamp}] {level}: {message}")

            # Для файлового вывода
            self.logger.log(log_level, message)

    def info(self, message: str):
        """Логирование информационного сообщения."""
        self._log('INFO', message)

    def warning(self, message: str):
        """Логирование предупреждения."""
        self._log('WARNING', message)

    def error(self, message: str):
        """Логирование ошибки."""
        self._log('ERROR', message)

    def success(self, message: str):
        """Логирование успешного действия."""
        self._log('SUCCESS', message)

    def debug(self, message: str):
        """Логирование отладочной информации."""
        if self.level == LogLevel.DEBUG:
            self._log('DEBUG', message)

    def set_level(self, level: LogLevel):
        """
        Установка уровня логирования.

        Args:
            level: Новый уровень логирования
        """
        self.level = level

    def close(self):
        """Закрытие логгера и освобождение ресурсов."""
        if self._file_handler:
            self._file_handler.close()
        self.logger.handlers.clear()
