#!/bin/sh
set -e

# Backend now uses robust config loading with defaults
# No need to create config.json - backend will use /app/config.default.json or hardcoded defaults
# This entrypoint is kept for backward compatibility but does not require config.json to exist

# Wait for PostgreSQL if DB_URL is set to Postgres
if [ -n "$DB_URL" ] && echo "$DB_URL" | grep -q "postgres"; then
    echo "[ENTRYPOINT] Waiting for PostgreSQL to be ready..."
    
    # Extract host and port from DB_URL
    DB_HOST=$(echo "$DB_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo "$DB_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    
    if [ -z "$DB_HOST" ]; then
        DB_HOST="postgres"
    fi
    if [ -z "$DB_PORT" ]; then
        DB_PORT="5432"
    fi
    
    # Wait for Postgres to be ready (max 60 seconds)
    MAX_ATTEMPTS=60
    ATTEMPT=0
    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
            echo "[ENTRYPOINT] PostgreSQL is ready!"
            break
        fi
        ATTEMPT=$((ATTEMPT + 1))
        echo "[ENTRYPOINT] Waiting for PostgreSQL... ($ATTEMPT/$MAX_ATTEMPTS)"
        sleep 1
    done
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo "[ENTRYPOINT] WARNING: PostgreSQL may not be ready, continuing anyway..."
    fi
fi

# Log config status
if [ -n "$CONFIG_PATH" ]; then
    echo "[ENTRYPOINT] CONFIG_PATH environment variable set to: $CONFIG_PATH"
else
    echo "[ENTRYPOINT] CONFIG_PATH not set - backend will use default configuration"
fi

# Optional: Try to create config.json in /repo if it's writable (for advanced users)
# This is NOT required - backend works fine without it
if [ -d "/repo" ] && [ -w "/repo" ]; then
    REPO_CONFIG="/repo/config.json"
    if [ ! -f "$REPO_CONFIG" ]; then
        # Try to copy from example if available
        if [ -f "/app/config.default.json" ]; then
            echo "[ENTRYPOINT] Copying default config to /repo/config.json (optional)"
            cp /app/config.default.json "$REPO_CONFIG" 2>/dev/null || true
        elif [ -f "/repo/config.json.example" ]; then
            echo "[ENTRYPOINT] Copying config.json.example to /repo/config.json (optional)"
            cp /repo/config.json.example "$REPO_CONFIG" 2>/dev/null || true
        fi
    fi
fi

# Execute the main command
exec "$@"

