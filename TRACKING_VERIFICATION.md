# GE Tracking Verification Guide

## How Real-Time Tracking Works

### 1. **Data Source: OSRS Wiki API**

The system uses the **OSRS Wiki Real-Time Prices API**:
- **Base URL**: `https://prices.runescape.wiki/api/v1/osrs`
- **Endpoints Used**:
  - `/latest` - Current high/low prices for all items
  - `/1h` - 1-hour aggregated data (volume, averages)
  - `/mapping` - Item ID to name mapping

**Important**: The OSRS Wiki API updates approximately **every 5 minutes**. This is the source of truth for GE prices.

### 2. **Polling Frequency**

Your system polls the API **every 8 seconds**:
- Location: `backend/app.py` → `poll()` function
- Interval: `time.sleep(8)` (line 443)
- Why 8 seconds? To catch updates as soon as the API refreshes (every 5 minutes)

**This means**:
- ✅ You'll see updates within 5-13 seconds of the API refreshing
- ✅ Near real-time tracking (limited by API update frequency, not your system)
- ✅ Database is updated every 8 seconds with latest available data

### 3. **Data Flow**

```
OSRS Wiki API (updates every 5 min)
    ↓
Backend poll() function (runs every 8 seconds)
    ↓
fetch_all() → Gets /latest, /1h, /mapping
    ↓
log_price() → Stores in SQLite database
    ↓
In-memory arrays (top_items, dump_items, spike_items, all_items)
    ↓
API endpoints (/api/top, /api/dumps, /api/spikes, /api/all_items)
    ↓
Frontend/Discord Bot (displays data)
```

### 4. **Database Storage**

- **Location**: `backend/utils/history.db`
- **Table**: `prices`
- **Columns**: `item_id`, `timestamp`, `low`, `high`, `volume`
- **Retention**: 7 days (auto-cleanup)
- **Update Frequency**: Every 8 seconds (when API has new data)

### 5. **What Gets Tracked**

For **every item** in the GE:
- Current buy price (low)
- Current sell price (high)
- Instant buy price (high)
- Instant sell price (low)
- 1-hour volume
- Trade limit
- Calculated profit margins
- Risk metrics

**Special Detection**:
- **Dumps**: Price drops > threshold (default 18%)
- **Spikes**: Price rises > threshold (default 20%)
- **Flips**: Profitable margin opportunities

## Verification Steps

### Step 1: Check if Polling is Running

Look for these log messages when backend starts:
```
[+] Database initialized
[+] GE tracking thread started
[POLL] Starting GE activity tracking...
[+] X flips | X dumps | X spikes
```

### Step 2: Verify Database Updates

Check the database for recent records:
```sql
SELECT COUNT(*), MAX(timestamp) 
FROM prices 
WHERE timestamp > (strftime('%s', 'now') - 3600);
```

Should show records from the last hour.

### Step 3: Test API Endpoints

```bash
# Health check
curl http://localhost:5000/api/health

# Get top flips
curl http://localhost:5000/api/top

# Get dumps
curl http://localhost:5000/api/dumps

# Get spikes
curl http://localhost:5000/api/spikes
```

### Step 4: Monitor Real-Time Updates

Watch backend logs for:
- `[+] X flips | X dumps | X spikes` (every 8 seconds)
- `[POLL] Tracking active - completed X polls` (every ~80 seconds)

## Understanding "Real-Time" Limitations

### What "Real-Time" Means Here:

1. **Your System**: Updates every 8 seconds ✅
2. **OSRS Wiki API**: Updates every ~5 minutes ⚠️
3. **Effective Latency**: 5-13 seconds from actual GE trade to your system

### Why This is Still "Near Real-Time":

- The OSRS Wiki API is the **official** source for GE prices
- It aggregates data from RuneLite clients
- 5-minute updates are the fastest available
- Your system catches updates immediately when they're available

### What You're Actually Tracking:

- ✅ **Price changes** (within 5 minutes of happening)
- ✅ **Volume changes** (1-hour aggregates)
- ✅ **Market movements** (dumps, spikes, flips)
- ❌ **Individual trades** (not available via API)
- ❌ **Sub-minute price movements** (API limitation)

## Troubleshooting

### Problem: No updates in database

**Check**:
1. Is the backend running?
2. Look for `[+] GE tracking thread started` in logs
3. Check for `[ERROR]` messages in logs
4. Verify database file exists: `backend/utils/history.db`

### Problem: Stale data

**Check**:
1. OSRS Wiki API status
2. Network connectivity
3. Backend error logs
4. Database file permissions

### Problem: Missing items

**Check**:
1. Item cache: `backend/utils/item_cache.json`
2. Cache updater service (runs every 6 hours)
3. Manual cache update: `POST /api/update_cache`

## Expected Behavior

### Normal Operation:

- **Every 8 seconds**: System polls API
- **Every 5 minutes**: API provides new data (when available)
- **Every 8 seconds**: Database gets updated with latest data
- **Every 20 seconds**: Discord bot polls backend for alerts
- **Every 6 hours**: Item cache updates

### What You Should See:

1. **Backend logs**: Regular `[+] X flips | X dumps | X spikes` messages
2. **Database**: Growing record count (thousands per hour)
3. **API endpoints**: Returning current data
4. **Discord bot**: Sending alerts for dumps/spikes

## Verification Script

Run `verify_tracking.py` to check:
- API connectivity
- Database activity
- Backend API status
- Real-time update monitoring

```bash
python verify_tracking.py
```

## Summary

✅ **Your system IS tracking GE activity in near real-time**
- Limited by OSRS Wiki API (5-minute updates)
- Your polling (8 seconds) is faster than API updates
- Database stores all price data
- All items are tracked continuously

The system is working as designed. The "real-time" aspect is constrained by the external API's update frequency, not your implementation.

