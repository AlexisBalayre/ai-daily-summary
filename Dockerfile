# AI Daily Summary - Data Platform
# Python application with cron scheduling for ETL and newsletter generation

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY ai_daily/ ./ai_daily/
COPY lib/ ./lib/
COPY templates/ ./templates/
COPY config.json ./
COPY alembic.ini ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install .

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs

# Set up cron jobs
# ETL at 6:00 AM daily
# Newsletter + TTS at 7:30 AM daily
RUN echo "0 6 * * * cd /app && /usr/local/bin/ai-daily run all >> /app/logs/cron-etl.log 2>&1" > /etc/cron.d/ai-daily && \
    echo "30 7 * * * cd /app && /usr/local/bin/ai-daily run-daily >> /app/logs/cron-daily.log 2>&1" >> /etc/cron.d/ai-daily && \
    echo "" >> /etc/cron.d/ai-daily && \
    chmod 0644 /etc/cron.d/ai-daily && \
    crontab /etc/cron.d/ai-daily

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
