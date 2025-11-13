# Tier System Documentation

## Overview

The tier system automatically categorizes Grand Exchange dump opportunities based on a quality score (0-100). This score is calculated by analyzing multiple factors that indicate a **true dump** (oversupply event), not just a simple price drop.

## What is a "True Dump"?

A dump represents **oversupply** - large quantities of an item being sold at lower prices than usual. The system distinguishes between:

- ✅ **True Dump**: Price drop + volume spike + oversupply (high-quality opportunity)
- ❌ **Simple Price Drop**: Price fell but no volume increase (may be temporary fluctuation)

## Tier Structure

The system uses 10 tiers organized into two groups:

### Metal Tiers (Lower Quality)
- 🔩 **Iron** (0-10): Minimal dump opportunities
- 🪙 **Copper** (11-20): Low-tier opportunities
- 🏅 **Bronze** (21-30): Entry-level opportunities
- 🥈 **Silver** (31-40): Moderate opportunities
- 🥇 **Gold** (41-50): Good opportunities
- ⚪ **Platinum** (51-60): High-quality opportunities

### Gem Tiers (Higher Quality)
- 💎🔴 **Ruby** (61-70): Premium opportunities
- 💎🔵 **Sapphire** (71-80): Excellent opportunities
- 💎🟢 **Emerald** (81-90): Exceptional opportunities
- 💎 **Diamond** (91-100): Best opportunities

## How Tiers Are Assigned

### Step 1: Data Collection

The system collects 5-minute snapshots from the OSRS Wiki API:
- **Current prices**: Low and high prices for each item
- **Volume**: Number of items traded in the last 5 minutes
- **Historical data**: Previous snapshots stored in database (last 60 minutes)

### Step 2: Dump Detection

For each item, the system checks:
1. **Price Drop**: Current low price < previous low price
2. **Valid Data**: Item has a buy limit and valid price data
3. **History Available**: At least 2 snapshots exist for comparison

Items that don't meet these criteria are skipped (not considered dumps).

### Step 3: Quality Score Calculation

The quality score (0-100) is calculated using a **weighted formula** with four components:

#### Component 1: Price Drop Percentage (40% weight)
- **What it measures**: How much the price fell from the previous period
- **Calculation**: `((previous_low - current_low) / previous_low) * 100`
- **Scoring**: 
  - 20% drop = 40 points (maximum for this component)
  - Formula: `min(drop_pct * 2.0, 40.0)`
- **Why it matters**: Larger price drops indicate stronger selling pressure

**Example:**
- Previous low: 1000 GP
- Current low: 800 GP
- Drop: 20%
- Score contribution: 40 points (40% of total)

#### Component 2: Volume Spike Percentage (30% weight)
- **What it measures**: How much current volume exceeds expected baseline
- **Calculation**: 
  - Expected 5-minute volume = `average_volume / (24 hours * 12 periods per hour)`
  - Volume spike = `((current_volume - expected_volume) / expected_volume) * 100`
- **Scoring**:
  - 100% spike (double expected) = 30 points (maximum for this component)
  - Formula: `min(vol_spike_pct * 0.3, 30.0)`
- **Why it matters**: High volume confirms active dumping, not just price fluctuation

**Example:**
- Average daily volume: 12,000 items
- Expected 5-minute volume: 12,000 / 288 = ~42 items
- Current 5-minute volume: 84 items
- Volume spike: 100%
- Score contribution: 30 points (30% of total)

#### Component 3: Oversupply Ratio (20% weight)
- **What it measures**: Volume traded relative to GE buy limit
- **Calculation**: `(current_volume / buy_limit) * 100`
- **Scoring**:
  - 100% oversupply (volume = limit in 5 minutes) = 20 points (maximum)
  - Formula: `min(oversupply_pct * 0.2, 20.0)`
- **Why it matters**: High oversupply means large quantities are being dumped quickly

**Example:**
- Buy limit: 10,000 items per 4 hours
- Current 5-minute volume: 5,000 items
- Oversupply: 50%
- Score contribution: 10 points (20% of total)

#### Component 4: Buy Speed (10% weight)
- **What it measures**: Trading activity relative to buy limit per 5 minutes
- **Calculation**: `(current_volume / buy_limit) * 100`
- **Scoring**:
  - 100% buy speed (volume = limit in 5 min) = 10 points (maximum)
  - Formula: `min(buy_speed_pct * 0.1, 10.0)`
