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

### Prerequisites

**None!** The backend uses built-in default configuration and will start successfully without any `config.json` file. Just run docker-compose and everything will be set up automatically.

**Important**: 
- **No `config.json` file is required** - the backend uses sensible defaults
- After services start, visit http://localhost:3000 and use the **Setup page** to configure your Discord bot token and other settings
- The setup page will save your configuration to `config.json` automatically (optional)
- The backend will work perfectly fine even if `config.json` never exists

### Start Services

```bash
# Navigate to the docker directory
cd docker

# Start all services
docker-compose up -d --build
```

**Important**: 
- **No `config.json` file is required** - backend uses built-in defaults
- The backend will start successfully on a fresh clone with zero configuration
- After services start, visit http://localhost:3000 to complete setup via the web UI (optional)
- The setup page will guide you through configuring your Discord bot token and other settings
- Configuration is saved to `config.json` automatically when you use the setup page

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
- `CONFIG_FILE` - Optional path to config.json (not required - backend uses defaults)
- `BACKEND_UTILS` - Backend utils directory (default: `${REPO_ROOT}/backend/utils`)
- `BACKEND_SERVER_CONFIGS` - Server configs directory (default: `${REPO_ROOT}/backend/server_configs`)
- `DISCORD_BOT_DATA` - Discord bot data directory (default: `${REPO_ROOT}/discord-bot/data`)

To override these, create a `.env` file in the `docker/` directory (see `.env.example`).

### Service Environment Variables

#### Frontend
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:5000)

#### Backend
- `FLASK_ENV` - Flask environment (production)
- `CONFIG_PATH` - Optional path to config.json (defaults to `/app/config.default.json` or built-in defaults)
- `DB_PATH` - Path to database file (`/app/utils/history.db`)

#### Bot
- `BACKEND_URL` - Backend API URL (http://backend:5000)
- `CONFIG_PATH` - Optional path to config.json (defaults to `/repo/config.json` if mounted, or built-in defaults)

## Troubleshooting

### Frontend not starting
- Check if backend is healthy: `docker-compose ps`
- Check frontend logs: `docker-compose logs frontend`
- Verify NEXT_PUBLIC_API_URL is set correctly

### Backend not starting
- Check if cache-updater completed: `docker-compose logs cache-updater`
- Check backend logs: `docker-compose logs backend`
- **Note**: `config.json` is NOT required - backend uses built-in defaults
- **Path issues**: If you see mount errors, ensure you're running `docker-compose` from the `docker/` directory, or create a `.env` file with absolute paths

### Config File Issues
- **Missing config.json**: This is normal and expected! The backend uses built-in defaults and will start successfully without `config.json`
- **config.json is a directory**: If this happens:
  1. **Stop Docker containers**: `docker-compose down`
  2. **Remove the directory**: `rm -rf ../config.json` (Linux/macOS) or `Remove-Item -Recurse -Force ..\config.json` (Windows)
  3. **Restart**: `docker-compose up -d`
  4. The backend will work fine without the file - it's optional (entrypoint will create the file automatically)

### Services not connecting
- Ensure all services are on the same network: `sniper-network`
- Check service health: `docker-compose ps`
- Verify environment variables are set correctly

