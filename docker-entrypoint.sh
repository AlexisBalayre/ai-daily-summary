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

# Pull Ollama models if using Ollama provider
if [ "${LLM_PROVIDER:-ollama}" = "ollama" ]; then
    OLLAMA_URL="${OLLAMA_HOST:-http://ollama:11434}"
    echo "[$(date -Iseconds)] Waiting for Ollama service at ${OLLAMA_URL}..."

    # Wait for Ollama to be ready
    max_retries=30
    retry_count=0
    until curl -s "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; do
        retry_count=$((retry_count + 1))
        if [ $retry_count -ge $max_retries ]; then
            echo "[$(date -Iseconds)] WARNING: Ollama service not available after ${max_retries} attempts. Continuing without model pull..."
            break
        fi
        echo "[$(date -Iseconds)] Ollama not ready (attempt ${retry_count}/${max_retries}), waiting..."
        sleep 5
    done

    if curl -s "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        echo "[$(date -Iseconds)] Ollama is ready!"

        # Pull LLM model
        LLM_MODEL_NAME="${LLM_MODEL:-llama3.2}"
        echo "[$(date -Iseconds)] Pulling LLM model: ${LLM_MODEL_NAME}..."
        if curl -s -X POST "${OLLAMA_URL}/api/pull" -d "{\"name\": \"${LLM_MODEL_NAME}\"}" > /dev/null 2>&1; then
            echo "[$(date -Iseconds)] LLM model ${LLM_MODEL_NAME} pulled successfully (or already exists)"
        else
            echo "[$(date -Iseconds)] WARNING: Failed to pull LLM model ${LLM_MODEL_NAME}"
        fi

        # Pull embedding model
        EMBEDDING_MODEL_NAME="${EMBEDDING_MODEL:-nomic-embed-text}"
        echo "[$(date -Iseconds)] Pulling embedding model: ${EMBEDDING_MODEL_NAME}..."
        if curl -s -X POST "${OLLAMA_URL}/api/pull" -d "{\"name\": \"${EMBEDDING_MODEL_NAME}\"}" > /dev/null 2>&1; then
            echo "[$(date -Iseconds)] Embedding model ${EMBEDDING_MODEL_NAME} pulled successfully (or already exists)"
        else
            echo "[$(date -Iseconds)] WARNING: Failed to pull embedding model ${EMBEDDING_MODEL_NAME}"
        fi

        echo "[$(date -Iseconds)] Ollama models ready!"
    fi
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
