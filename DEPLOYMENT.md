# OSRS GE Sniper - Deployment Guide

## Prerequisites
- Docker & Docker Compose installed
- Proxmox VM with Docker support
- Discord Bot Token
- Discord Webhook URL (optional)

## Quick Start

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd OSRS-GE-Sniper
```

### 2. Configure Settings
Create `config.json` in the root directory (copy from `config.json.example`):
```json
{
  "discord_webhook": "https://discord.com/api/webhooks/YOUR_WEBHOOK",
  "discord_token": "YOUR_BOT_TOKEN",
  "backend_url": "http://YOUR_PROXMOX_IP:5000",
  "alert_channel_id": 123456789012345678,
  "admin_key": "GENERATE_A_SECURE_RANDOM_STRING",
  "thresholds": {
    "margin_min": 2000000,
    "dump_drop_pct": 18,
    "spike_rise_pct": 20,
    "min_volume": 400
  }
}
```

### 3. Deploy with Docker Compose
```bash
cd docker
docker-compose up -d
```

### 4. Verify Services
```bash
docker-compose ps
docker-compose logs -f
```

## Proxmox Deployment

### 1. Create LXC Container or VM
- Recommended: LXC with Docker support
- Allocate: 2GB RAM, 2 CPU cores, 10GB storage

### 2. Install Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

### 3. Install Docker Compose
```bash
apt-get update
apt-get install docker-compose-plugin
```

### 4. Clone and Deploy
```bash
git clone <your-repo-url>
cd OSRS-GE-Sniper
# Configure config.json
cd docker
docker-compose up -d
```

## Configuration

### Backend URL
Update `backend_url` in `config.json` to your Proxmox IP:
```json
"backend_url": "http://192.168.1.100:5000"
```

### Firewall Rules
Open port 5000 on Proxmox:
```bash
ufw allow 5000/tcp
```

### Persistent Data
Data is stored in:
- `backend/server_configs/` - Per-server configurations
- `backend/utils/item_cache.json` - Item cache
- `discord-bot/data/` - Bot data (watchlists, stats)

## Discord Bot Setup

1. Create Discord Application: https://discord.com/developers/applications
2. Create Bot and copy token
3. Enable Privileged Gateway Intents:
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT (if needed)
4. Invite bot with permissions:
   - Send Messages
   - Embed Links
   - Use Slash Commands
   - Mention Roles

## Monitoring

### View Logs
```bash
docker-compose logs -f backend
docker-compose logs -f bot
docker-compose logs -f cache-updater
```

### Restart Services
```bash
docker-compose restart backend
docker-compose restart bot
```

### Update Code
```bash
git pull
cd docker
docker-compose up -d --build
```

## Troubleshooting

### Bot Not Connecting
- Check Discord token in config.json
- Verify bot has correct permissions
- Check firewall rules

### Backend Not Accessible
- Verify port 5000 is open
- Check backend_url in config.json
- Review backend logs: `docker-compose logs backend`

### Config Path Errors
- Ensure config.json exists in root directory
- Check file permissions
- Verify volume mounts in docker-compose.yml

