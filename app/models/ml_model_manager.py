#!/usr/bin/env python3
"""
ML Model Manager — управление кастомными и готовыми ML-моделями для vision.

Архитектура:
    BaseMLModel          → абстрактный интерфейс модели
    CustomVisionModel    → кастомная PyTorch модель (своё обучение)
    FineTunedVisionModel → дообученная готовая модель (ResNet/YOLO/etc.)
    VisionModelManager   → менеджер: загрузка, выбор, предсказание
    AIRobotController    → прослойка ИИ → команды робота

TDD-принципы:
    - Все публичные методы покрываются тестами в app/tests/test_ml_model_manager.py
    - Зависимости инжектируются (нет глобального состояния)
    - Каждый класс имеет одну ответственность
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ──────────────────── Типы результатов ────────────────────


@dataclass
class DetectionResult:
    """Результат детекции объекта."""

    found: bool = False
    label: str = ""
    confidence: float = 0.0
    bbox: list[float] = field(default_factory=list)  # [x1, y1, x2, y2] нормализованные
    cx: float = 0.5
    cy: float = 0.5
    width: float = 0.0
    height: float = 0.0
    model_name: str = ""
    latency_ms: float = 0.0
    raw_output: Any = None

    @classmethod
    def not_found(cls, model_name: str = "") -> "DetectionResult":
        return cls(found=False, model_name=model_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "label": self.label,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "cx": self.cx,
            "cy": self.cy,
            "model_name": self.model_name,
            "latency_ms": self.latency_ms,
        }


@dataclass
class RobotCommand:
    """Команда управления роботом от ИИ."""

    joint_deltas: list[float] = field(default_factory=lambda: [0.0] * 6)
    gripper_open: bool | None = None  # None = не менять
    speed: int = 800
    description: str = ""

    @classmethod
    def idle(cls) -> "RobotCommand":
        return cls(description="idle")

    def to_dict(self) -> dict[str, Any]:
        return {
            "joint_deltas": self.joint_deltas,
            "gripper_open": self.gripper_open,
            "speed": self.speed,
            "description": self.description,
        }


# ──────────────────── Базовый класс модели ────────────────────


class BaseMLModel(ABC):
    """Абстрактный интерфейс для любой ML-модели."""

    def __init__(self, name: str, model_path: str | None = None):
        self.name = name
        self.model_path = model_path
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @abstractmethod
    def load(self) -> bool:
        """Загрузить модель. Возвращает True при успехе."""
        ...

    @abstractmethod
    def predict(self, frame: np.ndarray) -> DetectionResult:
        """Детекция объекта в кадре (RGB uint8 HxWx3)."""
        ...

    def unload(self) -> None:
        """Выгрузить модель из памяти."""
        self._loaded = False
        logger.info("[%s] unloaded", self.name)

    def __repr__(self) -> str:
        status = "loaded" if self._loaded else "unloaded"
        return f"{self.__class__.__name__}(name={self.name!r}, {status})"


# ──────────────────── Кастомная PyTorch модель ────────────────────


class CustomVisionModel(BaseMLModel):
    """
    Кастомная модель на PyTorch (.pt / .pth файл).

    Формат модели:
        model.forward(tensor) → tensor shape [N, 5+C]
        где 5 = [cx, cy, w, h, conf], C = число классов
    """

    def __init__(
        self,
        name: str,
        model_path: str,
        class_names: list[str] | None = None,
        conf_threshold: float = 0.5,
        device: str = "cpu",
    ):
        super().__init__(name, model_path)
        self.class_names = class_names or ["object"]
        self.conf_threshold = conf_threshold
        self.device = device
        self._model = None

    def load(self) -> bool:
        try:
            import torch  # noqa: F401

            if not os.path.exists(self.model_path):
                logger.error("[%s] model file not found: %s", self.name, self.model_path)
                return False

            import torch

            self._model = torch.load(self.model_path, map_location=self.device)
            self._model.eval()
            self._loaded = True
            logger.info("[%s] loaded from %s on %s", self.name, self.model_path, self.device)
            return True
        except ImportError:
            logger.error("PyTorch not installed. Run: pip install torch torchvision")
            return False
        except Exception as e:
            logger.exception("[%s] load failed: %s", self.name, e)
            return False

    def predict(self, frame: np.ndarray) -> DetectionResult:
        import time

        if not self._loaded or self._model is None:
            return DetectionResult.not_found(self.name)

        t0 = time.time()
        try:
            import torch
            import torchvision.transforms.functional as TF

            tensor = TF.to_tensor(frame).unsqueeze(0).to(self.device)
            with torch.no_grad():
                output = self._model(tensor)

            latency = (time.time() - t0) * 1000
            return self._parse_output(output, latency)
        except Exception as e:
            logger.exception("[%s] predict failed: %s", self.name, e)
            return DetectionResult.not_found(self.name)

    def _parse_output(self, output, latency_ms: float) -> DetectionResult:
        """Разобрать вывод модели в DetectionResult."""
        try:
            import torch

            if isinstance(output, (list, tuple)):
                output = output[0]

            # Ожидаем [N, 5+C] или [5+C]
            if hasattr(output, "squeeze"):
                output = output.squeeze()

            if output.dim() == 1:
                arr = output.cpu().numpy()
            else:
                # Взять детекцию с максимальной уверенностью
                confs = output[:, 4].cpu().numpy()
                best = int(confs.argmax())
                arr = output[best].cpu().numpy()

            conf = float(arr[4])
            if conf < self.conf_threshold:
                return DetectionResult.not_found(self.name)

            cx, cy, w, h = float(arr[0]), float(arr[1]), float(arr[2]), float(arr[3])
            class_id = int(arr[5:].argmax()) if len(arr) > 5 else 0
            label = self.class_names[class_id] if class_id < len(self.class_names) else "object"

            return DetectionResult(
                found=True,
                label=label,
                confidence=conf,
                bbox=[cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
                cx=cx,
                cy=cy,
                width=w,
                height=h,
                model_name=self.name,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.exception("[%s] parse_output failed: %s", self.name, e)
            return DetectionResult.not_found(self.name)


# ──────────────────── Дообученная готовая модель (YOLO/ResNet) ────────────────────


class FineTunedVisionModel(BaseMLModel):
    """
    Дообученная модель через Ultralytics YOLO (yolov8/yolov11).

    Установка: pip install ultralytics
    Обучение:  yolo train data=dataset.yaml model=yolov8n.pt epochs=50
    Экспорт:   yolo export model=best.pt format=torchscript
    """

    def __init__(
        self,
        name: str,
        model_path: str,
        conf_threshold: float = 0.45,
        iou_threshold: float = 0.5,
        target_class: str | None = None,
    ):
        super().__init__(name, model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.target_class = target_class  # если None — брать лучший результат
        self._yolo = None

    def load(self) -> bool:
        try:
            from ultralytics import YOLO  # noqa: F401
        except ImportError:
            logger.error("Ultralytics not installed. Run: pip install ultralytics")
            return False

        try:
            from ultralytics import YOLO

            self._yolo = YOLO(self.model_path)
            self._loaded = True
            logger.info("[%s] YOLO loaded from %s", self.name, self.model_path)
            return True
        except Exception as e:
            logger.exception("[%s] YOLO load failed: %s", self.name, e)
            return False

    def predict(self, frame: np.ndarray) -> DetectionResult:
        import time

        if not self._loaded or self._yolo is None:
            return DetectionResult.not_found(self.name)

        t0 = time.time()
        try:
            results = self._yolo(
                frame,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False,
            )
            latency = (time.time() - t0) * 1000

            if not results or len(results[0].boxes) == 0:
                return DetectionResult.not_found(self.name)

            boxes = results[0].boxes
            names = results[0].names

            # Фильтр по классу если задан
            best_conf = -1.0
            best_box = None
            best_label = ""

            for box in boxes:
                cls_id = int(box.cls[0])
                label = names.get(cls_id, str(cls_id))
                conf = float(box.conf[0])

                if self.target_class and label.lower() != self.target_class.lower():
                    continue

                if conf > best_conf:
                    best_conf = conf
                    best_box = box.xyxyn[0].cpu().numpy()  # нормализованный xyxy
                    best_label = label

            if best_box is None:
                return DetectionResult.not_found(self.name)

            x1, y1, x2, y2 = best_box
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            w = x2 - x1
            h = y2 - y1

            return DetectionResult(
                found=True,
                label=best_label,
                confidence=best_conf,
                bbox=[float(x1), float(y1), float(x2), float(y2)],
                cx=float(cx),
                cy=float(cy),
                width=float(w),
                height=float(h),
                model_name=self.name,
                latency_ms=latency,
            )
        except Exception as e:
            logger.exception("[%s] predict failed: %s", self.name, e)
            return DetectionResult.not_found(self.name)

    def train(
        self,
        data_yaml: str,
        epochs: int = 50,
        imgsz: int = 640,
        output_dir: str = "runs/train",
    ) -> str | None:
        """
        Запустить дообучение YOLO на своём датасете.

        Args:
            data_yaml: путь к dataset.yaml (формат Ultralytics)
            epochs: количество эпох
            imgsz: размер входного изображения
            output_dir: директория для сохранения весов

        Returns:
            Путь к лучшим весам (best.pt) или None при ошибке.
        """
        if not self._loaded or self._yolo is None:
            logger.error("[%s] model not loaded, cannot train", self.name)
            return None

        try:
            results = self._yolo.train(
                data=data_yaml,
                epochs=epochs,
                imgsz=imgsz,
                project=output_dir,
                name=self.name,
            )
            best_path = str(results.save_dir / "weights" / "best.pt")
            logger.info("[%s] training complete → %s", self.name, best_path)
            return best_path
        except Exception as e:
            logger.exception("[%s] training failed: %s", self.name, e)
            return None


# ──────────────────── Менеджер моделей ────────────────────


class VisionModelManager:
    """
    Менеджер ML-моделей.

    Функции:
        - Регистрация / загрузка / выгрузка моделей
        - Выбор активной модели
        - Предсказание через активную модель
        - Список доступных моделей
    """

    def __init__(self):
        self._models: dict[str, BaseMLModel] = {}
        self._active_name: str | None = None

    # ── Регистрация ──

    def register(self, model: BaseMLModel, load_now: bool = False) -> bool:
        """Зарегистрировать модель."""
        self._models[model.name] = model
        logger.info("Registered model: %s", model.name)
        if load_now:
            return model.load()
        return True

    def unregister(self, name: str) -> bool:
        """Удалить модель из менеджера."""
        if name not in self._models:
            return False
        self._models[name].unload()
        del self._models[name]
        if self._active_name == name:
            self._active_name = None
        return True

    # ── Загрузка ──

    def load(self, name: str) -> bool:
        """Загрузить модель по имени."""
        if name not in self._models:
            logger.error("Model not registered: %s", name)
            return False
        return self._models[name].load()

    def load_all(self) -> dict[str, bool]:
        """Загрузить все зарегистрированные модели."""
        return {name: model.load() for name, model in self._models.items()}

    # ── Активная модель ──

    def set_active(self, name: str) -> bool:
        """Выбрать активную модель для предсказаний."""
        if name not in self._models:
            logger.error("Cannot set active — model not registered: %s", name)
            return False
        if not self._models[name].is_loaded:
            ok = self._models[name].load()
            if not ok:
                return False
        self._active_name = name
        logger.info("Active model → %s", name)
        return True

    @property
    def active_model(self) -> BaseMLModel | None:
        if self._active_name:
            return self._models.get(self._active_name)
        return None

    # ── Предсказание ──

    def predict(self, frame: np.ndarray) -> DetectionResult:
        """Детекция через активную модель."""
        if self.active_model is None:
            return DetectionResult.not_found("no_model")
        return self.active_model.predict(frame)

    # ── Информация ──

    def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "type": type(model).__name__,
                "loaded": model.is_loaded,
                "active": name == self._active_name,
                "path": model.model_path,
            }
            for name, model in self._models.items()
        ]

    def __len__(self) -> int:
        return len(self._models)

    def __repr__(self) -> str:
        return f"VisionModelManager(models={list(self._models)}, active={self._active_name!r})"


# ──────────────────── ИИ-прослойка → команды робота ────────────────────


class AIRobotController:
    """
    Прослойка: детекция объекта → команды управления роботом.

    Логика:
        1. Получаем DetectionResult от VisionModelManager
        2. Вычисляем ошибку позиции (объект - центр кадра)
        3. PID → дельты суставов J1 (pan) и J2 (tilt)
        4. Если объект найден и в зоне захвата → команда grip

    Интеграция с VisionTrackerService:
        Может работать параллельно с VLM-трекером, заменяя его
        или дополняя для задач манипуляции.
    """

    GRIP_ZONE_SIZE = 0.15  # нормализованный размер объекта = "близко"
    CENTER_DEADZONE = 0.05  # ошибка меньше этого = уже по центру

    def __init__(
        self,
        model_manager: VisionModelManager,
        kp_pan: float = 20.0,
        kp_tilt: float = 15.0,
        max_delta: float = 10.0,
    ):
        self.manager = model_manager
        self.kp_pan = kp_pan
        self.kp_tilt = kp_tilt
        self.max_delta = max_delta
        self._last_result: DetectionResult | None = None

    def process_frame(self, frame: np.ndarray) -> RobotCommand:
        """
        Главный метод: кадр → команда робота.

        Args:
            frame: RGB uint8 HxWx3

        Returns:
            RobotCommand с дельтами суставов
        """
        result = self.manager.predict(frame)
        self._last_result = result

        if not result.found:
            return RobotCommand.idle()

        # Ошибка от центра кадра
        err_x = result.cx - 0.5
        err_y = result.cy - 0.5

        # Мёртвая зона
        if abs(err_x) < self.CENTER_DEADZONE and abs(err_y) < self.CENTER_DEADZONE:
            cmd = RobotCommand(description="centered")
        else:
            delta_j1 = float(self._clamp(-self.kp_pan * err_x))
            delta_j2 = float(self._clamp(-self.kp_tilt * err_y))
            cmd = RobotCommand(
                joint_deltas=[delta_j1, delta_j2, 0, 0, 0, 0],
                description=f"tracking err=({err_x:+.2f},{err_y:+.2f})",
            )

        # Проверка зоны захвата
        if result.width >= self.GRIP_ZONE_SIZE and result.height >= self.GRIP_ZONE_SIZE:
            cmd.gripper_open = False
            cmd.description += " [GRIP]"
            logger.info(
                "Object in grip zone: %s (%.2f x %.2f)", result.label, result.width, result.height
            )

        return cmd

    def _clamp(self, v: float) -> float:
        return max(-self.max_delta, min(self.max_delta, v))

    @property
    def last_detection(self) -> DetectionResult | None:
        return self._last_result

    def get_status(self) -> dict[str, Any]:
        return {
            "active_model": self.manager._active_name,
            "last_detection": self._last_result.to_dict() if self._last_result else None,
            "models": self.manager.list_models(),
        }
