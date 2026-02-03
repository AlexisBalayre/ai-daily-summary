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

# Start orchestrator in background
echo "[$(date -Iseconds)] Starting orchestrator..."
ai-daily orchestrator start &

echo "=== AI Daily Summary - Container ready ==="
echo "[$(date -Iseconds)] Orchestrator running in background with scheduled tasks"
echo "[$(date -Iseconds)] API server starting on port 8000..."

# Start API server (keeps container running)
exec uvicorn ai_daily.api.server:app --host 0.0.0.0 --port 8000
