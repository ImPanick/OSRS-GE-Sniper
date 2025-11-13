#!/usr/bin/env python3
# backend/utils/dump_engine.py
"""
5-Minute Time-Series Dump Engine
- Fetches /5m data from OSRS Wiki API
- Stores snapshots in database
- Calculates dump quality scores (0-100)
- Maps scores to tier system (Iron → Diamond)

True Dump Detection:
A "dump" represents oversupply - large quantities sold at lower prices than usual.
This is NOT just a price drop, but a combination of:
- Price drop percentage (from previous period)
- Volume spike (current volume vs expected baseline)
- Oversupply ratio (volume traded vs GE buy limit)
- Buy speed (trades per 5 minutes relative to limit)
"""
import requests
from datetime import datetime
from typing import Dict, List, Optional
import os
import threading
import time

# Import database and metadata modules
from .database import get_db_connection, db_transaction
from .item_metadata import get_item_meta

# OSRS Wiki API configuration
BASE_URL = "https://prices.runescape.wiki/api/v1/osrs"
USER_AGENT = os.getenv('OSRS_API_USER_AGENT', "OSRS-GE-Sniper/1.0 (https://github.com/ImPanick/OSRS-GE-Sniper; contact@example.com)")
HEADERS = {"User-Agent": USER_AGENT}
FALLBACK_BASE = "https://grandexchange.tools/api"
FALLBACK_HEADERS = {"User-Agent": USER_AGENT}

# In-memory cache for opportunities (refreshed by background worker)
_opportunities_cache: List[Dict] = []
_cache_lock = threading.Lock()
_cache_timestamp: float = 0.0
CACHE_TTL = 300  # Cache expires after 5 minutes (300 seconds)

# Tier definitions (canonical)
TIERS = [
    {"name": "iron", "emoji": "🔩", "group": "metals", "min": 0, "max": 10},
    {"name": "copper", "emoji": "🪙", "group": "metals", "min": 11, "max": 20},
    {"name": "bronze", "emoji": "🏅", "group": "metals", "min": 21, "max": 30},
    {"name": "silver", "emoji": "🥈", "group": "metals", "min": 31, "max": 40},
    {"name": "gold", "emoji": "🥇", "group": "metals", "min": 41, "max": 50},
    {"name": "platinum", "emoji": "⚪", "group": "metals", "min": 51, "max": 60},
    {"name": "ruby", "emoji": "💎🔴", "group": "gems", "min": 61, "max": 70},
    {"name": "sapphire", "emoji": "💎🔵", "group": "gems", "min": 71, "max": 80},
    {"name": "emerald", "emoji": "💎🟢", "group": "gems", "min": 81, "max": 90},
    {"name": "diamond", "emoji": "💎", "group": "gems", "min": 91, "max": 100},
]

def fetch_with_fallback(url, headers, fallback_url=None, fallback_headers=None, timeout=30):
    """Fetch data from primary API with automatic fallback"""
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json(), 'primary'
    except Exception as e:
        print(f"[WARN] Primary API failed ({url}): {e}")
        if fallback_url and fallback_headers:
            try:
                response = requests.get(fallback_url, headers=fallback_headers, timeout=timeout)
                response.raise_for_status()
                return response.json(), 'fallback'
            except Exception as fallback_error:
                print(f"[ERROR] Fallback API also failed: {fallback_error}")
                raise
        raise

def convert_5m_data_to_dict(data_5m):
    """
    Convert 5m price data to dict format for easier access.
    OSRS API /5m endpoint returns: {"data": {"2": {"avgHighPrice": 2550, "highPriceVolume": 100, ...}}}
    """
    if isinstance(data_5m, dict) and "data" in data_5m:
        data = data_5m["data"]
        result = {}
        for item_id, item_data in data.items():
            # Calculate volume from highPriceVolume and lowPriceVolume
            volume = (item_data.get("highPriceVolume", 0) or 0) + (item_data.get("lowPriceVolume", 0) or 0)
            result[str(item_id)] = {
                "avgHighPrice": item_data.get("avgHighPrice"),
                "avgLowPrice": item_data.get("avgLowPrice"),
                "volume": volume,
                "timestamp": item_data.get("timestamp")
            }
        return result
    elif isinstance(data_5m, dict):
        return data_5m
    return {}