- **Why it matters**: Fast trading indicates active market activity

**Example:**
- Buy limit: 10,000 items per 4 hours
- Current 5-minute volume: 2,000 items
- Buy speed: 20%
- Score contribution: 2 points (10% of total)

### Step 4: Total Score Calculation

The final score is the sum of all four components:
```
Total Score = Drop Score + Volume Spike Score + Oversupply Score + Buy Speed Score
```

**Example Calculation:**
- Price drop: 40 points (40%)
- Volume spike: 30 points (30%)
- Oversupply: 20 points (20%)
- Buy speed: 10 points (10%)
- **Total Score: 100** → Diamond tier

### Step 5: Tier Assignment

The score is mapped to a tier based on score ranges:

```python
if score >= 91:  → Diamond tier
if score >= 81:  → Emerald tier
if score >= 71:  → Sapphire tier
if score >= 61:  → Ruby tier
if score >= 51:  → Platinum tier
if score >= 41:  → Gold tier
if score >= 31:  → Silver tier
if score >= 21:  → Bronze tier
if score >= 11:  → Copper tier
if score >= 0:   → Iron tier
```

## Special Flags

The system also assigns special flags to highlight unique characteristics:

### `slow_buy`
- **Condition**: Buy speed < 50% (less than half of limit traded in 5 minutes)
- **Meaning**: Gradual dump, good for slow buyers who want time to accumulate
- **Use case**: Items that are dumping but not being bought up quickly

### `one_gp_dump`
- **Condition**: Current low price = 1 GP
- **Meaning**: Panic selling or market manipulation
- **Use case**: Extreme dumps that may recover quickly

### `super`
- **Condition**: Score >= 51 (Platinum tier or higher)
- **Meaning**: Exceptional opportunity
- **Use case**: High-quality dumps worth immediate attention

## Filtering System

The API and dashboard support multiple filtering options:

### Tier Filtering
Filter by specific tier:
- `?tier=gold` - Only show Gold tier opportunities
- `?tier=diamond` - Only show Diamond tier opportunities

### Group Filtering
Filter by tier group:
- `?group=metals` - Show all metal tiers (Iron through Platinum)
- `?group=gems` - Show all gem tiers (Ruby through Diamond)

### Special Flag Filtering
Filter by special characteristics:
- `?special=slow_buy` - Only slow buy opportunities
- `?special=one_gp_dump` - Only 1 GP dumps
- `?special=super` - Only Platinum tier or higher

### Combined Filtering
You can combine multiple filters:
- `?tier=platinum&special=super` - Platinum tier super opportunities
- `?group=gems&special=slow_buy` - Gem tier slow buy opportunities

## What the System Looks For

### Required Conditions

1. **Price Must Drop**
   - Current low price < previous low price
   - Items with price increases are ignored

2. **Valid Item Data**
   - Item must have a buy limit > 0
   - Item must have valid price data (low > 0, high > 0)
   - Untradeable or special items are skipped

3. **Historical Context**
   - At least 2 snapshots must exist for comparison
   - System needs baseline to calculate volume spikes

### Scoring Priorities

The system prioritizes opportunities based on:

1. **Price Drop (40%)** - Most important factor
   - Larger drops = higher scores
   - Indicates strong selling pressure

2. **Volume Spike (30%)** - Second most important
   - Confirms active dumping
   - Distinguishes true dumps from price fluctuations

3. **Oversupply (20%)** - Third priority
   - Shows quantity being dumped
   - High oversupply = better opportunity

4. **Buy Speed (10%)** - Least important
   - Indicates market activity
   - Faster = more active market

### What Gets Filtered Out

The system automatically excludes:
- ❌ Items with no price drop (price increased or stayed same)
- ❌ Items with score = 0 (no dump detected)
- ❌ Items without buy limits (untradeable)
- ❌ Items with invalid price data
- ❌ Items without sufficient history (< 2 snapshots)

## Data Flow

```
1. OSRS Wiki API (/5m endpoint)
   ↓
2. Fetch 5-minute snapshot
   ↓
3. Store snapshot in database (ge_prices_5m table)
   ↓
4. For each item:
   - Compare current vs previous snapshot
   - Calculate quality score (0-100)
   - Assign tier based on score
   - Add special flags if applicable
   ↓
5. Sort opportunities by score (highest first)
   ↓
6. Cache results (5-minute TTL)
   ↓
7. Return to API/dashboard with filtering applied
```

