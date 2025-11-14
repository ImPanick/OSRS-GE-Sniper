#!/bin/sh
set -e

# Get config path from environment or use default
# In Docker, config.json is in /repo (mounted repo root)
CONFIG_PATH="${CONFIG_PATH:-/repo/config.json}"

# Create config.json in repo root if it doesn't exist and /repo is writable
# This is optional - bot.py will use defaults if config doesn't exist
if [ ! -f "$CONFIG_PATH" ] && [ -d "/repo" ] && [ -w "/repo" ]; then
    # Try to find config.json.example in repo
    EXAMPLE_PATHS="/repo/config.json.example /app/config.json.example"
    EXAMPLE_FOUND=false
    
    for example_path in $EXAMPLE_PATHS; do
        if [ -f "$example_path" ]; then
            echo "[ENTRYPOINT] Creating config.json from $example_path"
            cp "$example_path" "$CONFIG_PATH" 2>/dev/null && EXAMPLE_FOUND=true && break || true
        fi
    done
    
    # If no example found, create minimal config
    if [ "$EXAMPLE_FOUND" = false ]; then
        echo "[ENTRYPOINT] Creating minimal config.json"
        cat > "$CONFIG_PATH" << 'EOF'
{
  "discord_token": "YOUR_BOT_TOKEN_HERE",
  "backend_url": "http://backend:5000",
  "admin_key": "CHANGE_THIS_TO_A_SECURE_RANDOM_STRING",
  "discord_webhook": "https://discord.com/api/webhooks/YOUR_WEBHOOK_HERE",
  "thresholds": {
    "margin_min": 100000,
    "dump_drop_pct": 5,
    "spike_rise_pct": 5,
    "min_volume": 100
  }
}
EOF
    fi
    
    if [ -f "$CONFIG_PATH" ]; then
        echo "[ENTRYPOINT] Config file created at $CONFIG_PATH"
    fi
elif [ ! -f "$CONFIG_PATH" ]; then
    echo "[ENTRYPOINT] Config file not found at $CONFIG_PATH (bot will use defaults)"
fi

# Execute the main command
exec "$@"

