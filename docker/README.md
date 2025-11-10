# Docker Deployment Guide

## Services Overview

This Docker Compose setup includes 4 services:

1. **cache-updater** - Populates item cache from OSRS Wiki API
2. **backend** - Flask API server (port 5000)
3. **frontend** - Next.js web interface (port 3000)
4. **bot** - Discord bot service

## Startup Order

Services start in the following order with health checks:

1. **cache-updater** starts first and populates the item cache
2. **backend** waits for cache-updater to be healthy, then starts
3. **frontend** waits for backend to be healthy, then starts
4. **bot** waits for backend to be healthy, then starts

## Quick Start

```bash
cd docker
docker-compose up -d --build
```

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

### Frontend
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://backend:5000)

### Backend
- `FLASK_ENV` - Flask environment (production)
- `CONFIG_PATH` - Path to config.json

### Bot
- `BACKEND_URL` - Backend API URL (http://backend:5000)
- `CONFIG_PATH` - Path to config.json

## Troubleshooting

### Frontend not starting
- Check if backend is healthy: `docker-compose ps`
- Check frontend logs: `docker-compose logs frontend`
- Verify NEXT_PUBLIC_API_URL is set correctly

### Backend not starting
- Check if cache-updater completed: `docker-compose logs cache-updater`
- Check backend logs: `docker-compose logs backend`
- Verify config.json exists and is valid

### Services not connecting
- Ensure all services are on the same network: `sniper-network`
- Check service health: `docker-compose ps`
- Verify environment variables are set correctly

