# Docker Deployment Guide

## Services Overview

This Docker Compose setup includes 4 services (project name: `osrs-sniper`):

1. **osrs-sniper-cache-updater** - Populates item cache from OSRS Wiki API
2. **osrs-sniper-backend** - Flask API server (port 5000)
3. **osrs-sniper-frontend** - Next.js web interface (port 3000)
4. **osrs-sniper-bot** - Discord bot service

## Startup Order

Services start in the following order with health checks:

1. **cache-updater** starts first and populates the item cache
2. **backend** waits for cache-updater to be healthy, then starts
3. **frontend** waits for backend to be healthy, then starts
4. **bot** waits for backend to be healthy, then starts

## Quick Start

**IMPORTANT**: Always run `docker-compose` from the `docker/` directory. The paths are configured to work universally from this location.

### Step 1: Initialize config.json

Before starting Docker, ensure `config.json` exists in the repository root. If it doesn't exist, it will be created from `config.json.example`:

**Linux/macOS:**
```bash
cd docker
./init-config.sh
```

**Windows (PowerShell):**
```powershell
cd docker
.\init-config.ps1
```

**Manual:**
```bash
# From repository root
cp config.json.example config.json
# Then edit config.json and set your discord_token and admin_key
```

### Step 2: Start Services

```bash
# Navigate to the docker directory
cd docker

# Start all services
docker-compose up -d --build
```

**Note**: If `config.json` doesn't exist when Docker starts, Docker will create a **directory** instead of mounting the file. Always ensure the file exists before running `docker-compose`.

The docker-compose.yml uses environment variables with sensible defaults that work when run from the `docker/` directory. If you need to use absolute paths or run from a different location, create a `.env` file in the `docker/` directory (see `.env.example`).

## Access Services

- **Frontend Web UI**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **API Health Check**: http://localhost:5000/api/health

## Service Health Checks

All services have health checks configured:
- **cache-updater**: Checks if item_cache.json exists
- **backend**: Checks if API endpoint responds
- **frontend**: Checks if web server responds
- **bot**: No health check (runs continuously)

## View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f frontend
docker-compose logs -f backend
docker-compose logs -f bot
docker-compose logs -f cache-updater

# Or by container name
docker logs -f osrs-sniper-frontend
docker logs -f osrs-sniper-backend
docker logs -f osrs-sniper-bot
docker logs -f osrs-sniper-cache-updater
```

## Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart frontend
docker-compose restart backend
```

## Stop Services

```bash
docker-compose down
```

## Rebuild After Code Changes

```bash
docker-compose up -d --build
```

## Environment Variables

### Path Configuration (docker-compose.yml)

These variables control where Docker looks for files. They default to relative paths (`../`) which work when running from the `docker/` directory:

- `REPO_ROOT` - Repository root directory (default: `..`)
- `CONFIG_FILE` - Path to config.json (default: `${REPO_ROOT}/config.json`)
- `BACKEND_UTILS` - Backend utils directory (default: `${REPO_ROOT}/backend/utils`)
- `BACKEND_SERVER_CONFIGS` - Server configs directory (default: `${REPO_ROOT}/backend/server_configs`)
- `DISCORD_BOT_DATA` - Discord bot data directory (default: `${REPO_ROOT}/discord-bot/data`)

To override these, create a `.env` file in the `docker/` directory (see `.env.example`).

### Service Environment Variables

#### Frontend
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:5000)

#### Backend
- `FLASK_ENV` - Flask environment (production)
- `CONFIG_PATH` - Path to config.json inside container (`/app/config.json`)
- `DB_PATH` - Path to database file (`/app/utils/history.db`)

#### Bot
- `BACKEND_URL` - Backend API URL (http://backend:5000)
- `CONFIG_PATH` - Path to config.json inside container (`/app/config.json`)

## Troubleshooting

### Frontend not starting
- Check if backend is healthy: `docker-compose ps`
- Check frontend logs: `docker-compose logs frontend`
- Verify NEXT_PUBLIC_API_URL is set correctly

### Backend not starting
- Check if cache-updater completed: `docker-compose logs cache-updater`
- Check backend logs: `docker-compose logs backend`
- Verify config.json exists and is valid
- **Path issues**: If you see mount errors, ensure you're running `docker-compose` from the `docker/` directory, or create a `.env` file with absolute paths

### config.json is a directory instead of a file
This happens when Docker tries to mount a file that doesn't exist. To fix:
1. **Stop Docker containers**: `docker-compose down`
2. **Remove the directory**: `rm -rf ../config.json` (Linux/macOS) or `Remove-Item -Recurse -Force ..\config.json` (Windows)
3. **Create the file**: Run `./init-config.sh` (Linux/macOS) or `.\init-config.ps1` (Windows) from the `docker/` directory
4. **Restart**: `docker-compose up -d`

### Services not connecting
- Ensure all services are on the same network: `sniper-network`
- Check service health: `docker-compose ps`
- Verify environment variables are set correctly

