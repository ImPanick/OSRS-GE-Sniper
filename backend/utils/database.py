import sqlite3
from datetime import datetime

DB_PATH = "history.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prices
                 (item_id INTEGER, timestamp INTEGER, low INTEGER, high INTEGER, volume INTEGER)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_time ON prices (timestamp)''')
    conn.commit()
    conn.close()

def log_price(item_id, low, high, volume):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ts = int(datetime.now().timestamp())
    c.execute("INSERT INTO prices VALUES (?,?,?,?,?)", (item_id, ts, low, high, volume))
    week_ago = ts - 7*24*60*60
    c.execute("DELETE FROM prices WHERE timestamp < ?", (week_ago,))
    conn.commit()
    conn.close()

def get_history(item_id, hours=24):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff = int(datetime.now().timestamp()) - hours*3600
    c.execute("SELECT timestamp, low, high FROM prices WHERE item_id = ? AND timestamp > ? ORDER BY timestamp", 
              (item_id, cutoff))
    data = c.fetchall()
    conn.close()
    return [{"time": datetime.fromtimestamp(timestamp).strftime("%H:%M"), "low": low_price, "high": high_price} 
            for timestamp, low_price, high_price in data]

def get_price_historicals(item_id):
    """
    Get price historicals for an item:
    - 7d, 24h, 12h, 6h, 1h averages
    - Previous price (most recent before current)
    Returns dict with avg_7d, avg_24h, avg_12h, avg_6h, avg_1h, prev_price, prev_timestamp
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    current_time = int(datetime.now().timestamp())
    
    historicals = {
        "avg_7d": None,
        "avg_24h": None,
        "avg_12h": None,
        "avg_6h": None,
        "avg_1h": None,
        "prev_price": None,
        "prev_timestamp": None
    }
    
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
    
    conn.close()
    return historicals