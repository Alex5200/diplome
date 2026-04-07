# MuJoCo Robot Simulation Container
# Supports both headless and GUI modes via X11 forwarding

FROM python:3.12-slim-bookworm

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for MuJoCo and GUI
RUN apt-get update && apt-get install -y --no-install-recommends \
    # X11 dependencies for GUI
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libxkbcommon0 \
    libsm6 \
    libice6 \
    libdbus-1-3 \
    # Build dependencies
    build-essential \
    gcc \
    g++ \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/

# Set Python path
ENV PYTHONPATH=/app:/app/src

# Create non-root user for X11 security
RUN useradd -m -u 1000 mujoco && chown -R mujoco:mujoco /app
USER mujoco

# Default command - headless mode
ENTRYPOINT ["python", "-m", "src.mujoco_robot_sim"]
CMD ["--headless"]
