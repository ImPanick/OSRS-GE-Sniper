#!/usr/bin/env python3
# backend/utils/dump_engine.py
"""
5-Minute Time-Series Dump Engine
- Fetches /5m data from OSRS Wiki API
- Stores snapshots in database
- Calculates dump quality scores (0-100)
- Maps scores to tier system (Iron → Diamond)
"""
import requests
from datetime import datetime
from typing import Dict, List
import os

# Import database and metadata modules
from .database import get_db_connection, db_transaction
from .item_metadata import get_item_meta

# OSRS Wiki API configuration
BASE_URL = "https://prices.runescape.wiki/api/v1/osrs"
USER_AGENT = os.getenv('OSRS_API_USER_AGENT', "OSRS-GE-Sniper/1.0 (https://github.com/ImPanick/OSRS-GE-Sniper; contact@example.com)")
HEADERS = {"User-Agent": USER_AGENT}
FALLBACK_BASE = "https://grandexchange.tools/api"
FALLBACK_HEADERS = {"User-Agent": USER_AGENT}

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
    Compute dump quality score (0-100)
    
    Args:
        prev_low: Previous period's low price
        curr_low: Current low price
        curr_volume: Current 5-minute volume
        avg_volume: Average 5-minute volume (baseline)
        buy_limit: Max buy per 4h
        
    Returns:
        Score from 0-100
    """
    if prev_low <= 0 or curr_low <= 0:
        return 0.0
    
    # Calculate drop percentage
    drop_pct = ((prev_low - curr_low) / prev_low) * 100
    
    # Expected 5-minute volume (baseline)
    expected_5m = avg_volume / (24 * 12) if avg_volume > 0 else 1  # 24h * 12 (5-min periods)
    
    # Volume spike percentage
    vol_spike_pct = ((curr_volume - expected_5m) / max(expected_5m, 1)) * 100
    
    # Oversupply ratio (how much volume vs buy limit)
    oversupply_ratio = (curr_volume / max(buy_limit, 1)) * 100 if buy_limit > 0 else 0
    
    # Buy speed (units per 5 min relative to limit)
    buy_speed = (curr_volume / max(buy_limit, 1)) * 100 if buy_limit > 0 else 0
    
    # Combine into score (weighted)
    # 40% drop_pct, 30% vol_spike_pct, 20% oversupply_ratio, 10% buy_speed
    score = (
        min(drop_pct * 2.5, 40) +  # Max 40 points for drop (16% drop = 40 points)
        min(vol_spike_pct * 0.3, 30) +  # Max 30 points for volume spike
        min(oversupply_ratio * 0.2, 20) +  # Max 20 points for oversupply
        min(buy_speed * 0.1, 10)  # Max 10 points for buy speed
    )
    
    # Clamp to [0, 100]
    return max(0.0, min(100.0, score))

def assign_tier(score: float) -> Dict[str, str]:
    """
    Assign tier based on score
    
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

def analyze_dumps() -> List[Dict]:
    """
    Analyze current dump/flip opportunities
    
    Returns:
        List of dicts with dump analysis for each candidate item
    """
    try:
        # Fetch latest snapshot
        snapshot = fetch_5m_snapshot()
        if not snapshot:
            return []
        
        opportunities = []
        current_time = int(datetime.now().timestamp())
        
        for item_id_str, current_data in snapshot.items():
            item_id = int(item_id_str)
            
            # Get item metadata
            meta = get_item_meta(item_id)
            if not meta:
                continue
            
            buy_limit = meta.get('buy_limit', 0)
            item_name = meta.get('name', f'Item {item_id}')
            
            # Skip items with no buy limit or invalid prices
            if buy_limit == 0:
                continue
            
            low = current_data.get("low")
            high = current_data.get("high")
            volume = current_data.get("volume", 0)
            
            if low is None or high is None or low <= 0:
                continue
            
            # Get recent history (last 60 minutes = 12 snapshots)
            history = get_recent_history(item_id, minutes=60)
            
            if len(history) < 2:
                continue  # Need at least 2 snapshots for comparison
            
            # Calculate average volume over history
            avg_volume = sum(h.get("volume", 0) for h in history) / len(history) if history else 0
            
            # Get previous low price (from second-to-last snapshot)
            prev_low = history[-2].get("low") if len(history) >= 2 else low
            
            # Compute dump score
            score = compute_dump_score(
                prev_low=prev_low,
                curr_low=low,
                curr_volume=volume,
                avg_volume=avg_volume,
                buy_limit=buy_limit
            )
            
            # Assign tier
            tier_info = assign_tier(score)
            
            # Calculate metrics
            drop_pct = ((prev_low - low) / prev_low * 100) if prev_low > 0 else 0
            expected_5m = avg_volume / (24 * 12) if avg_volume > 0 else 1
            vol_spike_pct = ((volume - expected_5m) / max(expected_5m, 1)) * 100
            oversupply_pct = (volume / max(buy_limit, 1)) * 100 if buy_limit > 0 else 0
            buy_speed = (volume / max(buy_limit, 1)) * 100 if buy_limit > 0 else 0
            
            # Determine flags
            flags = []
            if buy_speed < 50:  # Less than 50% of limit in 5 min
                flags.append("slow_buy")
            if low == 1:  # One GP dump
                flags.append("one_gp_dump")
            if score >= 51:  # Platinum or higher
                flags.append("super")
            
            # Build opportunity dict
            opportunity = {
                "item_id": item_id,
                "name": item_name,
                "tier": tier_info["tier_name"],
                "emoji": tier_info["emoji"],
                "group": tier_info["group"],
                "score": round(score, 1),
                "drop_pct": round(drop_pct, 1),
                "vol_spike_pct": round(vol_spike_pct, 1),
                "oversupply_pct": round(oversupply_pct, 1),
                "buy_speed": round(buy_speed, 1),
                "volume": int(volume),
                "high": int(high),
                "low": int(low),
                "flags": flags,
                "max_buy_4h": buy_limit,
                "timestamp": datetime.fromtimestamp(current_data.get("timestamp", current_time)).isoformat() + "Z"
            }
            
            opportunities.append(opportunity)
        
        # Sort by score (highest first)
        opportunities.sort(key=lambda x: x["score"], reverse=True)
        
        print(f"[DUMP_ENGINE] Analyzed {len(opportunities)} dump opportunities")
        return opportunities
        
    except Exception as e:
        print(f"[ERROR] analyze_dumps failed: {e}")
        import traceback
        traceback.print_exc()
        return []

def run_cycle():
    """
    Run one complete cycle: fetch snapshot, record it, analyze dumps
    This is the main entry point for the background worker
    """
    try:
        print(f"[DUMP_ENGINE] Starting cycle at {datetime.now().isoformat()}")
        
        # Fetch 5-minute snapshot
        snapshot = fetch_5m_snapshot()
        if not snapshot:
            print("[DUMP_ENGINE] No snapshot data available")
            return
        
        # Record snapshot
        record_snapshot(snapshot)
        
        # Analyze dumps
        opportunities = analyze_dumps()
        
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

