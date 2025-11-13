#!/usr/bin/env python3
"""
5-Minute Dump Worker
- Runs dump engine cycle every 5 minutes (300 seconds)
- On start: runs immediately once
- Then sleeps 300 seconds in a loop
"""
import time
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
# In Docker: /app/utils/dump_worker.py -> add /app to path
# Locally: backend/utils/dump_worker.py -> add backend to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils.dump_engine import run_cycle
from utils.database import init_db

def main():
    """Main worker loop"""
    print(f"[DUMP_WORKER] Starting dump worker at {datetime.now().isoformat()}")
    
    # Initialize database (ensure tables exist)
    try:
        init_db()
        print("[DUMP_WORKER] Database initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
        sys.exit(1)
    
    # Run immediately on start
    print("[DUMP_WORKER] Running initial cycle...")
    try:
        run_cycle()
    except Exception as e:
        print(f"[ERROR] Initial cycle failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Then loop every 5 minutes (300 seconds)
    cycle_count = 1
    while True:
        try:
            print(f"[DUMP_WORKER] Sleeping 300 seconds before next cycle...")
            time.sleep(300)  # Sleep for 5 minutes
            
            cycle_count += 1
            print(f"[DUMP_WORKER] Starting cycle #{cycle_count} at {datetime.now().isoformat()}")
            run_cycle()
            
        except KeyboardInterrupt:
            print("\n[DUMP_WORKER] Shutting down gracefully...")
            break
        except Exception as e:
            print(f"[ERROR] Cycle #{cycle_count} failed: {e}")
            import traceback
            traceback.print_exc()
            # Continue running even if a cycle fails
            print("[DUMP_WORKER] Continuing to next cycle...")

if __name__ == "__main__":
    main()

