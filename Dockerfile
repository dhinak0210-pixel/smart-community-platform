# Optimized Lightweight Dockerfile for Render Free Tier
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=10000 \
    ML_MODE=lightweight

# Install essential system dependencies (libpq-dev for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /home/user/app

# Copy dependency specifications first for Docker caching
COPY --chown=user:user requirements-free.txt .

# Install Python packages (Lightweight, ~200MB total)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-free.txt

# Copy application files
COPY --chown=user:user . .

# Run lightweight model download
RUN python scripts/download_models_lite.py

EXPOSE 10000

# Execute database migrations and launch FastAPI on $PORT
CMD ["sh", "-c", "python scripts/migrate.py && uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 1"]

