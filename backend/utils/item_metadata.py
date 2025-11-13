#!/usr/bin/env python3
# backend/utils/item_metadata.py
"""
Item Metadata Manager
- Loads item metadata (name, buy_limit) from OSRS Wiki API
- Caches metadata for fast lookups
- Provides get_item_meta() function for dump engine
"""
import requests
import json
import os
from typing import Dict, Optional

# OSRS Wiki API endpoints
BASE_URL = "https://prices.runescape.wiki/api/v1/osrs"
HEADERS = {"User-Agent": "OSRS-GE-Sniper/1.0 (https://github.com/your-repo; contact@example.com)"}
FALLBACK_BASE = "https://grandexchange.tools/api"
FALLBACK_HEADERS = {"User-Agent": "OSRS-GE-Sniper/1.0 (fallback)"}

# Cache file location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
METADATA_CACHE_FILE = os.path.join(SCRIPT_DIR, "item_metadata_cache.json")

# In-memory cache
_metadata_cache: Dict[int, Dict] = {}
_cache_loaded = False

def fetch_item_mapping():
    """Fetch item mapping from OSRS Wiki API with fallback"""
    try:
        response = requests.get(f"{BASE_URL}/mapping", headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json(), 'primary'
    except Exception as e:
        print(f"[WARN] Primary API failed for mapping: {e}")
        if FALLBACK_BASE:
            try:
                response = requests.get(f"{FALLBACK_BASE}/mapping", headers=FALLBACK_HEADERS, timeout=30)
                response.raise_for_status()
                return response.json(), 'fallback'
            except Exception as fallback_error:
                print(f"[ERROR] Fallback API also failed: {fallback_error}")
        raise

def load_metadata_cache():
    """Load metadata from cache file"""
    global _metadata_cache, _cache_loaded
    
    if _cache_loaded:
        return _metadata_cache
    
    # Try to load from file
    if os.path.exists(METADATA_CACHE_FILE):
        try:
            with open(METADATA_CACHE_FILE, 'r', encoding='utf-8') as f:
                _metadata_cache = {int(k): v for k, v in json.load(f).items()}
            print(f"[METADATA] Loaded {len(_metadata_cache)} items from cache")
            _cache_loaded = True
            return _metadata_cache
        except Exception as e:
            print(f"[ERROR] Failed to load metadata cache: {e}")
    
    # If no cache, fetch from API
    return refresh_metadata_cache()

def refresh_metadata_cache():
    """Refresh metadata cache from API"""
    global _metadata_cache, _cache_loaded
    
    try:
        mapping_data, source = fetch_item_mapping()
        print(f"[METADATA] Fetching metadata from {source} API...")
        
        _metadata_cache = {}
        for item in mapping_data:
            item_id = int(item['id'])
            _metadata_cache[item_id] = {
                'name': item.get('name', f'Item {item_id}'),
                'buy_limit': item.get('limit', 0),  # Max units per 4h
                'members': item.get('members', True),
                'examine': item.get('examine', ''),
                'icon': item.get('icon', ''),
                'highalch': item.get('highalch', 0),
                'lowalch': item.get('lowalch', 0)
            }
        
        # Save to cache file
        try:
            with open(METADATA_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(_metadata_cache, f, indent=2)
            print(f"[METADATA] Cached {len(_metadata_cache)} items")
        except Exception as e:
            print(f"[WARN] Failed to save metadata cache: {e}")
        
        _cache_loaded = True
        return _metadata_cache
    except Exception as e:
        print(f"[ERROR] Failed to refresh metadata cache: {e}")
        return _metadata_cache

def get_item_meta(item_id: int) -> Optional[Dict]:
    """
    Get item metadata (name, buy_limit, etc.)
    
    Args:
        item_id: OSRS item ID
        
    Returns:
        Dict with keys: name, buy_limit, members, examine, icon, highalch, lowalch
        Returns None if item not found
    """
    if not _cache_loaded:
        load_metadata_cache()
    
    return _metadata_cache.get(item_id)

def get_item_name(item_id: int) -> str:
    """Get item name, fallback to 'Item {id}' if not found"""
    meta = get_item_meta(item_id)
    if meta:
        return meta['name']
    return f"Item {item_id}"

def get_buy_limit(item_id: int) -> int:
    """Get buy limit (max units per 4h), returns 0 if not found"""
    meta = get_item_meta(item_id)
    if meta:
        return meta.get('buy_limit', 0)
    return 0

# Initialize cache on module import
load_metadata_cache()

