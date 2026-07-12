# AI Daily Summary - Data Platform
# Multi-stage build: Frontend (Node.js) + Backend (Python)

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python application
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY ai_daily/ ./ai_daily/
COPY templates/ ./templates/
COPY config.json ./
COPY alembic.ini ./

# Copy built frontend from first stage
COPY --from=frontend-builder /ai_daily/static ./ai_daily/api/static

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install .

# Headless Chromium for the leaderboard watcher (playwright)
RUN python -m playwright install --with-deps chromium

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose API port
EXPOSE 8000

# Health check to verify API is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]