## Caching

The system uses in-memory caching to improve performance:
- **Cache Duration**: 5 minutes (300 seconds)
- **Cache Location**: In-memory list (`_opportunities_cache`)
- **Cache Refresh**: Automatically refreshed by background worker
- **Cache Benefits**: Reduces API load and improves response times

## Example Scenarios

### Scenario 1: High-Quality Dump (Diamond Tier)

**Item**: Dragon bones
- Previous low: 3,000 GP
- Current low: 2,100 GP (30% drop)
- Average daily volume: 50,000
- Current 5-minute volume: 500
- Buy limit: 5,000 per 4 hours

**Calculations:**
- Price drop: 30% → 40 points (capped at 40)
- Volume spike: 500 vs 174 expected → 187% spike → 30 points (capped at 30)
- Oversupply: 500/5,000 = 10% → 2 points
- Buy speed: 500/5,000 = 10% → 1 point
- **Total Score: 73** → Sapphire tier

### Scenario 2: Low-Quality Dump (Iron Tier)

**Item**: Rune essence
- Previous low: 5 GP
- Current low: 4 GP (20% drop)
- Average daily volume: 1,000
- Current 5-minute volume: 4
- Buy limit: 25,000 per 4 hours

**Calculations:**
- Price drop: 20% → 40 points (capped at 40)
- Volume spike: 4 vs 0.35 expected → 1,043% spike → 30 points (capped at 30)
- Oversupply: 4/25,000 = 0.016% → 0 points
- Buy speed: 4/25,000 = 0.016% → 0 points
- **Total Score: 70** → Actually Sapphire, but low absolute value

**Note**: This example shows why absolute values matter - a 1 GP drop on a 5 GP item is less significant than a 900 GP drop on a 3,000 GP item.

### Scenario 3: Slow Buy Opportunity

**Item**: Abyssal whip
- Score: 45 (Gold tier)
- Buy speed: 30% (< 50% threshold)
- **Flag**: `slow_buy`

This indicates a gradual dump where you have time to accumulate the item.

## Configuration

### Per-Server Tier Settings

Each Discord server can configure:
- **Role Mentions**: Which Discord role to ping for each tier
- **Enable/Disable**: Turn alerts on/off per tier
- **Minimum Tier**: Only tiers at or above this threshold trigger alerts

**Example Configuration:**
- Gold tier → Role: `@GoldAlerts` → Enabled
- Platinum tier → Role: `@PremiumAlerts` → Enabled
- Minimum tier: Silver
- Result: Only Silver, Gold, Platinum, and above tiers trigger alerts

### Admin Tier Management

Admins can:
- Adjust tier score ranges (if needed)
- View all guild tier settings
- Manage tier configurations globally

## Best Practices

1. **Focus on Higher Tiers**: Platinum and above (score >= 51) are exceptional opportunities
2. **Use Special Flags**: `slow_buy` for accumulation, `super` for immediate action
3. **Set Minimum Tier**: Configure your server to only alert on tiers you care about
4. **Monitor Volume**: High volume spikes confirm true dumps vs price fluctuations
5. **Check Oversupply**: High oversupply means large quantities available

## Technical Details

### Database Tables

- `ge_prices_5m`: Stores 5-minute price snapshots
- `tiers`: Stores tier definitions (score ranges, emoji, group)
- `guild_tier_settings`: Stores per-server tier configurations
- `guild_config`: Stores minimum tier thresholds per server

### API Endpoints

- `GET /api/dumps` - Get dump opportunities with filtering
- `GET /api/dumps/<item_id>` - Get specific dump with history
- `GET /api/tiers?guild_id=<guild_id>` - Get tier configuration

### Background Processing

The dump engine runs continuously:
- Fetches 5-minute snapshots every 5 minutes
- Analyzes all items for dump opportunities
- Updates cache with latest results
- Processes in background thread (non-blocking)

## Conclusion

The tier system provides a sophisticated way to identify and categorize dump opportunities based on multiple factors. By analyzing price drops, volume spikes, oversupply, and buy speed, the system distinguishes between true dumps and simple price fluctuations, helping you find the best opportunities in the Grand Exchange.

