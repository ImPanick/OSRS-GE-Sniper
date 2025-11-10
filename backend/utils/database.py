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
    return [{"time": datetime.fromtimestamp(t).strftime("%H:%M"), "low": l, "high": h} for t,l,h in data]