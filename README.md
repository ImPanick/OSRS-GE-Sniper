# OSRS GE Sniper Bot

A Discord bot and web dashboard for tracking OSRS Grand Exchange price movements, dumps, spikes, and profitable flips.

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/9a4282c36652471aa002017202d45a3b)](https://app.codacy.com/gh/ImPanick/OSRS-GE-Sniper/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)

## Features

- **Real-time Price Tracking**: Monitors all GE items for dumps, spikes, and flips
- **Discord Notifications**: Per-server channel routing with role pings based on risk/quality
- **Web Dashboard**: View top flips, dumps, spikes, and volume tracker
- **Per-Server Configuration**: Each Discord server can configure channels and roles
- **Server Information Management**: View roles, members, channels, and online count via admin panel
- **Role Assignment**: Assign roles to members directly from the web interface
- **Rich Embeds**: Detailed notifications with item thumbnails, price history, risk metrics, and profit calculations
- **Risk Assessment**: Calculates risk scores, liquidity, and profitability confidence
- **Item Thumbnails**: All notifications include item images from OSRS Wiki
- **Admin Controls**: Ban/remove servers, manage configurations, view server details

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd OSRS-GE-Sniper
   ```

2. **Set up Discord Bot**
   - See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed Discord bot setup instructions
   - Quick steps:
     1. Create Discord application at https://discord.com/developers/applications
     2. Create bot and enable MESSAGE CONTENT INTENT and SERVER MEMBERS INTENT
     3. Copy bot token and add to `config.json`
     4. Generate invite link with `bot` and `applications.commands` scopes
     5. Invite bot to your server with required permissions

3. **Configure settings**
   ```bash
   cp config.json.example config.json
   # Edit config.json with your Discord token, webhook, etc.
   ```

4. **Deploy with Docker (Single Command)**
   ```bash
   cd docker
   docker compose up -d --build
   ```
   
   This single command will:
   - Build all services (cache-updater, backend, frontend, bot)
   - Start all services in the correct order
   - Set up networking and health checks
   - Make everything production-ready
   
   **Note:** The first build may take 5-10 minutes as it downloads dependencies. Subsequent builds are much faster.

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

## Discord Bot Setup

For complete step-by-step instructions, see [DEPLOYMENT.md](DEPLOYMENT.md#discord-bot-setup).

### Quick Setup Guide

1. **Create Discord Application**
   - Go to https://discord.com/developers/applications
   - Click "New Application"
   - Name your application

2. **Create Bot**
   - Go to "Bot" section
   - Click "Add Bot"
   - Enable **MESSAGE CONTENT INTENT** and **SERVER MEMBERS INTENT**
   - Copy the bot token

3. **Generate Invite Link**
   - Get your Application ID from "General Information"
   - Use this URL template (replace `YOUR_APPLICATION_ID`):
     ```
     https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=2416267520&scope=bot%20applications.commands
     ```
   - Or use https://discordapi.com/permissions.html for a visual generator
   - **Note:** The bot requires "Manage Roles" permission for role assignment features

4. **Invite Bot**
   - Open the invite URL in your browser
   - Select your server and authorize

5. **Configure Bot Token**
   - Add the bot token to `config.json`:
   ```json
   {
     "discord_token": "YOUR_BOT_TOKEN_HERE",
     ...
   }
   ```

## Configuration

### Config File
Edit `config.json`:
- `discord_token`: Your Discord bot token (from Discord Developer Portal)
- `discord_webhook`: Optional webhook for backend notifications
- `backend_url`: Backend URL (use Proxmox IP for production)
- `admin_key`: Secure random string for admin API access

## Discord Commands

- `/dip` - View top dumps (buy opportunities)
- `/pump` - View top spikes (sell opportunities)
- `/flips [min_gp]` - View top profitable flips
- `/sniper_config` - Open web dashboard for server configuration
- `/watch <item>` - Get DMs when item dumps/pumps
- `/profit <gp>` - Log your flip profit
- `/leaderboard` - View top flippers

## Web Dashboard

- `/dashboard` - Main dashboard with top flips, dumps, spikes
- `/volume_tracker` - All GE items with filtering and sorting
- `/config/<guild_id>` - Per-server configuration with:
  - Server information (roles, members, channels, online count)
  - Role assignment interface (assign roles to members)
  - Channel selection (click to copy channel IDs)
  - Role selection (click to copy role IDs)
  - Bot permission status
- `/admin` - Admin panel (requires admin_key) with:
  - Server management (ban/unban/delete)
  - Auto-updater controls
  - Server list with status

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
