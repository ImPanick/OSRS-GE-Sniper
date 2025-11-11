# Quick Start Guide - Host Setup

## 🎯 What You're Building

A **hosted Discord bot service** where:
- You run ONE bot that connects to Discord
- Users invite YOUR bot to their servers
- Each server configures channels/roles via your web UI
- Bot sends alerts to each server based on their config

## ⚡ 5-Minute Setup

### Step 1: Get Your Bot Token (One Time)

1. Go to https://discord.com/developers/applications
2. Create/Select your application
3. Go to **Bot** section
4. Click **Reset Token** → Copy it
5. **Enable these intents:**
   - ✅ MESSAGE CONTENT INTENT
   - ✅ SERVER MEMBERS INTENT

### Step 2: Get Your Application ID

1. In Discord Developer Portal → **General Information**
2. Copy your **Application ID** (you'll need this for invite links)

### Step 3: Configure config.json

Edit `config.json` in the project root:

```json
{
  "discord_token": "YOUR_BOT_TOKEN_FROM_STEP_1",
  "backend_url": "http://backend:5000",
  "admin_key": "GENERATE_A_RANDOM_STRING_HERE",
  "discord_webhook": "OPTIONAL_WEBHOOK_URL",
  "alert_channel_id": 123456789012345678,
  "thresholds": {
    "margin_min": 2000000,
    "dump_drop_pct": 18,
    "spike_rise_pct": 20,
    "min_volume": 400
  }
}
```

**Important:**
- `discord_token`: Your bot token from Step 1
- `backend_url`: Keep as `http://backend:5000` for Docker
- `admin_key`: Generate a random string (for your admin panel)

### Step 4: Deploy

```bash
cd docker
docker compose up -d --build
```

### Step 5: Verify

```bash
# Check all services are running
docker compose ps

# Check bot logs (should show "ONLINE")
docker compose logs bot

# Check backend logs
docker compose logs backend
```

## 🔗 Creating Invite Links for Users

Generate invite URL using your Application ID:

```
https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=2416267520&scope=bot%20applications.commands
```

Replace `YOUR_APPLICATION_ID` with your actual Application ID.

**Required Permissions:**
- Send Messages, Embed Links, Attach Files, Read Message History
- Use Slash Commands, Mention Everyone, Use External Emojis
- **Manage Roles** (required for role assignment via admin panel)

**Total Permission Value:** 2416267520

**Share this link with users** - they use it to invite your bot to their servers.

## 🎮 How Users Use It

1. **User invites your bot** using the invite link
2. **User runs `/sniper_config`** in their Discord server
3. **Bot responds with a config URL** like:
   ```
   http://your-server:3000/config/123456789?token=abc123
   ```
4. **User opens that URL** in browser
5. **User configures:**
   - Which channels get which alerts
   - Which roles get pinged for different risk levels
6. **Bot automatically sends alerts** based on their config

## 🔍 Troubleshooting

### Bot Won't Connect

**Check token:**
```bash
docker compose logs bot | grep -i token
```

**Common issues:**
- Token was reset → Get new token from Discord Developer Portal
- Token has spaces → Make sure no extra spaces in config.json
- Wrong token type → Must be Bot Token, not Client Secret

**Fix:**
1. Reset token in Discord Developer Portal
2. Update `config.json`
3. Restart: `docker compose restart bot`

### Backend Not Responding

```bash
docker compose logs backend
docker compose ps  # Check if backend is healthy
```

### Bot Not Sending Notifications

1. Check if bot is in the server: Look for bot in member list
2. Check server config exists: `ls backend/server_configs/`
3. Check bot logs: `docker compose logs bot`
4. Verify channels/roles are configured in web UI

## 📊 Monitoring

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f bot
docker compose logs -f backend
docker compose logs -f frontend

# Check service status
docker compose ps
```

## 🔐 Security Notes

1. **Never commit `config.json`** to git (it's in `.gitignore`)
2. **Reset bot token** if it's ever exposed
3. **Use strong `admin_key`** for admin panel
4. **Limit admin panel access** (currently LAN-only by default)

## 🎉 You're Done!

Once the bot shows "ONLINE" in logs:
- ✅ Bot is connected to Discord
- ✅ Backend is serving data
- ✅ Users can invite your bot
- ✅ Users can configure their servers
- ✅ Bot will send alerts automatically

**The bot polls your backend every 20 seconds** and routes notifications to each server based on their configuration!

