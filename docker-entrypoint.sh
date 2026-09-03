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

# First boot without a mounted config.json: start from the example sources/whitelist
if [ ! -s /app/config.json ]; then
    echo "[$(date -Iseconds)] No config.json mounted, using config.example.json"
    cp /app/config.example.json /app/config.json
fi

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

# Run the scheduler and the API side by side; if either dies the container exits so
# Docker's restart policy brings both back instead of leaving a half-alive service.
echo "[$(date -Iseconds)] Starting orchestrator..."
ai-daily orchestrator start &
ORCHESTRATOR_PID=$!

echo "[$(date -Iseconds)] API server starting on port 8000..."
uvicorn ai_daily.api.server:app --host 0.0.0.0 --port 8000 &
API_PID=$!

trap 'kill "$ORCHESTRATOR_PID" "$API_PID" 2>/dev/null' TERM INT
echo "=== AI Daily Summary - Container ready ==="

set +e
wait -n "$ORCHESTRATOR_PID" "$API_PID"
STATUS=$?
echo "[$(date -Iseconds)] A service exited with status $STATUS; stopping container"
kill "$ORCHESTRATOR_PID" "$API_PID" 2>/dev/null
wait
exit "$STATUS"
