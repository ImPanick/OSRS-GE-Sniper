#!/bin/bash
# Standalone update script for OSRS GE Sniper
# This script pulls the latest code from GitHub and restarts Docker services

set -e

echo "🔄 OSRS GE Sniper - Auto Updater"
echo "=================================="
echo ""

# Check if we're in a git repo
if [ ! -d ".git" ]; then
    echo "❌ Error: Not a git repository"
    echo "Please run this script from the repository root"
    exit 1
fi

# Get current commit
CURRENT_COMMIT=$(git rev-parse HEAD)
echo "📌 Current commit: ${CURRENT_COMMIT:0:8}"
echo ""

# Stash any local changes
echo "📦 Stashing local changes..."
git stash || true
echo ""

# Fetch latest changes
echo "⬇️  Fetching latest changes from GitHub..."
git fetch origin
echo ""

# Check current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "🌿 Current branch: $BRANCH"
echo ""

# Pull latest changes
echo "⬇️  Pulling latest changes..."
git pull origin "$BRANCH"
echo ""

# Get new commit
NEW_COMMIT=$(git rev-parse HEAD)
echo "📌 New commit: ${NEW_COMMIT:0:8}"
echo ""

if [ "$CURRENT_COMMIT" = "$NEW_COMMIT" ]; then
    echo "✅ Already up to date!"
    exit 0
fi

echo "✅ Code updated successfully!"
echo ""

# Check if Docker Compose is available
if command -v docker-compose &> /dev/null || command -v docker &> /dev/null; then
    if [ -f "docker/docker-compose.yml" ]; then
        echo "🐳 Restarting Docker services..."
        cd docker
        if command -v docker-compose &> /dev/null; then
            docker-compose up -d --build
        else
            docker compose up -d --build
        fi
        echo ""
        echo "✅ Docker services restarted!"
    else
        echo "⚠️  docker-compose.yml not found, skipping Docker restart"
    fi
else
    echo "⚠️  Docker not found, skipping Docker restart"
fi

echo ""
echo "🎉 Update complete!"

