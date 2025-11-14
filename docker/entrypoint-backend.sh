#!/bin/bash
set -e

# Backend now uses robust config loading with defaults
# No need to create config.json - backend will use /app/config.default.json or hardcoded defaults
# This entrypoint is kept for backward compatibility but does not require config.json to exist

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

