# OSRS GE Sniper - Deployment Guide

## Prerequisites
- Docker & Docker Compose installed
- Proxmox VM with Docker support (for production)
- Discord Bot Token
- Discord Webhook URL (optional)

## Discord Bot Setup

### Step 1: Create Discord Application

1. **Go to Discord Developer Portal**
   - Visit: https://discord.com/developers/applications
   - Log in with your Discord account

2. **Create New Application**
   - Click the **"New Application"** button (top right)
   - Enter a name for your application (e.g., "OSRS GE Sniper")
   - Click **"Create"**

3. **Configure Application**
   - In the left sidebar, click **"General Information"**
   - Note your **Application ID** (you'll need this for the bot invite link)
   - Optionally add a description and icon

### Step 2: Create Bot

1. **Navigate to Bot Section**
   - In the left sidebar, click **"Bot"**

2. **Create Bot User**
   - Click **"Add Bot"** (if you haven't already)
   - Click **"Yes, do it!"** to confirm

3. **Configure Bot Settings**
   - **Username**: Set your bot's display name
   - **Icon**: Upload a bot avatar (optional)
   - **Public Bot**: Leave this **OFF** (unchecked) for private use
   - **Requires OAuth2 Code Grant**: Leave this **OFF**

4. **Enable Privileged Gateway Intents**
   - Scroll down to **"Privileged Gateway Intents"**
   - Enable the following intents:
     - ✅ **MESSAGE CONTENT INTENT** (Required for reading message content)
     - ✅ **SERVER MEMBERS INTENT** (Required for role mentions and member access)
   - Click **"Save Changes"**

5. **Copy Bot Token**
   - Under **"Token"**, click **"Reset Token"** (if this is a new bot)
   - Click **"Yes, do it!"** to confirm
   - **IMPORTANT**: Copy the token immediately and save it securely
   - ⚠️ **Never share this token publicly or commit it to git!**
   - If you lose the token, you'll need to reset it

### Step 3: Generate Bot Invite Link

**Note:** Discord removed the OAuth2 URL Generator from their interface. You now need to manually construct the invite URL.

1. **Get Your Application ID**
   - Go to https://discord.com/developers/applications
   - Click on your application (e.g., "OSRS Sniper")
   - In the left sidebar, click **"General Information"**
   - Copy your **Application ID** (it's a long number, like `123456789012345678`)

2. **Construct the Invite URL**
   
   Replace `YOUR_APPLICATION_ID` in this URL with your actual Application ID:
   ```
   https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=2416267520&scope=bot%20applications.commands&integration_type=0
   ```
   
   The `integration_type=0` parameter ensures it's a "Guild Install" (server install), not "User Install" (DM install).
   
   **Example:** If your Application ID is `123456789012345678`, your URL would be:
   ```
   https://discord.com/oauth2/authorize?client_id=123456789012345678&permissions=2416267520&scope=bot%20applications.commands&integration_type=0
   ```

3. **What This URL Includes:**
   - **Scopes:** `bot` and `applications.commands` (for slash commands)
   - **Permissions:** 
     - Send Messages (512)
     - Embed Links (16384)
     - Attach Files (32768)
     - Read Message History (65536)
     - Use Slash Commands (2147483648)
     - Mention Everyone (131072)
     - Use External Emojis (262144)
     - **Manage Roles (268435456)** - Required for role assignment via admin panel
     - **Total Permission Value:** 2416267520
   
   **Why Manage Roles?** The bot needs this permission to assign roles to members when admins use the web interface to manage role assignments for notifications.

4. **Alternative: Use Online Generator**
   
   If you prefer a visual tool, you can use:
   - https://discordapi.com/permissions.html
   - Select your permissions, enter your Application ID, and it will generate the URL for you

### Step 4: Invite Bot to Your Server

1. **Open Invite Link**
   - Paste the invite URL in your browser
   - Select the Discord server you want to add the bot to
   - Click **"Authorize"**
   - Complete any CAPTCHA if prompted

2. **Verify Bot is Online**
   - Go to your Discord server
   - Check the member list - your bot should appear
   - The bot should show as "Online" once it's running

### Step 5: Create Discord Webhook (Optional)

**Note:** Webhooks are **OPTIONAL** and can be created **AFTER** you've invited the bot to your server. You don't need a webhook to invite the bot.

If you want backend notifications sent to a webhook (separate from the bot):

1. **Go to Server Settings**
   - Right-click your Discord server
   - Click **"Server Settings"**

2. **Navigate to Integrations**
   - Click **"Integrations"** in the left sidebar
   - Click **"Webhooks"**
   - Click **"New Webhook"**

3. **Configure Webhook**
   - **Name**: Give it a name (e.g., "OSRS Sniper Alerts")
   - **Channel**: Select the channel for notifications
   - **Avatar**: Upload an icon (optional)
   - Click **"Save Changes"**

4. **Copy Webhook URL**
   - Click **"Copy Webhook URL"**
   - Save this URL securely
   - ⚠️ **Never share this URL publicly or commit it to git!**

### Step 6: Get Channel ID (Optional)

If you need channel IDs for configuration:

1. **Enable Developer Mode**
   - Go to Discord Settings → **Advanced**
   - Enable **"Developer Mode"**

2. **Copy Channel ID**
   - Right-click on any channel
   - Click **"Copy ID"**
   - Use this ID in your configuration
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
  "discord_webhook": "https://discord.com/api/webhooks/YOUR_WEBHOOK_HERE",
  "discord_token": "YOUR_BOT_TOKEN_HERE",
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

**Important Configuration Values:**
- `discord_token`: Paste the bot token from Step 2.5
- `discord_webhook`: Paste the webhook URL from Step 5.4 (or leave as placeholder)
- `backend_url`: Use `http://localhost:5000` for local, or your Proxmox IP for production
- `admin_key`: Generate a secure random string (e.g., use a password generator)

### 3. Deploy with Docker Compose (Single Command)
```bash
cd docker
docker compose up -d --build
```

This **single command** will:
- ✅ Build all Docker images (cache-updater, backend, frontend, bot)
- ✅ Start all services in the correct dependency order
- ✅ Set up networking and health checks automatically
- ✅ Make everything production-ready

**First Build:** May take 5-10 minutes as it downloads dependencies. This is normal.
**Subsequent Builds:** Much faster (30 seconds - 2 minutes) due to Docker layer caching.

### 4. Verify Services (Optional)
```bash
# Check service status
docker compose ps

# View logs (all services)
docker compose logs -f

# View logs for specific service
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f bot
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
# Configure config.json with your Discord token and Proxmox IP
cd docker
docker-compose up -d --build
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

## Discord Bot Commands

Once the bot is running, you can use these slash commands in Discord:

- `/dip` - View top dumps (buy opportunities)
- `/pump` - View top spikes (sell opportunities)
- `/flips [min_gp]` - View top profitable flips
- `/sniper_config` - Open web dashboard for server configuration
- `/watch <item_name>` - Get DMs when item dumps/pumps
- `/unwatch <item_name>` - Stop watching an item
- `/watching` - View your watchlist
- `/profit <gp>` - Log your flip profit
- `/leaderboard` - View top flippers

## Web Dashboard

- `/dashboard` - Main dashboard with top flips, dumps, spikes
- `/volume_tracker` - All GE items with filtering and sorting
- `/config/<guild_id>` - Per-server configuration
- `/admin` - Admin panel (requires admin_key)

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
- **Check Discord token in config.json**
  - Verify the token is correct (no extra spaces)
  - Make sure you copied the full token
  - If token was leaked, reset it in Discord Developer Portal

- **Verify bot has correct permissions**
  - Check bot permissions in server settings
  - Ensure bot has "Send Messages" and "Use Slash Commands" permissions

- **Check Gateway Intents**
  - Verify MESSAGE CONTENT INTENT is enabled in Discord Developer Portal
  - Restart the bot after enabling intents

- **Check firewall rules**
  - Ensure bot can connect to Discord API (port 443)

### Backend Not Accessible
- Verify port 5000 is open
- Check backend_url in config.json
- Review backend logs: `docker-compose logs backend`
- Ensure backend service is running: `docker-compose ps`

### Config Path Errors
- Ensure config.json exists in root directory
- Check file permissions
- Verify volume mounts in docker-compose.yml

### Bot Commands Not Appearing
- Slash commands can take up to 1 hour to sync globally
- Try restarting Discord client
- Verify bot has "applications.commands" scope in invite link
- Check bot logs for registration errors

### Role Pings Not Working
- Verify bot has "Mention Everyone" permission
- Check role configuration in web dashboard
- Ensure roles exist in the server
- Verify role IDs or names are correct in configuration

## Security Best Practices

1. **Never commit sensitive data**
   - Add `config.json` to `.gitignore`
   - Use `config.json.example` as a template

2. **Protect your bot token**
   - Never share the token publicly
   - Reset token if it's accidentally exposed
   - Use environment variables in production (optional)

3. **Secure admin panel**
   - Use a strong, random `admin_key`
   - Don't share admin_key with unauthorized users
   - Use HTTPS in production

4. **Limit bot permissions**
   - Only grant necessary permissions
   - Don't give Administrator permission unless needed
   - Review permissions regularly

## Additional Resources

- Discord Developer Portal: https://discord.com/developers/applications
- Discord.py Documentation: https://discordpy.readthedocs.io/
- Discord API Documentation: https://discord.com/developers/docs/
