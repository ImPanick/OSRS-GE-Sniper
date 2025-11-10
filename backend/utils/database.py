import sqlite3
from datetime import datetime
import os
import contextlib
import threading

# Use environment variable for DB path, fallback to default
DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'history.db'))

# Thread-local storage for database connections (connection per thread)
_local = threading.local()

def get_db_connection():
    """Get or create a thread-local database connection"""
    if not hasattr(_local, 'connection') or _local.connection is None:
        _local.connection = sqlite3.connect(
            DB_PATH,
            timeout=10.0,  # 10 second timeout for database locks
            check_same_thread=False  # Allow use across threads
        )
        _local.connection.row_factory = sqlite3.Row  # Return rows as dict-like objects
    return _local.connection

@contextlib.contextmanager
def db_transaction():
    """Context manager for database transactions with proper error handling"""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        # Don't close connection here - keep it for thread reuse
        pass

def init_db():
    """Initialize database with proper error handling"""
    try:
        with db_transaction() as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS prices
                         (item_id INTEGER, timestamp INTEGER, low INTEGER, high INTEGER, volume INTEGER)''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_time ON prices (timestamp)''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_item_time ON prices (item_id, timestamp)''')
    except sqlite3.Error as e:
        print(f"[ERROR] Database initialization failed: {e}")
        raise

def log_price(item_id, low, high, volume):
    """Log price data with proper error handling and transaction management"""
    try:
        with db_transaction() as conn:
            c = conn.cursor()
            ts = int(datetime.now().timestamp())
            c.execute("INSERT INTO prices VALUES (?,?,?,?,?)", (item_id, ts, low, high, volume))
            # Clean up old data (older than 7 days)
            week_ago = ts - 7*24*60*60
            c.execute("DELETE FROM prices WHERE timestamp < ?", (week_ago,))
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to log price for item {item_id}: {e}")
        # Don't raise - allow application to continue

def get_history(item_id, hours=24):
    """Get price history for an item with proper error handling"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        cutoff = int(datetime.now().timestamp()) - hours*3600
        c.execute("SELECT timestamp, low, high FROM prices WHERE item_id = ? AND timestamp > ? ORDER BY timestamp", 
                  (item_id, cutoff))
        data = c.fetchall()
        return [{"time": datetime.fromtimestamp(timestamp).strftime("%H:%M"), "low": low_price, "high": high_price} 
                for timestamp, low_price, high_price in data]
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to get history for item {item_id}: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Unexpected error getting history: {e}")
        return []

def get_price_historicals(item_id):
    """
    Get price historicals for an item:
    - 7d, 24h, 12h, 6h, 1h averages
    - Previous price (most recent before current)
    Returns dict with avg_7d, avg_24h, avg_12h, avg_6h, avg_1h, prev_price, prev_timestamp
    """
    historicals = {
        "avg_7d": None,
        "avg_24h": None,
        "avg_12h": None,
        "avg_6h": None,
        "avg_1h": None,
        "prev_price": None,
        "prev_timestamp": None
    }
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        current_time = int(datetime.now().timestamp())
        
        # Calculate averages for different time periods
        periods = [
            ("avg_7d", 7 * 24 * 3600),
            ("avg_24h", 24 * 3600),
            ("avg_12h", 12 * 3600),
            ("avg_6h", 6 * 3600),
            ("avg_1h", 1 * 3600)
        ]
        
        for key, seconds in periods:
            cutoff = current_time - seconds
            c.execute("""
                SELECT AVG((low + high) / 2.0) as avg_price 
                FROM prices 
                WHERE item_id = ? AND timestamp > ? AND timestamp < ?
            """, (item_id, cutoff, current_time))
            result = c.fetchone()
            if result and result[0] is not None:
                historicals[key] = int(result[0])
        
        # Get previous price (most recent before current, excluding the last entry)
        c.execute("""
            SELECT (low + high) / 2.0 as avg_price, timestamp
            FROM prices 
            WHERE item_id = ? AND timestamp < ?
            ORDER BY timestamp DESC
            LIMIT 1 OFFSET 1
        """, (item_id, current_time))
        prev_result = c.fetchone()
        if prev_result and prev_result[0] is not None:
            historicals["prev_price"] = int(prev_result[0])
            historicals["prev_timestamp"] = prev_result[1]
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to get price historicals for item {item_id}: {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error getting price historicals: {e}")
    
    return historicals