def fetch_5m_snapshot() -> Dict[str, Dict]:
    """
    Fetch 5-minute snapshot from OSRS Wiki API
    
    Returns:
        Dict mapping item_id (str) to {low, high, volume, timestamp}
    """
    try:
        # Fetch 5-minute prices
        data_5m_raw, source = fetch_with_fallback(
            f"{BASE_URL}/5m",
            HEADERS,
            None,  # Fallback API doesn't support 5m endpoint
            None,
            timeout=30
        )
        
        if source == 'fallback':
            print("[INFO] Using fallback API for 5m prices")
        
        # Convert to dict format
        data_5m = convert_5m_data_to_dict(data_5m_raw)
        
        # Also fetch latest prices for current low/high
        latest, _ = fetch_with_fallback(
            f"{BASE_URL}/latest",
            HEADERS,
            f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None,
            timeout=30
        )
        
        # Merge 5m data with latest prices
        snapshot = {}
        current_time = int(datetime.now().timestamp())
        
        for item_id_str, item_data in data_5m.items():
            # Get current low/high from latest
            latest_data = latest.get("data", {}).get(item_id_str, {})
            
            snapshot[item_id_str] = {
                "low": latest_data.get("low") or item_data.get("avgLowPrice"),
                "high": latest_data.get("high") or item_data.get("avgHighPrice"),
                "volume": item_data.get("volume", 0) or 0,
                "timestamp": item_data.get("timestamp") or current_time
            }
        
        print(f"[DUMP_ENGINE] Fetched 5m snapshot: {len(snapshot)} items")
        return snapshot
        
    except Exception as e:
        print(f"[ERROR] fetch_5m_snapshot failed: {e}")
        import traceback
        traceback.print_exc()
        return {}

def record_snapshot(snapshot: Dict[str, Dict]):
    """
    Persist 5-minute snapshot to database
    
    Args:
        snapshot: Dict mapping item_id (str) to {low, high, volume, timestamp}
    """
    try:
        with db_transaction() as conn:
            c = conn.cursor()
            
            for item_id_str, data in snapshot.items():
                item_id = int(item_id_str)
                timestamp = data.get("timestamp", int(datetime.now().timestamp()))
                low = data.get("low")
                high = data.get("high")
                volume = data.get("volume", 0)
                
                if low is None or high is None:
                    continue
                
                # Insert or replace (handle duplicates)
                c.execute("""
                    INSERT OR REPLACE INTO ge_prices_5m 
                    (item_id, timestamp, low, high, volume)
                    VALUES (?, ?, ?, ?, ?)
                """, (item_id, timestamp, low, high, volume))
            
            # Clean up old data (older than 7 days)
            week_ago = int(datetime.now().timestamp()) - 7 * 24 * 60 * 60
            c.execute("DELETE FROM ge_prices_5m WHERE timestamp < ?", (week_ago,))
            
        print(f"[DUMP_ENGINE] Recorded {len(snapshot)} items to database")
    except Exception as e:
        print(f"[ERROR] record_snapshot failed: {e}")
        import traceback
        traceback.print_exc()

