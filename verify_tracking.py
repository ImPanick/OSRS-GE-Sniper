#!/usr/bin/env python3
"""
Verification script to test real-time GE tracking
"""

import requests
import sqlite3
import time
from datetime import datetime
import os

DB_PATH = os.path.join("backend", "utils", "history.db")
BASE = "https://prices.runescape.wiki/api/v1/osrs"
HEADERS = {"User-Agent": "OSRS-Sniper-Verification"}

def check_api():
    """Check API connectivity"""
    print("=" * 60)
    print("1. CHECKING OSRS WIKI API")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE}/latest", headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        item_count = len(data.get('data', {}))
        print(f"✓ API responding with {item_count:,} items")
        
        # Check a sample item
        sample_id = "2"  # Cannonball
        if sample_id in data.get('data', {}):
            item = data['data'][sample_id]
            print(f"  Sample item {sample_id}: low={item.get('low'):,}, high={item.get('high'):,}")
        return True
    except Exception as e:
        print(f"✗ API check failed: {e}")
        return False

def check_database():
    """Check database for recent activity"""
    print("\n" + "=" * 60)
    print("2. CHECKING DATABASE")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print(f"✗ Database not found: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices'")
        if not c.fetchone():
            print("✗ 'prices' table missing")
            conn.close()
            return False
        
        # Get stats
        c.execute("SELECT COUNT(*) FROM prices")
        total = c.fetchone()[0]
        print(f"✓ Database found: {total:,} total records")
        
        # Check recent activity
        current_time = int(time.time())
        c.execute("SELECT MAX(timestamp) FROM prices")
        latest_ts = c.fetchone()[0]
        
        if latest_ts:
            age_seconds = current_time - latest_ts
            age_minutes = age_seconds / 60
            print(f"✓ Most recent record: {age_minutes:.1f} minutes ago")
            
            if age_seconds < 300:
                print("  ✓ REAL-TIME: Updates within last 5 minutes")
            elif age_seconds < 600:
                print("  ⚠ RECENT: Updates within last 10 minutes")
            else:
                print("  ✗ STALE: No recent updates")
        
        # Show recent items
        print("\n  Last 5 records:")
        c.execute("""
            SELECT item_id, timestamp, low, high, volume 
            FROM prices 
            ORDER BY timestamp DESC 
            LIMIT 5
        """)
        for row in c.fetchall():
            item_id, ts, low, high, vol = row
            age = (current_time - ts) / 60
            print(f"    Item {item_id}: {low:,}-{high:,} GP, vol={vol:,} ({age:.1f}m ago)")
        
        conn.close()
        return True
    except Exception as e:
        print(f"✗ Database check failed: {e}")
        return False

def check_backend():
    """Check backend API"""
    print("\n" + "=" * 60)
    print("3. CHECKING BACKEND API")
    print("=" * 60)
    
    urls = ["http://localhost:5000", "http://127.0.0.1:5000"]
    for url in urls:
        try:
            response = requests.get(f"{url}/api/health", timeout=5)
            if response.status_code == 200:
                print(f"✓ Backend accessible at: {url}")
                
                # Check endpoints
                for endpoint in ["/api/top", "/api/dumps", "/api/spikes"]:
                    try:
                        r = requests.get(f"{url}{endpoint}", timeout=5)
                        if r.status_code == 200:
                            data = r.json()
                            print(f"  ✓ {endpoint}: {len(data)} items")
                    except:
                        pass
                return True
        except:
            continue
    
    print("⚠ Backend not accessible (may not be running)")
    return None

def monitor_updates():
    """Monitor for new database entries"""
    print("\n" + "=" * 60)
    print("4. MONITORING FOR UPDATES (30 seconds)")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print("✗ Database not found")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get initial max timestamp
        c.execute("SELECT MAX(timestamp) FROM prices")
        initial_ts = c.fetchone()[0] or 0
        
        print("Watching for new records...")
        start = time.time()
        updates = 0
        
        while time.time() - start < 30:
            c.execute("SELECT COUNT(*) FROM prices WHERE timestamp > ?", (initial_ts,))
            count = c.fetchone()[0]
            if count > updates:
                updates = count
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] +{count} new record(s)")
            time.sleep(2)
        
        if updates > 0:
            print(f"\n✓ TRACKING ACTIVE: {updates} new records in 30 seconds")
        else:
            print(f"\n✗ NO UPDATES: Polling thread may not be running")
        
        conn.close()
    except Exception as e:
        print(f"✗ Monitoring failed: {e}")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("OSRS GE TRACKING VERIFICATION")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    api_ok = check_api()
    db_ok = check_database()
    backend_ok = check_backend()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"API: {'✓' if api_ok else '✗'}")
    print(f"Database: {'✓' if db_ok else '✗'}")
    print(f"Backend: {'✓' if backend_ok else '⚠' if backend_ok is None else '✗'}")
    
    if db_ok:
        monitor_updates()
    
    print("\nDone!")
