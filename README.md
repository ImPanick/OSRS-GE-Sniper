# OSRS GE Sniper Bot

A Discord bot and web dashboard for tracking OSRS Grand Exchange price movements, dumps, spikes, and profitable flips.

## Features

- **Real-time Price Tracking**: Monitors all GE items for dumps, spikes, and flips
- **Discord Notifications**: Per-server channel routing with role pings based on risk/quality
- **Web Dashboard**: View top flips, dumps, spikes, and volume tracker
- **Per-Server Configuration**: Each Discord server can configure channels and roles
- **Risk Assessment**: Calculates risk scores, liquidity, and profitability confidence
- **Item Thumbnails**: All notifications include item images from OSRS Wiki
- **Admin Controls**: Ban/remove servers, manage configurations

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd OSRS-GE-Sniper
   ```

2. **Configure settings**
   ```bash
   cp config.json.example config.json
   # Edit config.json with your Discord token, webhook, etc.
   ```

3. **Deploy with Docker**
   ```bash
   cd docker
   docker-compose up -d
   ```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

## Configuration

### Discord Bot Setup
1. Create a Discord application at https://discord.com/developers/applications
2. Create a bot and copy the token
3. Enable Privileged Gateway Intents:
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT (if needed)
4. Invite bot with permissions: Send Messages, Embed Links, Use Slash Commands, Mention Roles

### Config File
Edit `config.json`:
- `discord_token`: Your Discord bot token
- `discord_webhook`: Optional webhook for backend notifications
- `backend_url`: Backend URL (use Proxmox IP for production)
- `admin_key`: Secure random string for admin API access

## Discord Commands

- `/dip` - View top dumps (buy opportunities)
- `/pump` - View top spikes (sell opportunities)
- `/flips` - View top profitable flips
- `/sniper_config` - Open web dashboard for server configuration
- `/watch <item>` - Get DMs when item dumps/pumps
- `/profit <gp>` - Log your flip profit
- `/leaderboard` - View top flippers

## Web Dashboard

- `/dashboard` - Main dashboard with top flips, dumps, spikes
- `/volume_tracker` - All GE items with filtering and sorting
- `/config/<guild_id>` - Per-server configuration
- `/admin` - Admin panel (requires admin_key)

## Architecture

- **Backend** (`backend/app.py`): Flask API serving item data and web dashboard
- **Discord Bot** (`discord-bot/bot.py`): Discord bot with slash commands and notifications
- **Cache Updater** (`backend/utils/cache_updater.py`): Updates item cache every 6 hours

## Development

### Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
python app.py

# Bot
cd discord-bot
pip install -r requirements.txt
python bot.py
```

### Docker Development
```bash
cd docker
docker-compose up --build
```

## License

See [LICENSE](LICENSE) file.
