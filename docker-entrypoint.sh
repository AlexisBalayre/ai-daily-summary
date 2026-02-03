#!/bin/bash
set -e

echo "=== AI Daily Summary - Starting container ==="
echo "[$(date -Iseconds)] Container initialization started"

# Wait for database to be ready (extra safety beyond healthcheck)
echo "[$(date -Iseconds)] Waiting for database connection..."
until pg_isready -h "${DB_HOST:-postgres}" -p "${DB_PORT:-5432}" -U "${DB_USER:-postgres}" -d "${DB_NAME:-ai_daily}" > /dev/null 2>&1; do
    echo "[$(date -Iseconds)] Database not ready, waiting..."
    sleep 2
done
echo "[$(date -Iseconds)] Database is ready!"

# Run database migrations
echo "[$(date -Iseconds)] Running database migrations..."
if ! alembic upgrade head; then
    echo "[$(date -Iseconds)] ERROR: Database migrations failed!"
    exit 1
fi
echo "[$(date -Iseconds)] Database migrations completed successfully"

# Seed the database with initial data
echo "[$(date -Iseconds)] Seeding database..."
ai-daily seed || echo "[$(date -Iseconds)] Seeding skipped (may already be seeded)"

# Start cron daemon in background
echo "[$(date -Iseconds)] Starting cron daemon..."
cron

# Export environment variables for cron jobs
# Cron runs in a minimal environment, so we need to pass env vars
printenv | grep -E '^(DB_|LLM_|OPENAI_|GMAIL_|RECIPIENTS|OLLAMA_|DATA_DIR|LOGS_DIR|TEMPLATES_DIR|CONFIG_FILE)' > /etc/environment
# Secure the environment file (contains sensitive credentials)
chmod 0600 /etc/environment
echo "[$(date -Iseconds)] Environment variables exported for cron jobs"

echo "=== AI Daily Summary - Container ready ==="
echo "[$(date -Iseconds)] Cron jobs scheduled:"
echo "  - ETL: 6:00 AM daily"
echo "  - Newsletter + TTS: 7:30 AM daily"
echo ""
echo "[$(date -Iseconds)] API server starting on port 8000..."

# Keep the container running by starting the API server
exec ai-daily serve
