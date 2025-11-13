# Config.json Validation

## Required Fields by System

### Backend API (Can start without these, but functionality limited)

**Optional but Recommended:**
- `admin_key` - Auto-generated if missing or placeholder. Required for admin endpoints.
- `thresholds` - Has defaults if missing:
  - `margin_min`: 100000 (default)
  - `dump_drop_pct`: 5 (default)
  - `spike_rise_pct`: 5 (default)
  - `min_volume`: 100 (default)

**Optional:**
- `discord_webhook` - Used for notifications in background_tasks.py
- `discord_token` - Not used by backend (only by bot)

### Discord Bot (REQUIRED to start)

**Required:**
- `discord_token` - Bot will exit with error if missing or placeholder
- `backend_url` - Used to connect to backend API (default: `http://backend:5000` for Docker)

**Optional:**
- `discord_webhook` - Used for some notification features
- `admin_key` - Not used by bot

### Worker Service

Uses same config as backend. No additional requirements.

## Field Usage Summary

| Field | Backend | Bot | Worker | Required? |
|-------|---------|-----|--------|-----------|
| `discord_token` | ❌ | ✅ | ❌ | Bot: YES |
| `backend_url` | ❌ | ✅ | ❌ | Bot: YES |
| `admin_key` | ✅ | ❌ | ❌ | Backend: Auto-gen if missing |
| `discord_webhook` | ✅ | ✅ | ❌ | Optional |
| `thresholds` | ✅ | ❌ | ✅ | Has defaults |
| `alert_channel_id` | ❌ | ❌ | ❌ | **NOT USED** (removed) |

## Minimum Config for Backend to Run

```json
{
  "admin_key": "CHANGE_THIS_TO_A_SECURE_RANDOM_STRING"
}
```

Backend will:
- Auto-generate admin_key if it's the placeholder
- Use default thresholds if missing
- Start successfully without discord_token or discord_webhook

## Minimum Config for Bot to Run

```json
{
  "discord_token": "YOUR_ACTUAL_BOT_TOKEN",
  "backend_url": "http://backend:5000"
}
```

Bot will:
- Exit with error if discord_token is missing or placeholder
- Exit with error if backend_url is missing
- Work without discord_webhook (some features disabled)

## Recommended Complete Config

```json
{
  "discord_token": "YOUR_ACTUAL_BOT_TOKEN",
  "backend_url": "http://backend:5000",
  "admin_key": "GENERATE_A_SECURE_RANDOM_STRING_HERE",
  "discord_webhook": "https://discord.com/api/webhooks/YOUR_WEBHOOK",
  "thresholds": {
    "margin_min": 100000,
    "dump_drop_pct": 5,
    "spike_rise_pct": 5,
    "min_volume": 100
  }
}
```

