#!/usr/bin/env python3
# backend/utils/cache_updater.py
"""
OSRS Item Cache Auto-Updater
- Pulls full item mapping from prices.runescape.wiki API
- Updates item_cache.json every 6 hours
- Fallback to existing cache on API failure
- Logs cache health to console
"""

import requests
import json
import time
import os
from datetime import datetime

BASE_URL = "https://prices.runescape.wiki/api/v1/osrs/mapping"
# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "item_cache.json")
USER_AGENT = "OSRS-Sniper-CacheUpdater/1.0"
UPDATE_INTERVAL = 6 * 60 * 60  # 6 hours in seconds

def fetch_item_mapping():
    """Pull fresh item mapping from API"""
    headers = {"User-Agent": USER_AGENT}
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching item mapping...")
        response = requests.get(BASE_URL, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Build id -> name mapping
        item_map = {}
        for item in data:
            item_id = str(item['id'])
            item_name = item['name'].replace(' ', '_')  # Wiki-friendly
            item_map[item_id] = item_name
        
        print(f"✅ Cached {len(item_map)} items")
        return item_map
        
    except requests.RequestException as e:
        print(f"❌ API fetch failed: {e}")
        return None

def save_cache(item_map):
    """Save mapping to JSON file"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(item_map, f, indent=2)
        print(f"💾 Cache saved to {CACHE_FILE}")
        return True
    except Exception as e:
        print(f"❌ Cache save failed: {e}")
        return False

def load_existing_cache():
    """Load current cache as fallback"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
            print(f"📂 Loaded existing cache: {len(cache)} items")
            return cache
        except Exception as e:
            print(f"❌ Existing cache corrupt: {e}")
    return {}

def update_cache():
    """Main update function"""
    print("=" * 50)
    print(f"OSRS ITEM CACHE UPDATER — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Try fresh fetch
    item_map = fetch_item_mapping()
    
    # Fallback to existing if fetch fails
    if not item_map:
        item_map = load_existing_cache()
    
    # Save if we have data
    if item_map:
        success = save_cache(item_map)
        if success:
            print(f"🎯 Cache update complete — {len(item_map)} items ready")
        else:
            print("⚠️  Cache failed to save — using existing")
    else:
        print("💀 NO CACHE AVAILABLE — sniper will show 'Item XXXX'")
    
    print("=" * 50)
    return item_map

def main():
    """Run once or in loop"""
    if len(os.sys.argv) > 1 and os.sys.argv[1] == "--once":
        update_cache()
    else:
        print("🚀 Starting auto-cache updater (6h intervals)")
        while True:
            update_cache()
            print(f"⏳ Sleeping {UPDATE_INTERVAL//3600}h until next update...")
            time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()