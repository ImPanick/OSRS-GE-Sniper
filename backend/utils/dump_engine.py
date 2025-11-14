#!/usr/bin/env python3
# backend/utils/dump_engine.py
"""
5-Minute Time-Series Dump Engine
- Fetches /5m data from OSRS Wiki API
- Stores snapshots in database
- Calculates dump quality scores (0-100) using precise, deterministic metrics
- Maps scores to tier system (Iron → Diamond)

True Dump Detection:
A "dump" represents oversupply - large quantities sold at lower prices than usual.
This is NOT just a price drop, but a combination of:
- Price drop percentage (from baseline period)
- Volume spike (current volume vs expected baseline)
- Oversupply ratio (volume traded vs GE buy limit)
- Buy speed (trades per 5 minutes relative to limit)

All metrics are computed deterministically and are fully explainable.
"""
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os
import threading
import time
import logging

# Import database and metadata modules
from .database import get_db_session, db_transaction, bulk_insert_snapshots
from sqlalchemy import text
from .item_metadata import get_item_meta

# Configure logging
logger = logging.getLogger(__name__)

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

# Centralized Dump Scoring Configuration
# This configuration controls how dump scores are calculated.
# All weights must sum to 100.0 for proper normalization.
DUMP_SCORING_CONFIG = {
    # Component weights (must sum to 100.0)
    "weights": {
        "drop_pct": 40.0,      # Price drop percentage (largest weight)
        "vol_spike_pct": 30.0,  # Volume spike percentage
        "oversupply_pct": 20.0, # Oversupply percentage
        "max_profit_gp": 10.0,  # Maximum profit potential (normalized)
    },
    
    # Normalization factors (how to convert raw metrics to score components)
    "normalization": {
        # drop_pct: percentage points per score point
        # A 20% drop = 40 points (max for this component)
        "drop_pct_factor": 2.0,  # drop_pct * 2.0 = score (capped at weight)
        
        # vol_spike_pct: percentage points per score point
        # A 100% spike (double expected) = 30 points (max for this component)
        "vol_spike_pct_factor": 0.3,  # vol_spike_pct * 0.3 = score (capped at weight)
        
        # oversupply_pct: percentage points per score point
        # 100% oversupply (volume = limit) = 20 points (max for this component)
        "oversupply_pct_factor": 0.2,  # oversupply_pct * 0.2 = score (capped at weight)
        
        # max_profit_gp: GP per score point (normalized)
        # This is normalized based on a reference value (e.g., 1M GP = 10 points)
        "max_profit_gp_reference": 1000000.0,  # 1M GP = 10 points (max for this component)
        "max_profit_gp_factor": 10.0,  # (max_profit_gp / reference) * factor = score (capped at weight)
    },
    
    # Thresholds for flag detection
    "thresholds": {
        # slow_buy: volume is less than this percentage of expected 5-minute volume
        "slow_buy_volume_pct": 50.0,  # Less than 50% of expected volume in 5 minutes
        
        # one_gp_dump: price dropped to 1 GP
        "one_gp_dump_price": 1,
        
        # Minimum history required for reliable scoring
        "min_history_snapshots": 2,  # Need at least 2 snapshots to compare
        "preferred_history_snapshots": 48,  # Prefer 48 snapshots (4 hours)
    },
    
    # Baseline calculation
    "baseline": {
        # Use median for price baseline (more robust to outliers)
        "use_median_for_price": True,
        # Use mean for volume baseline (captures average activity)
        "use_mean_for_volume": True,
        # Number of recent snapshots to use for baseline (excluding current)
        "baseline_snapshots": 12,  # Last 12 snapshots (1 hour) for baseline
    }
}

