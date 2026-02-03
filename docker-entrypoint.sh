#!/bin/bash
set -e

echo "=== AI Daily Summary - Starting container ==="

# Wait for database to be ready (extra safety beyond healthcheck)
echo "Waiting for database connection..."
until pg_isready -h "${DB_HOST:-postgres}" -p "${DB_PORT:-5432}" -U "${DB_USER:-postgres}" -d "${DB_NAME:-ai_daily}" > /dev/null 2>&1; do
    echo "Database not ready, waiting..."
    sleep 2
done
echo "Database is ready!"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Seed the database with initial data
echo "Seeding database..."
ai-daily seed || echo "Seeding skipped (may already be seeded)"

# Start cron daemon in background
echo "Starting cron daemon..."
cron

# Export environment variables for cron jobs
# Cron runs in a minimal environment, so we need to pass env vars
printenv | grep -E '^(DB_|LLM_|OPENAI_|GMAIL_|RECIPIENTS|OLLAMA_|DATA_DIR|LOGS_DIR|TEMPLATES_DIR|CONFIG_FILE)' > /etc/environment

echo "=== AI Daily Summary - Container ready ==="
echo "Cron jobs scheduled:"
echo "  - ETL: 6:00 AM daily"
echo "  - Newsletter + TTS: 7:30 AM daily"
echo ""
echo "API server starting on port 8000..."

# Keep the container running by starting the API server
exec ai-daily serve
