# OSRS GE Sniper - Complete Architecture Guide

## 🏗️ System Overview

This is a **multi-tenant Discord bot system** where:
- **You host ONE bot** that connects to Discord
- **Users invite your bot** to their Discord servers
- **Each server has its own configuration** stored on your backend
- **Users configure their server** via your web UI using their server's admin token
- **The bot polls your backend** every 20 seconds for updates
- **The bot routes notifications** to each server's configured channels with role pings

## 🔄 How It Works

### 1. **Bot Token Setup (ONE TIME - You Only)**

You need **ONE bot token** from Discord Developer Portal. This is YOUR bot that will be invited to multiple servers.

**Steps:**
1. Create ONE Discord application at https://discord.com/developers/applications
2. Create ONE bot in that application
3. Get the bot token
4. Put it in `config.json` at the project root:
   ```json
   {
     "discord_token": "YOUR_BOT_TOKEN_HERE",
     "backend_url": "http://backend:5000",
     ...
   }
   ```

**This is the ONLY token you need.** Once set, you never touch it again (unless you reset it).

### 2. **Users Invite Your Bot**

Users generate an invite link using YOUR Application ID:

```
https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&permissions=2416267520&scope=bot%20applications.commands
```

When they invite it:
- Bot joins their server
- Bot can see the server (guild_id)
- Bot can send messages to configured channels
- Bot can ping configured roles
- Bot can assign/remove roles (via admin panel)

### 3. **Per-Server Configuration System**

Each Discord server (guild) has its own configuration file:
- **Location:** `backend/server_configs/{guild_id}.json`
- **Created automatically** when a server first uses the bot
- **Stored on YOUR backend** (not in Discord)

**Configuration includes:**
- **Channels:** Where to send different types of alerts
  - `cheap_flips`, `medium_flips`, `expensive_flips`, etc.
- **Roles:** Which roles to ping for different risk/quality levels
  - `risk_low`, `risk_medium`, `risk_high`, `quality_nuclear`, etc.
- **Tier Settings:** Per-tier Discord role mentions and enable/disable flags
  - Configure role mentions for each tier (Iron through Diamond)
  - Enable/disable alerts per tier
  - Set minimum tier threshold for automatic alerts
- **Thresholds:** Custom filtering per server

### 4. **Web UI Configuration**

Users access: `http://your-server:3000/config/{guild_id}?token={admin_token}`

**How admin tokens work:**
- Each server gets a unique admin token (stored in their config)
- Users get this token when they first set up the bot
- They use it to access their server's configuration page
- The web UI reads/writes to `backend/server_configs/{guild_id}.json`

**What users can configure:**
- Which channels receive which types of alerts
- Which roles get pinged for different risk levels
- **Tier system settings:**
  - Discord role mentions per tier (Iron, Copper, Bronze, Silver, Gold, Platinum, Ruby, Sapphire, Emerald, Diamond)
  - Enable/disable alerts per tier
  - Minimum tier threshold for automatic alerts
- Quality thresholds (nuclear dumps, god-tier, etc.)
- Enable/disable notifications

### 5. **Data Flow**

```
┌─────────────────┐
│  OSRS Wiki API  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Your Backend   │  ← Polls OSRS API, calculates dumps/spikes/flips
│  (Flask API)    │  ← Stores per-server configs in server_configs/
└────────┬────────┘
         │
         │ (Poll every 20 seconds)
         ▼
┌─────────────────┐
│  Discord Bot    │  ← Reads dumps/spikes/flips from backend
│  (Your Bot)     │  ← Gets each server's config from backend
└────────┬────────┘
         │
         │ (Routes to configured channels with role pings)
         ▼
┌─────────────────┐
│  User Servers   │  ← Each server gets notifications based on their config
│  (Discord)      │
└─────────────────┘
```

### 6. **Tier System**

The tier system automatically categorizes dump opportunities based on quality scores (0-100):

**Tier Structure:**
- **Metal Tiers:** Iron (0-10), Copper (11-20), Bronze (21-30), Silver (31-40), Gold (41-50), Platinum (51-60)
- **Gem Tiers:** Ruby (61-70), Sapphire (71-80), Emerald (81-90), Diamond (91-100)

**How It Works:**
1. **Dump Engine** analyzes price data and calculates quality scores
2. **Tier Assignment** automatically assigns items to tiers based on score
3. **Per-Server Configuration** allows each server to:
   - Set Discord role mentions per tier
   - Enable/disable alerts per tier
   - Set minimum tier threshold (only tiers at or above threshold trigger alerts)
4. **Database Storage** stores tier definitions and guild tier settings in SQLite

**Tier Configuration:**
- Tier definitions stored in `tiers` table (score ranges, emoji, group)
- Guild tier settings stored in `guild_tier_settings` table (role_id, enabled per tier)
- Guild config stores `min_tier_name` (minimum tier for alerts)

### 7. **Notification Routing**

When the bot finds a dump/spike/flip:

1. **Bot polls backend** → Gets list of items with tier information
2. **For each item:**
   - Bot gets list of all servers it's in
   - For each server:
     - Fetches that server's config from backend API (including tier settings)
     - Checks if item's tier meets minimum tier threshold
     - Determines which channel to use (based on item type/price)
     - Determines which roles to ping (based on tier settings or risk/quality)
     - Sends embed to that channel with tier-based role mentions

