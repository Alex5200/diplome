# ST3215 Robot Control - Production Dockerfile

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

WORKDIR /app
COPY --chown=appuser:appuser web/ ./web/
RUN pip install --no-cache-dir -e ./web

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8000 \
    AUTH_ENABLED=true \
    MOCK_MODE=false \
    LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:8000/api/status || exit 1

CMD ["python", "web/main.py"]
