# ST3215 Robot Control - Production Dockerfile
# Multi-stage build for optimized image

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /web

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

COPY pyproject.toml ./
RUN uv sync

COPY --chown=appuser:appuser . .
RUN chown -R appuser:appuser /web

USER appuser

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    AUTH_ENABLED=false \
    MOCK_MODE=false \
    LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/status || exit 1

CMD ["uv", "run", "main.py"]
