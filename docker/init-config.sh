#!/bin/bash
# Initialize config.json from config.json.example if it doesn't exist

set -e

# Get the repository root (parent of docker/ directory)
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CONFIG_FILE="${REPO_ROOT}/config.json"
CONFIG_EXAMPLE="${REPO_ROOT}/config.json.example"

if [ ! -f "$CONFIG_FILE" ]; then
    if [ -f "$CONFIG_EXAMPLE" ]; then
        echo "📋 config.json not found. Copying from config.json.example..."
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
        echo "✅ Created config.json from config.json.example"
        echo "⚠️  Please edit config.json and set your discord_token and admin_key before starting services."
    else
        echo "❌ Error: config.json.example not found at $CONFIG_EXAMPLE"
        exit 1
    fi
else
    echo "✅ config.json already exists"
fi

