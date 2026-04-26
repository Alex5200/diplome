#!/usr/bin/env python3

"""
Universal AI Provider — единый интерфейс для любых LLM/VLM бэкендов.

Поддерживаемые провайдеры:
    - Ollama (локальный, http://localhost:11434)
    - LM Studio (локальный/удалённый, OpenAI-совместимый API)
    - OpenAI API (gpt-4o, gpt-4-vision)
    - Любой OpenAI-compatible сервер (vLLM, text-generation-inference, LocalAI и др.)

Использование:
    # Ollama (локальный Qwen VL)
    provider = AIProvider.ollama(model="qwen2.5-vl")

    # LM Studio (удалённый сервер)
    provider = AIProvider.lm_studio(url="http://192.168.1.100:1234", model="qwen2.5-vl-7b")

    # OpenAI
    provider = AIProvider.openai(api_key="sk-...", model="gpt-4o")

    # Произвольный OpenAI-compatible сервер
    provider = AIProvider.custom(url="http://myserver:8080/v1", model="my-model")

    # Универсальный запрос
    response = provider.chat("Что на картинке?", images=[frame])
    response = provider.chat_json("Find the red ball", images=[frame], schema={"found": bool})
"""

import base64
import io
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
import requests
from PIL import Image

logger = logging.getLogger(__name__)


# ──────────────────── Типы провайдеров ────────────────────


class ProviderType(StrEnum):
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"


# ──────────────────── Данные ────────────────────


@dataclass
class AIResponse:
    """Ответ от AI-модели."""

    success: bool
    content: str = ""
    json_data: dict | None = None
    model: str = ""
    latency: float = 0.0  # секунд
    tokens_used: int = 0
    error: str = ""

    def get(self, key: str, default=None):
        """Получить значение из json_data."""
        if self.json_data:
            return self.json_data.get(key, default)
        return default


@dataclass
class AIConfig:
    """Конфигурация AI-провайдера."""

    provider_type: ProviderType = ProviderType.OLLAMA
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5-vl"
    api_key: str = ""
    temperature: float = 0.1
    max_tokens: int = 300
    timeout: int = 30
    # Дополнительные параметры
    extra_params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider_type.value,
            "url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


# ──────────────────── Утилиты ────────────────────


def frame_to_base64(frame: np.ndarray, quality: int = 85) -> str:
    """Конвертировать RGB numpy-кадр в base64 JPEG (через PIL, без cv2)."""
    img = Image.fromarray(frame)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def parse_json_from_text(text: str) -> dict | None:
    """Извлечь JSON из текстового ответа модели (с обработкой markdown)."""
    text = text.strip()

    # Убрать markdown code blocks
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{") or part.startswith("["):
                text = part
                break

    # Найти JSON
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        # Попробовать массив
        start = text.find("[")
        end = text.rfind("]")
    if start == -1 or end == -1:
        return None

    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


# ──────────────────── Базовый класс бэкенда ────────────────────


class AIBackend(ABC):
    """Абстрактный бэкенд для AI-провайдера."""

    def __init__(self, config: AIConfig):
        self.config = config

    @abstractmethod
    def chat(
        self, prompt: str, images: list[np.ndarray] | None = None, system: str = ""
    ) -> AIResponse:
        """Отправить запрос к модели."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Проверить доступность сервера."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Получить список доступных моделей."""
        ...

    def chat_json(
        self, prompt: str, images: list[np.ndarray] | None = None, system: str = ""
    ) -> AIResponse:
        """Отправить запрос и распарсить JSON из ответа."""
        response = self.chat(prompt, images, system)
        if response.success:
            response.json_data = parse_json_from_text(response.content)
        return response


# ──────────────────── Ollama Backend ────────────────────


class OllamaBackend(AIBackend):
    """Бэкенд для Ollama (http://localhost:11434)."""

    def chat(
        self, prompt: str, images: list[np.ndarray] | None = None, system: str = ""
    ) -> AIResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        user_msg: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            user_msg["images"] = [frame_to_base64(img) for img in images]
        messages.append(user_msg)

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        try:
            t0 = time.time()
            r = requests.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
                timeout=self.config.timeout,
            )
            latency = time.time() - t0

            if r.status_code != 200:
                return AIResponse(
                    success=False,
                    error=f"HTTP {r.status_code}: {r.text[:200]}",
                    latency=latency,
                    model=self.config.model,
                )

            data = r.json()
            content = data.get("message", {}).get("content", "")
            tokens = data.get("eval_count", 0)

            return AIResponse(
                success=True,
                content=content,
                model=self.config.model,
                latency=latency,
                tokens_used=tokens,
            )
        except requests.RequestException as e:
            return AIResponse(success=False, error=str(e), model=self.config.model)

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.config.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.config.base_url}/api/tags", timeout=5)
            if r.status_code == 200:
                return [m["name"] for m in r.json().get("models", [])]
        except requests.RequestException:
            pass
        return []


