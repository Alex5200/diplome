#!/usr/bin/env python3
"""
CameraService — кроссплатформенный сервис захвата камеры.

Поддерживаемые платформы:
    macOS   → cv2.CAP_AVFOUNDATION  (нативный Apple AVFoundation)
    Windows → cv2.CAP_DSHOW         (DirectShow, самый совместимый)
    Linux   → cv2.CAP_V4L2          (Video4Linux2)

Поддерживаемые платформы:
    macOS   → cv2.CAP_AVFOUNDATION  (нативный Apple AVFoundation)
    Windows → cv2.CAP_DSHOW         (DirectShow, самый совместимый)
    Linux   → cv2.CAP_V4L2          (Video4Linux2)

Преимущества перед ffmpeg subprocess:
    - Нет внешних зависимостей (только opencv-python)
    - Одинаковое поведение на всех платформах
    - Правильная обработка разрешений камеры (macOS TCC)
    - Нет задержек subprocess pipe

Использование:
    cam = CameraService()

    # Сканировать доступные камеры
    cameras = CameraService.scan_cameras()  # [{id, name, resolution}, ...]

    # Запустить захват
    cam.set_frame_callback(lambda rgb: ...)
    ok = cam.start(camera_id=0)

    # Получить кадр вручную
    frame = cam.get_frame()  # RGB numpy array или None

    # Остановить
    cam.stop()

TDD: app/tests/test_camera_service.py
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ──────────────────── Платформенные бэкенды ────────────────────


def _select_backend() -> int:
    """
    Выбрать оптимальный OpenCV бэкенд для текущей платформы.

    macOS:   CAP_AVFOUNDATION — нативный, поддерживает TCC разрешения
    Windows: CAP_DSHOW        — DirectShow, наиболее совместимый с webcam
    Linux:   CAP_V4L2         — Video4Linux2, стандарт для Linux
    Other:   CAP_ANY          — пусть OpenCV выберет сам
    """
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    elif sys.platform == "win32":
        return cv2.CAP_DSHOW
    elif sys.platform.startswith("linux"):
        return cv2.CAP_V4L2
    return cv2.CAP_ANY


@contextlib.contextmanager
def _suppress_cv2_stderr():
    """
    Временно перенаправить stderr в /dev/null.

    OpenCV печатает "out device of bound" и похожие предупреждения
    при сканировании камер на macOS — подавляем их во время скана.
    """
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    old_stderr_fd = os.dup(2)
    try:
        os.dup2(devnull_fd, 2)
        yield
    finally:
        os.dup2(old_stderr_fd, 2)
        os.close(old_stderr_fd)
        os.close(devnull_fd)


# Кэш результатов последнего сканирования (не повторяем из параллельных панелей)
_scan_cache: list[CameraInfo] | None = None
_scan_lock = threading.Lock()


def _get_camera_name(camera_id: int) -> str:
    """Получить имя камеры (платформозависимо)."""
    if sys.platform == "win32":
        try:
            # Попытка через Windows API (нет зависимостей)

            return f"Camera {camera_id}"
        except Exception:
            pass
    return f"Camera {camera_id}"


# ──────────────────── Данные ────────────────────


@dataclass
class CameraInfo:
    """Информация об одной камере."""

    id: int
    name: str
    width: int = 0
    height: int = 0
    fps: float = 0.0
    backend: str = ""

    @property
    def label(self) -> str:
        """Метка для UI комбобокса."""
        if self.width and self.height:
            return f"{self.id}: {self.name} ({self.width}×{self.height})"
        return f"{self.id}: {self.name}"

    @classmethod
    def default(cls) -> CameraInfo:
        """Дефолтная камера (fallback когда ничего не найдено)."""
        return cls(id=0, name="Default Camera")

    def __str__(self) -> str:
        return self.label


# ──────────────────── CameraService ────────────────────


class CameraService:
    """
    Кроссплатформенный сервис захвата камеры.

    Жизненный цикл:
        scan_cameras() → список доступных камер
        start(id)      → открыть камеру + запустить поток захвата
        get_frame()    → получить текущий кадр (RGB)
        stop()         → остановить захват + освободить камеру

    Callbacks:
        set_frame_callback(cb)  — вызывается на каждом кадре (RGB numpy array)
        set_error_callback(cb)  — вызывается при ошибке захвата

    Thread safety:
        Все поля защищены _lock.
        set_frame_callback можно вызывать из любого потока.
        get_frame() можно вызывать из любого потока.
    """

    DEFAULT_WIDTH = 640
    DEFAULT_HEIGHT = 480
    DEFAULT_FPS = 30

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        fps: float = DEFAULT_FPS,
    ):
        self._width = width
        self._height = height
        self._fps = fps
        self._backend = _select_backend()

        self._cap: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._camera_id: int = -1

        self._frame_callback: Callable[[np.ndarray], None] | None = None
        self._error_callback: Callable[[str], None] | None = None

        logger.debug("CameraService init (platform=%s, backend=%s)", sys.platform, self._backend)

    # ─── Сканирование ───

    @staticmethod
    def scan_cameras(max_index: int = 8, force: bool = False) -> list[CameraInfo]:
        """
        Найти все доступные камеры.

        Результат кэшируется — повторные вызовы из параллельных панелей
        не запускают повторный скан (только если force=True).

        Алгоритм:
          1. Пробует VideoCapture(i) с платформенным бэкендом
          2. При первом провале пробует CAP_ANY как fallback
          3. При двух подряд неудачах прекращает скан (нет смысла дальше)
          4. Весь вывод OpenCV подавляется через stderr redirect

        Returns:
            Список CameraInfo, отсортированный по ID.
        """
        global _scan_cache

        with _scan_lock:
            if _scan_cache is not None and not force:
                return list(_scan_cache)

            backend = _select_backend()
            found: list[CameraInfo] = []
            consecutive_fails = 0

            # Подавляем OpenCV stderr ("out device of bound" и т.п.)
            with _suppress_cv2_stderr():
                for i in range(max_index):
                    cap = cv2.VideoCapture(i, backend)
                    opened = cap.isOpened()

                    # fallback только если основной бэкенд не сработал
                    if not opened and backend != cv2.CAP_ANY:
                        cap.release()
                        cap = cv2.VideoCapture(i, cv2.CAP_ANY)
                        opened = cap.isOpened()

                    if opened:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        cap.release()
                        consecutive_fails = 0

                        found.append(
                            CameraInfo(
                                id=i,
                                name=_get_camera_name(i),
                                width=w,
                                height=h,
                                fps=fps,
                                backend=str(backend),
                            )
                        )
                        logger.info("Camera found: %d (%dx%d @ %.0ffps)", i, w, h, fps)
                    else:
                        cap.release()
                        consecutive_fails += 1
                        # На macOS AVFoundation сообщает точное число камер —
                        # после 2 провалов подряд дальше нет смысла
                        if consecutive_fails >= 2:
                            logger.debug("Stopping scan at index %d (2 consecutive failures)", i)
                            break

            if not found:
                logger.warning("No cameras detected, using fallback Camera 0")
                found.append(CameraInfo.default())

            _scan_cache = list(found)
            return list(_scan_cache)

    @staticmethod
    def invalidate_cache() -> None:
        """Сбросить кэш сканирования (вызвать перед повторным сканом)."""
        global _scan_cache
        with _scan_lock:
            _scan_cache = None

    @staticmethod
    def scan_cameras_labels(max_index: int = 8, force: bool = False) -> list[str]:
        """Вернуть список строк для UI комбобокса."""
        return [c.label for c in CameraService.scan_cameras(max_index, force=force)]

    # ─── Lifecycle ───

    def start(self, camera_id: int = 0) -> bool:
        """
        Открыть камеру и запустить поток захвата.

        Args:
            camera_id: индекс камеры (из scan_cameras)

        Returns:
            True если камера открылась успешно
        """
        if self._running:
            if self._camera_id == camera_id:
                return True  # уже запущена та же камера
            self.stop()  # перезапустить с новой камерой

        self._camera_id = camera_id
        if not self._open(camera_id):
            msg = f"Cannot open camera {camera_id}"
            logger.error(msg)
            if self._error_callback:
                self._error_callback(msg)
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"cam-{camera_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("CameraService started: camera=%d", camera_id)
        return True

    def stop(self) -> None:
        """Остановить захват и освободить камеру."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._close()
        with self._lock:
            self._frame = None
        logger.info("CameraService stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def camera_id(self) -> int:
        return self._camera_id

    # ─── Callbacks ───

    def set_frame_callback(self, cb: Callable[[np.ndarray], None] | None) -> None:
        """Установить callback для получения RGB кадров."""
        self._frame_callback = cb

    def set_error_callback(self, cb: Callable[[str], None] | None) -> None:
        """Установить callback для ошибок."""
        self._error_callback = cb

    # ─── Получение кадра ───

    def get_frame(self) -> np.ndarray | None:
        """
        Получить последний захваченный кадр (RGB, HxWx3 uint8).

        Thread-safe. Возвращает копию.
        """
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    # ─── Настройки ───

    def set_resolution(self, width: int, height: int) -> None:
        """Изменить желаемое разрешение (применяется при следующем start)."""
        self._width = width
        self._height = height

    def set_fps(self, fps: float) -> None:
        self._fps = fps

    def get_actual_resolution(self) -> tuple[int, int]:
        """Получить реальное разрешение открытой камеры."""
        if self._cap and self._cap.isOpened():
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return w, h
        return self._width, self._height

    # ─── Внутренние методы ───

    def _open(self, camera_id: int) -> bool:
        """Открыть VideoCapture с платформенным бэкендом."""
        # Подавляем предупреждения OpenCV при открытии
        with _suppress_cv2_stderr():
            # Попытка 1: платформенный бэкенд
            cap = cv2.VideoCapture(camera_id, self._backend)

            # Попытка 2: CAP_ANY как fallback
            if not cap.isOpened() and self._backend != cv2.CAP_ANY:
                logger.debug("Backend %s failed, trying CAP_ANY", self._backend)
                cap.release()
                cap = cv2.VideoCapture(camera_id, cv2.CAP_ANY)

        if not cap.isOpened():
            cap.release()
            return False

        # Настройка разрешения и FPS
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        cap.set(cv2.CAP_PROP_FPS, self._fps)

        # Буфер 1 кадр для минимальной задержки
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._cap = cap
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        logger.info("Camera %d opened: %dx%d @ %.0ffps", camera_id, actual_w, actual_h, actual_fps)
        return True

    def _close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def _capture_loop(self) -> None:
        """Основной поток захвата кадров."""
        fail_count = 0
        max_fails = 10

        while self._running:
            if not self._cap or not self._cap.isOpened():
                time.sleep(0.1)
                continue

            ret, bgr = self._cap.read()

            if not ret:
                fail_count += 1
                logger.debug("Camera read failed (%d/%d)", fail_count, max_fails)
                if fail_count >= max_fails:
                    msg = f"Camera {self._camera_id}: too many read failures"
                    logger.error(msg)
                    if self._error_callback:
                        self._error_callback(msg)
                    break
                time.sleep(0.05)
                continue

            fail_count = 0

            # BGR → RGB
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

            with self._lock:
                self._frame = rgb

            if self._frame_callback:
                try:
                    self._frame_callback(rgb)
                except Exception as e:
                    logger.exception("frame_callback error: %s", e)

            # Небольшая пауза чтобы не перегружать CPU
            time.sleep(1.0 / max(self._fps, 1))

        self._running = False
        logger.debug("capture_loop exited for camera %d", self._camera_id)

    def __repr__(self) -> str:
        status = f"camera={self._camera_id}" if self._running else "stopped"
        return f"CameraService({status}, backend={self._backend})"
