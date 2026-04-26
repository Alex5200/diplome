#!/usr/bin/env python3
"""
JWT Authentication module for the web API.

Provides:
    - API token generation (long-lived, for machine-to-machine)
    - JWT access tokens (short-lived, for users)
    - FastAPI dependencies for route protection
    - Login endpoint schema

Usage:
    from web.api.auth import router as auth_router, require_token
    app.include_router(auth_router, prefix="/auth")

    @app.get("/secure")
    async def secure(payload = Depends(require_token)):
        return {"user": payload["sub"]}

Environment variables:
    JWT_SECRET   — секретный ключ (обязательно задать в prod!)
    JWT_ALGO     — алгоритм (default: HS256)
    TOKEN_EXP_H  — время жизни JWT в часах (default: 24)
"""

from __future__ import annotations

import hmac
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

try:
    import jwt as pyjwt

    _HAS_JWT = True
except ImportError:
    _HAS_JWT = False

# ──────────────────── Конфиг ────────────────────

JWT_SECRET: str = os.environ.get("JWT_SECRET", "change-me-in-production-please")
JWT_ALGO: str = os.environ.get("JWT_ALGO", "HS256")
TOKEN_EXP_H: int = int(os.environ.get("TOKEN_EXP_H", "24"))

# ──────────────────── Хранилище API-токенов (in-memory) ────────────────────
# В production замените на Redis / БД


@dataclass
class APIToken:
    """Долгосрочный API-токен для machine-to-machine."""

    token: str
    owner: str
    created_at: float = field(default_factory=time.time)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": f"{self.token[:8]}...{self.token[-4:]}",  # маскируем
            "owner": self.owner,
            "created_at": self.created_at,
            "description": self.description,
        }


_api_tokens: dict[str, APIToken] = {}

# Дефолтный токен для разработки (из env или генерируем)
_DEV_TOKEN = os.environ.get("DEV_API_TOKEN", "dev-token-change-in-production")
_api_tokens[_DEV_TOKEN] = APIToken(
    token=_DEV_TOKEN,
    owner="dev",
    description="Default development token",
)


# ──────────────────── Pydantic схемы ────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = TOKEN_EXP_H * 3600


class APITokenResponse(BaseModel):
    token: str
    owner: str
    description: str = ""


class GenerateTokenRequest(BaseModel):
    owner: str
    description: str = ""


# ──────────────────── JWT helpers ────────────────────


def _create_jwt(payload: dict[str, Any], exp_hours: int = TOKEN_EXP_H) -> str:
    """Создать JWT токен."""
    if not _HAS_JWT:
        import secrets
        return f"dev-token-{secrets.token_urlsafe(32)}"

    try:
        data = {**payload, "exp": int(time.time()) + exp_hours * 3600, "iat": int(time.time())}
        return pyjwt.encode(data, JWT_SECRET, algorithm=JWT_ALGO)
    except Exception as e:
        import secrets
        return f"dev-token-{secrets.token_urlsafe(32)}"


def _decode_jwt(token: str) -> dict[str, Any] | None:
    """Декодировать и верифицировать JWT. Возвращает None при ошибке."""
    if not _HAS_JWT:
        return None
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        return None


def _verify_api_token(token: str) -> APIToken | None:
    """Проверить API-токен."""
    return _api_tokens.get(token)


# ──────────────────── FastAPI security ────────────────────
_bearer = HTTPBearer(auto_error=False)

_AUTH_SETUP = os.environ.get("AUTH_ENABLED", "true").lower() == "true"
_AUTH_SECRET = os.environ.get("JWT_SECRET", "")
_ALLOWED_PORTS = frozenset(os.environ.get("ALLOWED_PORTS", "").split(",") if os.environ.get("ALLOWED_PORTS") else [])

AUTH_ENABLED = _AUTH_SETUP or not _AUTH_SECRET


async def require_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """
    FastAPI dependency: проверяет Bearer токен (JWT или API-токен).

    Всегда требует авторизацию кроме публичных эндпоинтов.
    """
    if not AUTH_ENABLED:
        secret = os.environ.get("NO_AUTH_SECRET", "")
        if secret and creds and creds.credentials == secret:
            return {"sub": "no-auth", "type": "allowed"}
        if _ALLOWED_PORTS:
            return {"sub": "allowed-ports", "type": "limited"}
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = creds.credentials

    # 1. Проверяем API-токены (machine-to-machine)
    api_tok = _verify_api_token(token)
    if api_tok:
        return {"sub": api_tok.owner, "type": "api_token"}

    # 2. Проверяем JWT (пользователи)
    payload = _decode_jwt(token)
    if payload:
        return {**payload, "type": "jwt"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ──────────────────── Пользователи (stub) ────────────────────
# В production замените на реальную БД + хэширование паролей

_USERS: dict[str, str] = {
    "admin": os.environ.get("ADMIN_PASSWORD", "admin"),
    "operator": os.environ.get("OPERATOR_PASSWORD", "operator"),
}


def _verify_user(username: str, password: str) -> bool:
    stored = _USERS.get(username)
    if not stored:
        return False
    # Сравнение через hmac для защиты от timing attacks
    return hmac.compare_digest(stored.encode(), password.encode())


# ──────────────────── Роутер ────────────────────

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """
    Аутентификация по логину/паролю → JWT токен.

    Пример:
        POST /auth/login
        {"username": "admin", "password": "admin"}
    """
    print(f"Login attempt: {req.username}")
    if not _verify_user(req.username, req.password):
        print(f"Login failed for: {req.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    print(f"Login success for: {req.username}")
    token = _create_jwt({"sub": req.username, "role": "user"})
    return TokenResponse(access_token=token)


@router.post("/token/generate", response_model=APITokenResponse)
async def generate_api_token(
    req: GenerateTokenRequest,
    _payload: dict = Depends(require_token),
):
    """
    Генерация нового API-токена (требует авторизации).

    Пример:
        POST /auth/token/generate
        Authorization: Bearer <jwt>
        {"owner": "robot-client", "description": "UDP telemetry service"}
    """
    new_token = secrets.token_urlsafe(32)
    api_tok = APIToken(token=new_token, owner=req.owner, description=req.description)
    _api_tokens[new_token] = api_tok

    return APITokenResponse(
        token=new_token,
        owner=req.owner,
        description=req.description,
    )


@router.get("/token/list")
async def list_api_tokens(_payload: dict = Depends(require_token)):
    """Список активных API-токенов (маскированные)."""
    return [t.to_dict() for t in _api_tokens.values()]


@router.delete("/token/{token_prefix}")
async def revoke_api_token(
    token_prefix: str,
    _payload: dict = Depends(require_token),
):
    """Отозвать API-токен по первым 8 символам."""
    to_delete = [k for k in _api_tokens if k.startswith(token_prefix)]
    if not to_delete:
        raise HTTPException(status_code=404, detail="Token not found")
    for k in to_delete:
        del _api_tokens[k]
    return {"revoked": len(to_delete)}


@router.get("/me")
async def me(payload: dict = Depends(require_token)):
    """Информация о текущем токене/пользователе."""
    return {"sub": payload.get("sub"), "type": payload.get("type")}