# ──────────────────── OpenAI-Compatible Backend (LM Studio, vLLM, etc.) ────────────────────


class OpenAICompatibleBackend(AIBackend):
    """
    Бэкенд для OpenAI-совместимых API.
    Работает с: LM Studio, vLLM, text-generation-inference, LocalAI, OpenAI и др.
    """

    def chat(
        self, prompt: str, images: list[np.ndarray] | None = None, system: str = ""
    ) -> AIResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        # Формируем content с изображениями (OpenAI vision format)
        if images:
            content_parts: list[dict] = []
            for img in images:
                b64 = frame_to_base64(img)
                content_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                )
            content_parts.append({"type": "text", "text": prompt})
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        payload.update(self.config.extra_params)

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            t0 = time.time()
            # LM Studio: /v1/chat/completions
            url = self.config.base_url.rstrip("/")
            if not url.endswith("/chat/completions"):
                url = f"{url}/chat/completions"

            r = requests.post(url, json=payload, headers=headers, timeout=self.config.timeout)
            latency = time.time() - t0

            if r.status_code != 200:
                return AIResponse(
                    success=False,
                    error=f"HTTP {r.status_code}: {r.text[:300]}",
                    latency=latency,
                    model=self.config.model,
                )

            data = r.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)

            return AIResponse(
                success=True,
                content=content,
                model=self.config.model,
                latency=latency,
                tokens_used=tokens,
            )
        except requests.RequestException as e:
            return AIResponse(success=False, error=str(e), model=self.config.model)
        except (KeyError, IndexError) as e:
            return AIResponse(
                success=False, error=f"Bad response format: {e}", model=self.config.model
            )

    def is_available(self) -> bool:
        try:
            url = self.config.base_url.rstrip("/")
            # Пробуем /v1/models (стандарт OpenAI)
            if "/v1" in url:
                models_url = url.rsplit("/v1", 1)[0] + "/v1/models"
            else:
                models_url = f"{url}/models"

            headers = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            r = requests.get(models_url, headers=headers, timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        try:
            url = self.config.base_url.rstrip("/")
            if "/v1" in url:
                models_url = url.rsplit("/v1", 1)[0] + "/v1/models"
            else:
                models_url = f"{url}/models"

            headers = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            r = requests.get(models_url, headers=headers, timeout=5)
            if r.status_code == 200:
                return [m["id"] for m in r.json().get("data", [])]
        except requests.RequestException:
            pass
        return []


# ──────────────────── Фабрика / Главный класс ────────────────────


class AIProvider:
    """
    Универсальный AI-провайдер — единая точка входа для всех бэкендов.

    Примеры:
        # Ollama (локальный)
        ai = AIProvider.ollama(model="qwen2.5-vl")

        # LM Studio (удалённый сервер)
        ai = AIProvider.lm_studio(url="http://192.168.1.100:1234", model="qwen2.5-vl-7b")

        # OpenAI
        ai = AIProvider.openai(api_key="sk-...", model="gpt-4o")

        # Текстовый запрос
        resp = ai.chat("Привет!")

        # Vision-запрос (кадр с камеры)
        resp = ai.chat("Что на картинке?", images=[frame])

        # JSON-запрос (автопарсинг)
        resp = ai.chat_json("Find object", images=[frame])
        if resp.json_data and resp.json_data.get("found"):
            print(resp.json_data["bbox"])
    """

    def __init__(self, config: AIConfig):
        self.config = config
        self._backend = self._create_backend(config)

    @staticmethod
    def _create_backend(config: AIConfig) -> AIBackend:
        if config.provider_type == ProviderType.OLLAMA:
            return OllamaBackend(config)
        else:
            return OpenAICompatibleBackend(config)

    # ──────────── Фабричные методы ────────────

    @classmethod
    def ollama(
        cls,
        model: str = "qwen2.5-vl",
        url: str = "http://localhost:11434",
        temperature: float = 0.1,
        max_tokens: int = 300,
        timeout: int = 30,
    ) -> "AIProvider":
        """Создать провайдер для Ollama."""
        config = AIConfig(
            provider_type=ProviderType.OLLAMA,
            base_url=url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return cls(config)

    @classmethod
    def lm_studio(
        cls,
        url: str = "http://localhost:1234/v1",
        model: str = "qwen2.5-vl-7b",
        api_key: str = "lm-studio",  # LM Studio принимает любой ключ
        temperature: float = 0.1,
        max_tokens: int = 300,
        timeout: int = 30,
    ) -> "AIProvider":
        """Создать провайдер для LM Studio (локальный или удалённый)."""
        config = AIConfig(
            provider_type=ProviderType.LM_STUDIO,
            base_url=url,
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return cls(config)

    @classmethod
    def openai(
        cls,
        api_key: str,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        max_tokens: int = 300,
        timeout: int = 30,
    ) -> "AIProvider":
        """Создать провайдер для OpenAI API."""
        config = AIConfig(
            provider_type=ProviderType.OPENAI,
            base_url="https://api.openai.com/v1",
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return cls(config)

    @classmethod
    def custom(
        cls,
        url: str,
        model: str,
        api_key: str = "",
        temperature: float = 0.1,
        max_tokens: int = 300,
        timeout: int = 30,
        **extra,
    ) -> "AIProvider":
        """Создать провайдер для любого OpenAI-compatible сервера."""
        config = AIConfig(
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            base_url=url,
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            extra_params=extra,
        )
        return cls(config)

    @classmethod
    def from_dict(cls, data: dict) -> "AIProvider":
        """Создать из словаря/конфига (для загрузки из JSON/YAML)."""
        provider_type = data.get("provider", "ollama")
        if provider_type == "ollama":
            return cls.ollama(
                model=data.get("model", "qwen2.5-vl"),
                url=data.get("url", "http://localhost:11434"),
            )
        elif provider_type == "lm_studio":
            return cls.lm_studio(
                url=data.get("url", "http://localhost:1234/v1"),
                model=data.get("model", "qwen2.5-vl-7b"),
                api_key=data.get("api_key", "lm-studio"),
            )
        elif provider_type == "openai":
            return cls.openai(
                api_key=data.get("api_key", ""),
                model=data.get("model", "gpt-4o"),
            )
        else:
            return cls.custom(
                url=data.get("url", ""),
                model=data.get("model", ""),
                api_key=data.get("api_key", ""),
            )

    # ──────────── API ────────────

    def chat(
        self, prompt: str, images: list[np.ndarray] | None = None, system: str = ""
    ) -> AIResponse:
        """
        Отправить сообщение модели.

        Args:
            prompt: Текст запроса
            images: Список кадров OpenCV (BGR numpy arrays) для vision-моделей
            system: Системный промпт

        Returns:
            AIResponse с ответом модели
        """
        return self._backend.chat(prompt, images, system)

    def chat_json(
        self, prompt: str, images: list[np.ndarray] | None = None, system: str = ""
    ) -> AIResponse:
        """
        Отправить запрос и автоматически распарсить JSON из ответа.

        Полезно для structured output (детекция, классификация и т.д.)
        """
        return self._backend.chat_json(prompt, images, system)

    def is_available(self) -> bool:
        """Проверить доступность сервера."""
        return self._backend.is_available()

    def list_models(self) -> list[str]:
        """Получить список моделей на сервере."""
        return self._backend.list_models()

    def get_config(self) -> dict:
        """Получить текущую конфигурацию."""
        return self.config.to_dict()

    def switch_model(self, model: str):
        """Сменить модель на лету."""
        self.config.model = model
        logger.info("Switched model to: %s", model)

    def switch_provider(self, config: AIConfig):
        """Полностью сменить провайдер."""
        self.config = config
        self._backend = self._create_backend(config)
        logger.info("Switched provider to: %s (%s)", config.provider_type.value, config.model)

    def __repr__(self) -> str:
        return (
            f"AIProvider(type={self.config.provider_type.value}, "
            f"model={self.config.model}, url={self.config.base_url})"
        )
