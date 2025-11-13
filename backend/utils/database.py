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
            
            # 5-minute snapshot table for dump engine
            c.execute('''CREATE TABLE IF NOT EXISTS ge_prices_5m
                         (item_id INTEGER, timestamp INTEGER, low INTEGER, high INTEGER, volume INTEGER,
                          PRIMARY KEY (item_id, timestamp))''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_5m_time ON ge_prices_5m (timestamp)''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_5m_item_time ON ge_prices_5m (item_id, timestamp)''')
            
            # Watchlist table
            c.execute('''CREATE TABLE IF NOT EXISTS watchlists
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          guild_id TEXT NOT NULL,
                          user_id TEXT,
                          item_id INTEGER NOT NULL,
                          item_name TEXT NOT NULL,
                          UNIQUE(guild_id, user_id, item_id))''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_watchlist_guild ON watchlists (guild_id)''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlists (guild_id, user_id)''')
            
            # Tier system tables
            c.execute('''CREATE TABLE IF NOT EXISTS tiers
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          name TEXT NOT NULL UNIQUE,
                          emoji TEXT NOT NULL,
                          min_score INTEGER NOT NULL,
                          max_score INTEGER NOT NULL,
                          tier_group TEXT NOT NULL)''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_tier_name ON tiers (name)''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_tier_score ON tiers (min_score, max_score)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS guild_tier_settings
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          guild_id TEXT NOT NULL,
                          tier_name TEXT NOT NULL,
                          discord_role_id TEXT,
                          enabled INTEGER NOT NULL DEFAULT 1,
                          UNIQUE(guild_id, tier_name),
                          FOREIGN KEY (tier_name) REFERENCES tiers(name))''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_guild_tier_guild ON guild_tier_settings (guild_id)''')
            c.execute('''CREATE INDEX IF NOT EXISTS idx_guild_tier_name ON guild_tier_settings (tier_name)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS guild_config
                         (guild_id TEXT PRIMARY KEY,
                          min_tier_name TEXT,
                          FOREIGN KEY (min_tier_name) REFERENCES tiers(name))''')
            
            # Seed tiers if table is empty
            seed_tiers(conn)
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

def get_recent_history(item_id, minutes=5):
    """
    Get recent price history for an item (last N minutes)
    Returns list of dicts with timestamp, low, high, volume
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        cutoff = int(datetime.now().timestamp()) - minutes * 60
        c.execute("""
            SELECT timestamp, low, high, volume
            FROM prices
            WHERE item_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 20
        """, (item_id, cutoff))
        
        rows = c.fetchall()
        return [
            {
                "timestamp": row[0],
                "time": datetime.fromtimestamp(row[0]).strftime("%Y-%m-%d %H:%M:%S"),
                "low": row[1],
                "high": row[2],
                "volume": row[3]
            }
            for row in rows
        ]
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to get recent history for item {item_id}: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Unexpected error getting recent history: {e}")
        return []

def seed_tiers(conn=None):
    """Seed tiers table with canonical tier definitions"""
    if conn is None:
        conn = get_db_connection()
    
    try:
        c = conn.cursor()
        # Check if tiers already exist
        c.execute("SELECT COUNT(*) FROM tiers")
        count = c.fetchone()[0]
        
        if count > 0:
            return  # Already seeded
        
        # Import tier definitions from dump_engine
        try:
            from .dump_engine import TIERS
        except ImportError:
            # Fallback tier definitions if import fails
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
        
        # Insert tiers
        for tier in TIERS:
            c.execute("""INSERT OR IGNORE INTO tiers (name, emoji, min_score, max_score, tier_group)
                          VALUES (?, ?, ?, ?, ?)""",
                      (tier["name"], tier["emoji"], tier["min"], tier["max"], tier["group"]))
        
        conn.commit()
        print(f"[+] Seeded {len(TIERS)} tiers into database")
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to seed tiers: {e}")
        conn.rollback()

def get_all_tiers():
    """Get all tiers from database"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, emoji, min_score, max_score, tier_group FROM tiers ORDER BY min_score")
        rows = c.fetchall()
        return [{
            "id": row[0],
            "name": row[1],
            "emoji": row[2],
            "min_score": row[3],
            "max_score": row[4],
            "group": row[5]
        } for row in rows]
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to get tiers: {e}")
        return []

def update_tier(tier_id, min_score=None, max_score=None):
    """Update tier score ranges"""
    try:
        with db_transaction() as conn:
            c = conn.cursor()
            updates = []
            params = []
            
            if min_score is not None:
                updates.append("min_score = ?")
                params.append(min_score)
            if max_score is not None:
                updates.append("max_score = ?")
                params.append(max_score)
            
            if not updates:
                return False
            
            params.append(tier_id)
            c.execute(f"UPDATE tiers SET {', '.join(updates)} WHERE id = ?", params)
            return c.rowcount > 0
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to update tier: {e}")
        return False

def get_guild_tier_settings(guild_id):
    """Get tier settings for a specific guild"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""SELECT tier_name, discord_role_id, enabled
                     FROM guild_tier_settings
                     WHERE guild_id = ?""", (guild_id,))
        rows = c.fetchall()
        return {row[0]: {"role_id": row[1], "enabled": bool(row[2])} for row in rows}
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to get guild tier settings: {e}")
        return {}

def update_guild_tier_setting(guild_id, tier_name, role_id=None, enabled=None):
    """Update or create guild tier setting"""
    try:
        with db_transaction() as conn:
            c = conn.cursor()
            # Check if setting exists
            c.execute("SELECT id FROM guild_tier_settings WHERE guild_id = ? AND tier_name = ?",
                     (guild_id, tier_name))
            existing = c.fetchone()
            
            if existing:
                # Update existing
                updates = []
                params = []
                if role_id is not None:
                    updates.append("discord_role_id = ?")
                    params.append(role_id)
                if enabled is not None:
                    updates.append("enabled = ?")
                    params.append(1 if enabled else 0)
                
                if updates:
                    params.append(guild_id)
                    params.append(tier_name)
                    c.execute(f"UPDATE guild_tier_settings SET {', '.join(updates)} WHERE guild_id = ? AND tier_name = ?", params)
            else:
                # Insert new
                c.execute("""INSERT INTO guild_tier_settings (guild_id, tier_name, discord_role_id, enabled)
                             VALUES (?, ?, ?, ?)""",
                         (guild_id, tier_name, role_id, 1 if enabled is None else (1 if enabled else 0)))
            return True
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to update guild tier setting: {e}")
        return False

def get_guild_config(guild_id):
    """Get guild configuration (min_tier_name)"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT min_tier_name FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = c.fetchone()
        return {"min_tier_name": row[0] if row else None}
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to get guild config: {e}")
        return {"min_tier_name": None}

def update_guild_config(guild_id, min_tier_name=None):
    """Update guild configuration"""
    try:
        with db_transaction() as conn:
            c = conn.cursor()
            # Check if config exists
            c.execute("SELECT guild_id FROM guild_config WHERE guild_id = ?", (guild_id,))
            existing = c.fetchone()
            
            if existing:
                if min_tier_name is not None:
                    c.execute("UPDATE guild_config SET min_tier_name = ? WHERE guild_id = ?",
                             (min_tier_name, guild_id))
            else:
                c.execute("INSERT INTO guild_config (guild_id, min_tier_name) VALUES (?, ?)",
                         (guild_id, min_tier_name))
            return True
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to update guild config: {e}")
        return False