def get_recent_history(item_id: int, minutes: int = 60) -> List[Dict]:
    """
    Get recent 5-minute snapshots for an item
    
    Args:
        item_id: OSRS item ID
        minutes: Number of minutes of history to retrieve
        
    Returns:
        List of dicts with keys: timestamp, low, high, volume
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        cutoff = int(datetime.now().timestamp()) - (minutes * 60)
        c.execute("""
            SELECT timestamp, low, high, volume
            FROM ge_prices_5m
            WHERE item_id = ? AND timestamp > ?
            ORDER BY timestamp ASC
        """, (item_id, cutoff))
        
        rows = c.fetchall()
        return [
            {
                "timestamp": row[0],
                "low": row[1],
                "high": row[2],
                "volume": row[3]
            }
            for row in rows
        ]
    except Exception as e:
        print(f"[ERROR] get_recent_history failed for item {item_id}: {e}")
        return []

def compute_dump_score(
    prev_low: float,
    curr_low: float,
    curr_volume: float,
    avg_volume: float,
    buy_limit: int
) -> float:
    """
    Compute dump quality score (0-100) using weighted model.
    
    Scoring Formula:
    - 40% weight: Price drop percentage (how much price fell)
    - 30% weight: Volume spike percentage (current volume vs expected baseline)
    - 20% weight: Oversupply ratio (volume traded vs GE buy limit)
    - 10% weight: Buy speed (trades per 5 minutes relative to limit)
    
    Args:
        prev_low: Previous period's low price (baseline for comparison)
        curr_low: Current low price
        curr_volume: Current 5-minute volume
        avg_volume: Average volume over recent history (baseline)
        buy_limit: Max buy per 4h (GE limit)
        
    Returns:
        Score from 0-100, where:
        - 0-10: Iron tier (minimal dump)
        - 91-100: Diamond tier (exceptional dump opportunity)
    """
    if prev_low <= 0 or curr_low <= 0:
        return 0.0
    
    # 1. Calculate price drop percentage (40% weight)
    # Negative drop means price increased, so clamp to 0
    drop_pct = max(0.0, ((prev_low - curr_low) / prev_low) * 100)
    
    # Normalize drop_pct to 0-40 points (40% weight)
    # A 20% drop = 40 points (max for this component)
    drop_score = min(drop_pct * 2.0, 40.0)
    
    # 2. Calculate volume spike percentage (30% weight)
    # Expected 5-minute volume = average volume / (24h * 12 periods per hour)
    expected_5m = avg_volume / (24 * 12) if avg_volume > 0 else 1
    
    # Volume spike: how much current volume exceeds expected
    vol_spike_pct = max(0.0, ((curr_volume - expected_5m) / max(expected_5m, 1)) * 100)
    
    # Normalize vol_spike_pct to 0-30 points (30% weight)
    # A 100% spike (double expected) = 30 points (max for this component)
    vol_spike_score = min(vol_spike_pct * 0.3, 30.0)
    
    # 3. Calculate oversupply ratio (20% weight)
    # How much volume traded relative to buy limit
    # If volume = buy_limit, that's 100% oversupply in 5 minutes
    oversupply_pct = (curr_volume / max(buy_limit, 1)) * 100 if buy_limit > 0 else 0
    
    # Normalize oversupply_pct to 0-20 points (20% weight)
    # 100% oversupply (volume = limit) = 20 points (max for this component)
    oversupply_score = min(oversupply_pct * 0.2, 20.0)
    
    # 4. Calculate buy speed (10% weight)
    # Trades per 5 minutes relative to limit
    # Slow buy = lower score (good for "slow buy" flag, but lower overall score)
    # Fast buy = higher score (indicates active dumping)
    buy_speed_pct = (curr_volume / max(buy_limit, 1)) * 100 if buy_limit > 0 else 0
    
    # Normalize buy_speed_pct to 0-10 points (10% weight)
    # 100% buy speed (volume = limit in 5 min) = 10 points (max for this component)
    buy_speed_score = min(buy_speed_pct * 0.1, 10.0)
    
    # Combine weighted components
    total_score = drop_score + vol_spike_score + oversupply_score + buy_speed_score
    
    # Clamp to [0, 100]
    return max(0.0, min(100.0, total_score))

def assign_tier(score: float) -> Dict[str, str]:
    """
    Assign tier based on score.
    
    Args:
        score: Dump quality score (0-100)
        
    Returns:
        Dict with keys: tier_name, emoji, group
    """
    score = max(0, min(100, score))  # Clamp to [0, 100]
    
    for tier in TIERS:
        if tier["min"] <= score <= tier["max"]:
            return {
                "tier_name": tier["name"],
                "emoji": tier["emoji"],
                "group": tier["group"]
            }
    
    # Fallback (shouldn't happen)
    return {"tier_name": "iron", "emoji": "🔩", "group": "metals"}

def get_tier_by_name(tier_name: str) -> Optional[Dict]:
    """
    Get tier information by tier name.
    
    Args:
        tier_name: Tier name (e.g., "gold", "diamond")
        
    Returns:
        Dict with tier info (name, emoji, group, min, max) or None if not found
    """
    tier_name_lower = tier_name.lower()
    for tier in TIERS:
        if tier["name"].lower() == tier_name_lower:
            return tier.copy()
    return None

def get_all_tiers() -> List[Dict]:
    """
    Get all tier definitions.
    
    Returns:
        List of tier dicts with keys: name, emoji, group, min, max
    """
    return [tier.copy() for tier in TIERS]

def analyze_dumps(use_cache: bool = True) -> List[Dict]:
    """
    Analyze current dump/flip opportunities.
    
    This function detects true dumps (oversupply events) by analyzing:
    - Price drops from previous periods
    - Volume spikes vs expected baseline
    - Oversupply ratios (volume vs GE buy limit)
    - Buy speed (trades per 5 minutes)
    
    Uses in-memory cache to avoid recomputing on every API request.
    Cache expires after CACHE_TTL seconds (default 5 minutes).
    
    Args:
        use_cache: If True, return cached results if still valid
        
    Returns:
        List of dicts with dump analysis for each candidate item.
        Each dict includes:
        - id (item_id): OSRS item ID
        - name: Item name
        - tier: Tier name ("iron", "copper", ..., "diamond")
        - emoji: Tier emoji
        - group: Tier group ("metals" or "gems")
        - score: Quality score (0-100)
        - drop_pct: Price drop percentage
        - vol_spike_pct: Volume spike percentage
        - oversupply_pct: Oversupply percentage (volume vs buy limit)
        - buy_speed: Buy speed percentage (volume vs limit per 5 min)
        - volume: Current 5-minute volume
        - high: Current high price
        - low: Current low price
        - max_buy_4h: GE buy limit (max units per 4 hours)
        - flags: List of special flags (e.g., "slow_buy", "one_gp_dump", "super")
        - timestamp: ISO timestamp of snapshot
    """
    # Check cache first
    if use_cache:
        with _cache_lock:
            current_time = time.time()
            if _opportunities_cache and (current_time - _cache_timestamp) < CACHE_TTL:
                print(f"[DUMP_ENGINE] Returning cached opportunities ({len(_opportunities_cache)} items)")
                return _opportunities_cache.copy()
    
    try:
        # Fetch latest snapshot
        snapshot = fetch_5m_snapshot()
        if not snapshot:
            return []
        
        opportunities = []
        current_time = int(datetime.now().timestamp())
        
        for item_id_str, current_data in snapshot.items():
            item_id = int(item_id_str)
            
            # Get item metadata (includes buy_limit)
            meta = get_item_meta(item_id)
            if not meta:
                continue
            
            buy_limit = meta.get('buy_limit', 0)
            item_name = meta.get('name', f'Item {item_id}')
            
            # Skip items with no buy limit (untradeable or special items)
            if buy_limit == 0:
                continue
            
            low = current_data.get("low")
            high = current_data.get("high")
            volume = current_data.get("volume", 0)
            
            # Skip items with invalid price data
            if low is None or high is None or low <= 0:
                continue
            
            # Get recent history (last 60 minutes = 12 snapshots)
            # This provides baseline for volume comparison
            history = get_recent_history(item_id, minutes=60)
            
            # Need at least 2 snapshots to compare current vs previous
            if len(history) < 2:
                continue
            
            # Calculate average volume over history (baseline)
            avg_volume = sum(h.get("volume", 0) for h in history) / len(history) if history else 0
            
            # Get previous low price (from second-to-last snapshot)
            # This represents the "before" state for price drop calculation
            prev_low = history[-2].get("low") if len(history) >= 2 else low
            
            # Skip if no price drop (not a dump)
            if prev_low <= 0 or low >= prev_low:
                continue
            
            # Compute dump quality score (0-100)
            score = compute_dump_score(
                prev_low=prev_low,
                curr_low=low,
                curr_volume=volume,
                avg_volume=avg_volume,
                buy_limit=buy_limit
            )
            
            # Skip opportunities with score 0 (no dump detected)
            if score <= 0:
                continue
            
            # Assign tier based on score
            tier_info = assign_tier(score)
            
            # Calculate detailed metrics for display
            drop_pct = ((prev_low - low) / prev_low * 100) if prev_low > 0 else 0
            expected_5m = avg_volume / (24 * 12) if avg_volume > 0 else 1
            vol_spike_pct = max(0.0, ((volume - expected_5m) / max(expected_5m, 1)) * 100)
            oversupply_pct = (volume / max(buy_limit, 1)) * 100 if buy_limit > 0 else 0
            buy_speed_pct = (volume / max(buy_limit, 1)) * 100 if buy_limit > 0 else 0
            
            # Determine special flags
            flags = []
            # Slow buy: less than 50% of limit traded in 5 minutes
            # This indicates a gradual dump (good for slow buyers)
            if buy_speed_pct < 50:
                flags.append("slow_buy")
            # One GP dump: price dropped to 1 GP (often indicates panic selling)
            if low == 1:
                flags.append("one_gp_dump")
            # Super tier: Platinum or higher (score >= 51)
            # These are exceptional opportunities
            if score >= 51:
                flags.append("super")
            
            # Build opportunity dict with all required fields
            opportunity = {
                "id": item_id,  # Primary ID field
                "item_id": item_id,  # Also include for compatibility
                "name": item_name,
                "tier": tier_info["tier_name"],
                "emoji": tier_info["emoji"],
                "group": tier_info["group"],
                "score": round(score, 1),
                "drop_pct": round(drop_pct, 1),
                "vol_spike_pct": round(vol_spike_pct, 1),
                "oversupply_pct": round(oversupply_pct, 1),
                "buy_speed": round(buy_speed_pct, 1),  # Percentage, not absolute speed
                "volume": int(volume),
                "high": int(high),
                "low": int(low),
                "buy": int(low),  # Alias for compatibility
                "sell": int(high),  # Alias for compatibility
                "flags": flags,
                "max_buy_4h": buy_limit,
                "limit": buy_limit,  # Legacy alias
                "timestamp": datetime.fromtimestamp(current_data.get("timestamp", current_time)).isoformat() + "Z"
            }
            
            opportunities.append(opportunity)
        
        # Sort by score (highest first) - best opportunities first
        opportunities.sort(key=lambda x: x["score"], reverse=True)
        
        # Update cache
        with _cache_lock:
            global _opportunities_cache, _cache_timestamp
            _opportunities_cache = opportunities.copy()
            _cache_timestamp = time.time()
        
        print(f"[DUMP_ENGINE] Analyzed {len(opportunities)} dump opportunities (cached)")
        return opportunities
        
    except Exception as e:
        print(f"[ERROR] analyze_dumps failed: {e}")
        import traceback
        traceback.print_exc()
        return []

def run_cycle():
    """
    Run one complete cycle: fetch snapshot, record it, analyze dumps.
    This is the main entry point for the background worker (dump_worker.py).
    
    The cycle:
    1. Fetches latest 5-minute snapshot from OSRS Wiki API
    2. Records snapshot to database (ge_prices_5m table)
    3. Analyzes dumps and updates cache
    4. Returns list of opportunities
    
    Returns:
        List of dump opportunities (same format as analyze_dumps())
    """
    try:
        print(f"[DUMP_ENGINE] Starting cycle at {datetime.now().isoformat()}")
        
        # Fetch 5-minute snapshot
        snapshot = fetch_5m_snapshot()
        if not snapshot:
            print("[DUMP_ENGINE] No snapshot data available")
            return []
        
        # Record snapshot to database
        record_snapshot(snapshot)
        
        # Analyze dumps (force refresh, don't use cache)
        opportunities = analyze_dumps(use_cache=False)
        
        print(f"[DUMP_ENGINE] Cycle complete: {len(opportunities)} opportunities found")
        return opportunities
        
    except Exception as e:
        print(f"[ERROR] run_cycle failed: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    # Test run
    print("Running dump engine test cycle...")
    opportunities = run_cycle()
    if opportunities:
        print(f"\nTop 5 opportunities:")
        for opp in opportunities[:5]:
            print(f"  {opp['emoji']} {opp['name']}: {opp['score']:.1f} ({opp['tier']})")