def fetch_with_fallback(url, headers, fallback_url=None, fallback_headers=None, timeout=30):
    """Fetch data from primary API with automatic fallback"""
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json(), 'primary'
    except Exception as e:
        logger.warning(f"Primary API failed ({url}): {e}")
        if fallback_url and fallback_headers:
            try:
                response = requests.get(fallback_url, headers=fallback_headers, timeout=timeout)
                response.raise_for_status()
                return response.json(), 'fallback'
            except Exception as fallback_error:
                logger.error(f"Fallback API also failed: {fallback_error}")
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
            logger.info("Using fallback API for 5m prices")
        
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
        
        logger.info(f"Fetched 5m snapshot: {len(snapshot)} items")
        return snapshot
        
    except Exception as e:
        logger.error(f"fetch_5m_snapshot failed: {e}", exc_info=True)
        return {}

def record_snapshot(snapshot: Dict[str, Dict]):
    """
    Persist 5-minute snapshot to database
    
    Args:
        snapshot: Dict mapping item_id (str) to {low, high, volume, timestamp}
    """
    try:
        # Convert snapshot dict to list of records for bulk insert
        snapshot_data = []
        for item_id_str, data in snapshot.items():
            item_id = int(item_id_str)
            timestamp = data.get("timestamp", int(datetime.now().timestamp()))
            low = data.get("low")
            high = data.get("high")
            volume = data.get("volume", 0)
            
            if low is None or high is None:
                continue
            
            snapshot_data.append({
                "item_id": item_id,
                "timestamp": timestamp,
                "low": low,
                "high": high,
                "volume": volume
            })
        
        # Use bulk insert for better performance
        if snapshot_data:
            bulk_insert_snapshots(snapshot_data, table_name='ge_prices_5m')
            logger.info(f"Recorded {len(snapshot_data)} items to database")
    except Exception as e:
        logger.error(f"record_snapshot failed: {e}", exc_info=True)