**Example:**
- Item: "Dragon bones" - 15% dump, Gold tier (score 45), low risk, high volume
- Server A config: `cheap_flips` channel, Gold tier → ping `@GoldAlerts` role, min_tier = Silver
- Server B config: `medium_flips` channel, Gold tier → ping `@Deals` role, min_tier = Platinum
- Bot sends to Server A's `cheap_flips` with `@GoldAlerts` ping (Gold ≥ Silver threshold)
- Bot skips Server B (Gold < Platinum threshold)

## 🔧 Setup Process

### For You (Host):

1. **Get Bot Token** (one time)
   - Discord Developer Portal → Your Application → Bot → Copy Token
   - Put in root `config.json`

2. **Get Application ID** (for invite link)
   - Discord Developer Portal → Your Application → General Information
   - Use it to generate invite URL

3. **Deploy Everything**
   ```bash
   cd docker
   docker compose up -d --build
   ```

4. **Share Invite Link**
   - Give users the invite URL with your Application ID
   - They invite your bot to their servers

### For Users:

1. **Invite Bot**
   - Use the invite link you provide
   - Bot joins their server

2. **Get Admin Token**
   - Use `/sniper_config` command in Discord
   - Or access `/config/{guild_id}` (they need to know their guild_id)

3. **Configure Server**
   - Go to `http://your-server:3000/config/{guild_id}?token={admin_token}`
   - Set channels and roles
   - Save configuration

4. **Receive Notifications**
   - Bot automatically sends alerts to configured channels
   - Role pings happen based on risk/quality

## 🔐 Security Model

### Bot Token (Your Secret)
- **ONE token** for your bot
- Stored in root `config.json`
- **NEVER** shared with users
- If exposed, reset it in Discord Developer Portal

### Admin Tokens (Per Server)
- **Unique token per server**
- Generated when server first configures
- Stored in `backend/server_configs/{guild_id}.json`
- Users need this to access their server's config page
- Can be regenerated if needed

### Access Control
- Backend API checks `X-Admin-Key` header for admin endpoints
- Per-server configs are isolated by `guild_id`
- Users can only access their own server's config with correct token

## 📁 File Structure

```
OSRS-GE-Sniper/
├── config.json                    ← YOUR bot token (one time setup)
├── backend/
│   ├── app.py                     ← Flask API (JSON endpoints only, no HTML/UI)
│   ├── routes_*.py                ← API route modules (JSON-only)
│   │   ├── routes_api_dumps.py    ← Dump API with tier filtering
│   │   ├── routes_admin.py        ← Admin API including tier management
│   │   └── ...
│   ├── utils/
│   │   ├── dump_engine.py         ← Dump analysis and tier assignment
│   │   ├── database.py            ← Database with tier tables
│   │   └── ...
│   ├── server_configs/            ← Per-server configs (auto-created)
│   │   ├── 123456789.json         ← Server A's config
│   │   ├── 987654321.json         ← Server B's config
│   │   └── ...
│   └── config_manager.py          ← Manages per-server configs
├── discord-bot/
│   ├── bot.py                     ← Your bot (polls backend, routes tiered notifications)
│   └── utils/
│       └── notification_router.py ← Routes alerts to servers with tier support
└── frontend/
    ├── app/                        ← Next.js pages (ALL user-facing UI)
    │   ├── dashboard/              ← Dashboard page with tier filters
    │   ├── config/[guildId]/      ← Server configuration UI with tier settings
    │   ├── admin/                  ← Admin panel with tier management
    │   └── ...
    └── components/                ← React components
```

**Architecture Note:** The Flask backend is strictly API-only. It provides JSON endpoints for data and configuration. All HTML pages, dashboards, forms, and user interfaces are implemented in the Next.js frontend. Do NOT add HTML/Jinja/HTMX templates to the backend.

## 🚀 Current Status

**What's Working:**
- ✅ Multi-tenant architecture (per-server configs)
- ✅ Backend API serving data and configs
- ✅ Tier system with 10-tier quality scoring (Iron → Diamond)
- ✅ Tier-based notification routing with per-server tier settings
- ✅ Advanced API filtering (tier, group, special flags)
- ✅ Web UI for configuration including tier settings
- ✅ Role ping system based on tier/quality
- ✅ Dashboard tier and group filters

**What Needs Fixing:**
- ❌ Bot token in `config.json` - needs to be valid
- ❌ Backend URL should be `http://backend:5000` for Docker

## 🎯 Next Steps

1. **Fix Bot Token:**
   - Reset token in Discord Developer Portal
   - Update root `config.json`
   - Restart bot: `docker compose restart bot`

2. **Fix Backend URL:**
   - Change `backend_url` in `config.json` to `http://backend:5000`

3. **Test:**
   - Invite bot to a test server
   - Use `/sniper_config` to get config URL
   - Configure channels and roles
   - Wait for alerts!

## 💡 Key Points

- **ONE bot token** for you (host)
- **Multiple servers** can invite your bot
- **Each server** has its own config (channels, roles)
- **Users configure** via web UI with their admin token
- **Bot polls backend** every 20 seconds
- **Bot routes** notifications based on each server's config

This is a **hosted service model** - you run everything, users just invite and configure!

