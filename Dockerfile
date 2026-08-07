# Hugging Face Spaces Optimized Dockerfile for Smart Community Platform
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=7860

# Install system dependencies (libgl1 for OpenCV/YOLOv8, libpq-dev for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user required by Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /home/user/app

# Copy dependency specifications first for Docker caching
COPY --chown=user:user requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Copy application files
COPY --chown=user:user . .

# Expose Hugging Face default port 7860
EXPOSE 7860

# Execute database migrations and launch FastAPI on port 7860
CMD ["sh", "-c", "python scripts/migrate.py && uvicorn backend.main:app --host 0.0.0.0 --port 7860"]