def fetch_5m_snapshot_at_timestamp(timestamp: int) -> Dict[str, Dict]:
    """
    Fetch 5-minute snapshot from OSRS Wiki API for a specific timestamp
    
    Args:
        timestamp: Unix timestamp (will be aligned to 5-minute boundary)
    
    Returns:
        Dict mapping item_id (str) to {low, high, volume, timestamp}
    """
    try:
        # Align timestamp to 5-minute boundary
        aligned_ts = (timestamp // 300) * 300
        
        # Fetch 5-minute prices for specific timestamp
        url = f"{BASE_URL}/5m?timestamp={aligned_ts}"
        data_5m_raw, source = fetch_with_fallback(
            url,
            HEADERS,
            None,  # Fallback API doesn't support 5m endpoint
            None,
            timeout=30
        )
        
        if source == 'fallback':
            logger.info(f"Using fallback API for 5m prices at timestamp {aligned_ts}")
        
        # Convert to dict format
        data_5m = convert_5m_data_to_dict(data_5m_raw)
        
        # Build snapshot with timestamp
        snapshot = {}
        for item_id_str, item_data in data_5m.items():
            snapshot[item_id_str] = {
                "low": item_data.get("avgLowPrice"),
                "high": item_data.get("avgHighPrice"),
                "volume": item_data.get("volume", 0) or 0,
                "timestamp": item_data.get("timestamp") or aligned_ts
            }
        
        return snapshot
        
    except Exception as e:
        logger.error(f"fetch_5m_snapshot_at_timestamp failed for timestamp {timestamp}: {e}", exc_info=True)
        return {}

def fetch_recent_history(hours: int = 4) -> Dict:
    """
    Fetches 5-minute GE snapshots for the last `hours` hours
    from the RuneScape prices wiki API and writes them to the DB.
    
    Args:
        hours: Number of hours of history to fetch (default 4, max 24)
    
    Returns:
        Summary dict: { 'hours': hours, 'snapshots': n, 'items_written': m, 'items_inserted': x, 'items_skipped': y }
    """
    # Cap hours to a sane maximum
    hours = min(max(1, hours), 24)
    
    try:
        now_ts = int(datetime.now().timestamp())
        # Align to 5-minute boundary
        now_floor = (now_ts // 300) * 300
        
        # Calculate start timestamp (hours ago, also aligned)
        start_ts = now_floor - (hours * 3600)
        start_ts = (start_ts // 300) * 300  # Align start to 5-minute boundary
        
        total_snapshots = 0
        total_items_written = 0
        total_items_inserted = 0
        total_items_skipped = 0
        
        # Iterate backwards from now_floor to start_ts (inclusive) in 300s increments
        current_ts = now_floor
        timestamps_to_fetch = []
        
        while current_ts >= start_ts:
            timestamps_to_fetch.append(current_ts)
            current_ts -= 300
        
        logger.info(f"Fetching {len(timestamps_to_fetch)} snapshots for last {hours} hours")
        
        for ts in timestamps_to_fetch:
            try:
                # Fetch snapshot for this timestamp
                snapshot = fetch_5m_snapshot_at_timestamp(ts)
                
                if not snapshot:
                    logger.warning(f"No data for timestamp {ts}")
                    continue
                
                # Record snapshot to database using bulk insert
                snapshot_data = []
                items_skipped = 0
                for item_id_str, data in snapshot.items():
                    item_id = int(item_id_str)
                    timestamp = data.get("timestamp", ts)
                    low = data.get("low")
                    high = data.get("high")
                    volume = data.get("volume", 0)
                    
                    if low is None or high is None:
                        items_skipped += 1
                        continue
                    
                    snapshot_data.append({
                        "item_id": item_id,
                        "timestamp": timestamp,
                        "low": low,
                        "high": high,
                        "volume": volume
                    })
                
                if snapshot_data:
                    bulk_insert_snapshots(snapshot_data, table_name='ge_prices_5m')
                    items_inserted = len(snapshot_data)
                else:
                    items_inserted = 0
                
                total_snapshots += 1
                total_items_written += len(snapshot)
                total_items_inserted += items_inserted
                total_items_skipped += items_skipped
                
                # Small sleep between requests to respect rate limits
                time.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Failed to fetch/record snapshot for timestamp {ts}: {e}", exc_info=True)
                # Continue to next timestamp
                continue
        
        logger.info(f"Fetched {total_snapshots} snapshots, wrote {total_items_written} item entries ({total_items_inserted} new, {total_items_skipped} skipped)")
        
        return {
            'hours': hours,
            'snapshots': total_snapshots,
            'items_written': total_items_written,
            'items_inserted': total_items_inserted,
            'items_skipped': total_items_skipped
        }
        
    except Exception as e:
        logger.error(f"fetch_recent_history failed: {e}", exc_info=True)
        return {
            'hours': hours,
            'snapshots': 0,
            'items_written': 0,
            'items_inserted': 0,
            'items_skipped': 0,
            'error': str(e)
        }

def get_recent_history(item_id: int, minutes: int = 240) -> List[Dict]:
    """
    Get recent 5-minute snapshots for an item
    
    Args:
        item_id: OSRS item ID
        minutes: Number of minutes of history to retrieve (default 240 = 4 hours)
        
    Returns:
        List of dicts with keys: timestamp, low, high, volume
        Ordered by timestamp ASC (oldest first)
    """
    try:
        session = get_db_session()
        try:
            cutoff = int(datetime.now().timestamp()) - (minutes * 60)
            # Get up to 48 snapshots (4 hours * 12 snapshots per hour)
            max_snapshots = (minutes // 5) + 1
            result = session.execute(
                text("""
                    SELECT timestamp, low, high, volume
                    FROM ge_prices_5m
                    WHERE item_id = :item_id AND timestamp > :cutoff
                    ORDER BY timestamp ASC
                    LIMIT :max_snapshots
                """),
                {"item_id": item_id, "cutoff": cutoff, "max_snapshots": max_snapshots}
            )
            
            rows = result.fetchall()
            return [
                {
                    "timestamp": row[0],
                    "low": row[1],
                    "high": row[2],
                    "volume": row[3]
                }
                for row in rows
            ]
        finally:
            session.close()
    except Exception as e:
        logger.error(f"get_recent_history failed for item {item_id}: {e}", exc_info=True)
        return []

def compute_baseline_metrics(history: List[Dict], use_median_for_price: bool = True, use_mean_for_volume: bool = True, baseline_snapshots: int = 12) -> Tuple[float, float]:
    """
    Compute baseline price and volume from history.
    
    Args:
        history: List of snapshots (ordered by timestamp ASC, oldest first)
        use_median_for_price: If True, use median for price baseline (more robust)
        use_mean_for_volume: If True, use mean for volume baseline
        baseline_snapshots: Number of recent snapshots to use for baseline (excluding current)
    
    Returns:
        Tuple of (baseline_price, baseline_volume)
        Returns (0.0, 0.0) if insufficient data
    """
    if not history or len(history) < 2:
        return (0.0, 0.0)
    
    # Use last N snapshots for baseline (excluding the most recent, which is the current)
    baseline_data = history[-baseline_snapshots-1:-1] if len(history) > baseline_snapshots else history[:-1]
    
    if not baseline_data:
        return (0.0, 0.0)
    
    # Extract prices and volumes
    prices = [h.get("low", 0) for h in baseline_data if h.get("low") and h.get("low") > 0]
    volumes = [h.get("volume", 0) for h in baseline_data if h.get("volume") is not None]
    
    if not prices:
        return (0.0, 0.0)
    
    # Compute baseline price
    if use_median_for_price:
        prices_sorted = sorted(prices)
        mid = len(prices_sorted) // 2
        if len(prices_sorted) % 2 == 0:
            baseline_price = (prices_sorted[mid - 1] + prices_sorted[mid]) / 2.0
        else:
            baseline_price = prices_sorted[mid]
    else:
        baseline_price = sum(prices) / len(prices)
    
    # Compute baseline volume
    if use_mean_for_volume:
        baseline_volume = sum(volumes) / len(volumes) if volumes else 0.0
    else:
        volumes_sorted = sorted(volumes)
        mid = len(volumes_sorted) // 2
        if len(volumes_sorted) % 2 == 0:
            baseline_volume = (volumes_sorted[mid - 1] + volumes_sorted[mid]) / 2.0 if volumes_sorted else 0.0
        else:
            baseline_volume = volumes_sorted[mid] if volumes_sorted else 0.0
    
    return (baseline_price, baseline_volume)

def compute_dump_metrics(
    current_low: float,
    current_high: float,
    current_volume: int,
    history: List[Dict],
    buy_limit: int
) -> Dict:
    """
    Compute all dump-related metrics for an item.
    
    This function computes:
    - drop_pct: Price drop percentage from baseline
    - vol_spike_pct: Volume spike percentage vs baseline
    - oversupply_pct: Current volume as percentage of buy limit
    - slow_buy: Flag indicating slow buy speed
    - one_gp_dump: Flag indicating price dropped to 1 GP
    - margin_gp: Price margin (high - low)
    - max_buy_4h: GE buy limit (max units per 4 hours)
    - max_profit_gp: Maximum potential profit (margin_gp * max_buy_4h)
    
    Args:
        current_low: Current low price
        current_high: Current high price
        current_volume: Current 5-minute volume
        history: List of recent snapshots (ordered by timestamp ASC)
        buy_limit: GE buy limit (max units per 4 hours)
    
    Returns:
        Dict with all computed metrics, or None if insufficient data
    """
    config = DUMP_SCORING_CONFIG
    
    # Check minimum history requirement
    min_history = config["thresholds"]["min_history_snapshots"]
    if len(history) < min_history:
        logger.debug(f"Insufficient history: {len(history)} < {min_history} snapshots")
        return None
    
    # Validate current data
    if current_low is None or current_high is None or current_low <= 0:
        logger.debug(f"Invalid current price data: low={current_low}, high={current_high}")
        return None
    
    # Compute baseline metrics
    baseline_price, baseline_volume = compute_baseline_metrics(
        history,
        use_median_for_price=config["baseline"]["use_median_for_price"],
        use_mean_for_volume=config["baseline"]["use_mean_for_volume"],
        baseline_snapshots=config["baseline"]["baseline_snapshots"]
    )
    
    if baseline_price <= 0:
        logger.debug(f"Invalid baseline price: {baseline_price}")
        return None
    
    # 1. drop_pct: Price drop percentage from baseline
    # Formula: (baseline_price - current_low) / current_low * 100
    # Negative values mean price increased (clamp to 0)
    drop_pct = max(0.0, ((baseline_price - current_low) / current_low) * 100) if current_low > 0 else 0.0
    
    # 2. vol_spike_pct: Volume spike percentage vs baseline
    # Formula: (current_volume / baseline_volume - 1) * 100
    # Handle baseline_volume = 0 cleanly
    if baseline_volume > 0:
        vol_spike_pct = ((current_volume / baseline_volume) - 1.0) * 100.0
    else:
        # If baseline is 0, any volume is a spike
        vol_spike_pct = 100.0 if current_volume > 0 else 0.0
    
    # Clamp to reasonable range (avoid extreme outliers)
    vol_spike_pct = max(0.0, min(vol_spike_pct, 10000.0))  # Cap at 10000% spike
    
    # 3. oversupply_pct: Current volume as percentage of buy limit
    # Formula: (current_volume / buy_limit) * 100
    # Clamp to reasonable range
    if buy_limit > 0:
        oversupply_pct = min((current_volume / buy_limit) * 100.0, 10000.0)  # Cap at 10000%
    else:
        oversupply_pct = 0.0
    
    # 4. slow_buy flag: Volume is less than expected 5-minute volume
    # Expected 5-minute volume = buy_limit / (4h * 12 periods per hour) = buy_limit / 48
    # slow_buy = current_volume < threshold * expected_5m_volume
    expected_5m_volume = buy_limit / 48.0 if buy_limit > 0 else 0.0
    slow_buy_threshold = config["thresholds"]["slow_buy_volume_pct"] / 100.0
    slow_buy = current_volume < (slow_buy_threshold * expected_5m_volume) if expected_5m_volume > 0 else False
    
    # 5. one_gp_dump flag: Price dropped to 1 GP
    one_gp_dump = current_low <= config["thresholds"]["one_gp_dump_price"]
    
    # 6. margin_gp: Price margin (high - low), clamped at >= 0
    margin_gp = max(0.0, current_high - current_low)
    
    # 7. max_buy_4h: Directly from metadata (GE buy limit)
    max_buy_4h = buy_limit
    
    # 8. max_profit_gp: Maximum potential profit
    # Formula: margin_gp * max_buy_4h
    max_profit_gp = margin_gp * max_buy_4h
    
    return {
        "drop_pct": drop_pct,
        "vol_spike_pct": vol_spike_pct,
        "oversupply_pct": oversupply_pct,
        "slow_buy": slow_buy,
        "one_gp_dump": one_gp_dump,
        "margin_gp": margin_gp,
        "max_buy_4h": max_buy_4h,
        "max_profit_gp": max_profit_gp,
        "baseline_price": baseline_price,
        "baseline_volume": baseline_volume,
    }

def compute_dump_score(metrics: Dict) -> float:
    """
    Compute dump quality score (0-100) using weighted model.
    
    This function uses the centralized DUMP_SCORING_CONFIG to compute
    a weighted score from the provided metrics.
    
    Args:
        metrics: Dict with keys: drop_pct, vol_spike_pct, oversupply_pct, max_profit_gp
                (from compute_dump_metrics)
    
    Returns:
        Score from 0-100, where:
        - 0-10: Iron tier (minimal dump)
        - 91-100: Diamond tier (exceptional dump opportunity)
    """
    if not metrics:
        return 0.0
    
    config = DUMP_SCORING_CONFIG
    weights = config["weights"]
    norm = config["normalization"]
    
    # 1. drop_pct component (weight: 40.0)
    drop_pct = metrics.get("drop_pct", 0.0)
    drop_score = min(drop_pct * norm["drop_pct_factor"], weights["drop_pct"])
    
    # 2. vol_spike_pct component (weight: 30.0)
    vol_spike_pct = metrics.get("vol_spike_pct", 0.0)
    vol_spike_score = min(vol_spike_pct * norm["vol_spike_pct_factor"], weights["vol_spike_pct"])
    
    # 3. oversupply_pct component (weight: 20.0)
    oversupply_pct = metrics.get("oversupply_pct", 0.0)
    oversupply_score = min(oversupply_pct * norm["oversupply_pct_factor"], weights["oversupply_pct"])
    
    # 4. max_profit_gp component (weight: 10.0)
    # Normalize profit to reference value
    max_profit_gp = metrics.get("max_profit_gp", 0.0)
    profit_normalized = (max_profit_gp / norm["max_profit_gp_reference"]) * norm["max_profit_gp_factor"]
    profit_score = min(profit_normalized, weights["max_profit_gp"])
    
    # Combine weighted components
    total_score = drop_score + vol_spike_score + oversupply_score + profit_score
    
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
    - Price drops from baseline period
    - Volume spikes vs expected baseline
    - Oversupply ratios (volume vs GE buy limit)
    - Buy speed (trades per 5 minutes)
    
    Uses in-memory cache to avoid recomputing on every API request.
    Cache expires after CACHE_TTL seconds (default 5 minutes).
    
    Args:
        use_cache: If True, return cached results if still valid
        
    Returns:
        List of dicts with dump analysis for each candidate item.
        Each dict includes ALL metrics used in scoring for full explainability:
        - id (item_id): OSRS item ID
        - name: Item name
        - tier: Tier name ("iron", "copper", ..., "diamond")
        - emoji: Tier emoji
        - group: Tier group ("metals" or "gems")
        - score: Quality score (0-100)
        - drop_pct: Price drop percentage from baseline
        - vol_spike_pct: Volume spike percentage vs baseline
        - oversupply_pct: Oversupply percentage (volume vs buy limit)
        - slow_buy: Boolean flag (slow buy speed)
        - one_gp_dump: Boolean flag (price dropped to 1 GP)
        - volume: Current 5-minute volume
        - high: Current high price
        - low: Current low price
        - margin_gp: Price margin (high - low) in GP
        - max_buy_4h: GE buy limit (max units per 4 hours)
        - max_profit_gp: Maximum potential profit (margin_gp * max_buy_4h)
        - flags: List of special flags (e.g., "slow_buy", "one_gp_dump", "super")
        - timestamp: ISO timestamp of snapshot
    """
    global _cache_lock, _opportunities_cache, _cache_timestamp
    
    # Check cache first
    if use_cache:
        with _cache_lock:
            current_time = time.time()
            if _opportunities_cache and (current_time - _cache_timestamp) < CACHE_TTL:
                logger.debug(f"Returning cached opportunities ({len(_opportunities_cache)} items)")
                return _opportunities_cache.copy()
    
    try:
        # Fetch latest snapshot
        snapshot = fetch_5m_snapshot()
        if not snapshot:
            return []
        
        opportunities = []
        current_time = int(datetime.now().timestamp())
        config = DUMP_SCORING_CONFIG
        
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
            
            # Get recent history (last 4 hours = 240 minutes = 48 snapshots)
            # This provides baseline for volume comparison
            history = get_recent_history(item_id, minutes=240)
            
            # Check minimum history requirement
            min_history = config["thresholds"]["min_history_snapshots"]
            if len(history) < min_history:
                logger.debug(f"Item {item_id}: insufficient history ({len(history)} < {min_history})")
                continue
            
            # Compute all dump metrics
            metrics = compute_dump_metrics(
                current_low=low,
                current_high=high,
                current_volume=volume,
                history=history,
                buy_limit=buy_limit
            )
            
            if not metrics:
                logger.debug(f"Item {item_id}: failed to compute metrics")
                continue
            
            # Only consider items with price drop (true dump)
            if metrics["drop_pct"] <= 0:
                continue
            
            # Compute dump quality score (0-100)
            score = compute_dump_score(metrics)
            
            # Skip opportunities with score 0 (no dump detected)
            if score <= 0:
                continue
            
            # Assign tier based on score
            tier_info = assign_tier(score)
            
            # Determine special flags
            flags = []
            if metrics["slow_buy"]:
                flags.append("slow_buy")
            if metrics["one_gp_dump"]:
                flags.append("one_gp_dump")
            # Super tier: Platinum or higher (score >= 51)
            if score >= 51:
                flags.append("super")
            
            # Build opportunity dict with ALL metrics for explainability
            opportunity = {
                "id": item_id,  # Primary ID field
                "item_id": item_id,  # Also include for compatibility
                "name": item_name,
                "tier": tier_info["tier_name"],
                "emoji": tier_info["emoji"],
                "group": tier_info["group"],
                "score": round(score, 1),
                # All underlying metrics (for explainability)
                "drop_pct": round(metrics["drop_pct"], 1),
                "vol_spike_pct": round(metrics["vol_spike_pct"], 1),
                "oversupply_pct": round(metrics["oversupply_pct"], 1),
                "slow_buy": metrics["slow_buy"],
                "one_gp_dump": metrics["one_gp_dump"],
                "volume": int(volume),
                "high": int(high),
                "low": int(low),
                "buy": int(low),  # Alias for compatibility
                "sell": int(high),  # Alias for compatibility
                "margin_gp": int(metrics["margin_gp"]),
                "max_buy_4h": int(metrics["max_buy_4h"]),
                "max_profit_gp": int(metrics["max_profit_gp"]),
                "flags": flags,
                "limit": int(buy_limit),  # Legacy alias
                "timestamp": datetime.fromtimestamp(current_data.get("timestamp", current_time)).isoformat() + "Z",
                # Additional explainability fields (optional, for debugging)
                "baseline_price": round(metrics.get("baseline_price", 0), 1),
                "baseline_volume": round(metrics.get("baseline_volume", 0), 1),
            }
            
            opportunities.append(opportunity)
        
        # Sort by score (highest first) - best opportunities first
        opportunities.sort(key=lambda x: x["score"], reverse=True)
        
        # Update cache
        with _cache_lock:
            _opportunities_cache = opportunities.copy()
            _cache_timestamp = time.time()
        
        logger.info(f"Analyzed {len(opportunities)} dump opportunities (cached)")
        return opportunities
        
    except Exception as e:
        logger.error(f"analyze_dumps failed: {e}", exc_info=True)
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
        logger.info(f"Starting cycle at {datetime.now().isoformat()}")
        
        # Fetch 5-minute snapshot
        snapshot = fetch_5m_snapshot()
        if not snapshot:
            logger.warning("No snapshot data available")
            return []
        
        # Record snapshot to database
        record_snapshot(snapshot)
        
        # Analyze dumps (force refresh, don't use cache)
        opportunities = analyze_dumps(use_cache=False)
        
        logger.info(f"Cycle complete: {len(opportunities)} opportunities found")
        return opportunities
        
    except Exception as e:
        logger.error(f"run_cycle failed: {e}", exc_info=True)
        return []

if __name__ == "__main__":
    # Test run
    print("Running dump engine test cycle...")
    opportunities = run_cycle()
    if opportunities:
        print(f"\nTop 5 opportunities:")
        for opp in opportunities[:5]:
            print(f"  {opp['emoji']} {opp['name']}: {opp['score']:.1f} ({opp['tier']})")
            print(f"    drop_pct: {opp['drop_pct']:.1f}%, vol_spike: {opp['vol_spike_pct']:.1f}%, oversupply: {opp['oversupply_pct']:.1f}%")
