"""
Database layer with SQLAlchemy for PostgreSQL (Docker) and SQLite (local dev)
- Supports connection pooling for concurrent access
- Hardened schema with proper constraints
- Transactional integrity for all write operations
"""
from datetime import datetime
import os
import contextlib
import json
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, BigInteger, Boolean, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

# Database URL from environment, fallback to SQLite for local dev
DB_URL = os.getenv('DB_URL')
if not DB_URL:
    # Fallback to SQLite for local development
    DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'history.db'))
    DB_URL = f'sqlite:///{DB_PATH}'

# Determine if we're using Postgres or SQLite
USE_POSTGRES = DB_URL.startswith('postgresql://') or DB_URL.startswith('postgres://')

# Create engine with connection pooling
if USE_POSTGRES:
    # Postgres: use connection pooling for concurrent access
    engine = create_engine(
        DB_URL,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,   # Recycle connections after 1 hour
        echo=False
    )
else:
    # SQLite: single connection pool for file-based DB
    engine = create_engine(
        DB_URL,
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        connect_args={'check_same_thread': False, 'timeout': 10.0},
        echo=False
    )

# Thread-safe session factory
SessionLocal = scoped_session(sessionmaker(bind=engine, autocommit=False, autoflush=False))

# Metadata for schema management
metadata = MetaData()

# Table definitions with hardened schema
prices_table = Table(
    'prices',
    metadata,
    Column('item_id', Integer, nullable=False),
    Column('timestamp', BigInteger, nullable=False),
    Column('low', Integer, nullable=False),
    Column('high', Integer, nullable=False),
    Column('volume', Integer, nullable=False, default=0),
    Index('idx_time', 'timestamp'),
    Index('idx_item_time', 'item_id', 'timestamp')
)

ge_prices_5m_table = Table(
    'ge_prices_5m',
    metadata,
    Column('item_id', Integer, nullable=False),
    Column('timestamp', BigInteger, nullable=False),
    Column('low', Integer, nullable=False),
    Column('high', Integer, nullable=False),
    Column('volume', Integer, nullable=False, default=0),
    UniqueConstraint('item_id', 'timestamp', name='uq_ge_prices_5m_item_timestamp'),
    Index('idx_5m_time', 'timestamp'),
    Index('idx_5m_item_time', 'item_id', 'timestamp')
)

watchlists_table = Table(
    'watchlists',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('guild_id', String(255), nullable=False),
    Column('user_id', String(255), nullable=True),
    Column('item_id', Integer, nullable=False),
    Column('item_name', String(255), nullable=False),
    UniqueConstraint('guild_id', 'user_id', 'item_id', name='uq_watchlist_guild_user_item'),
    Index('idx_watchlist_guild', 'guild_id'),
    Index('idx_watchlist_user', 'guild_id', 'user_id')
)

tiers_table = Table(
    'tiers',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('name', String(50), nullable=False, unique=True),
    Column('emoji', String(20), nullable=False),
    Column('min_score', Integer, nullable=False),
    Column('max_score', Integer, nullable=False),
    Column('tier_group', String(50), nullable=False),
    Index('idx_tier_name', 'name'),
    Index('idx_tier_score', 'min_score', 'max_score'),
    CheckConstraint('min_score <= max_score', name='chk_tier_score_range')
)

guild_tier_settings_table = Table(
    'guild_tier_settings',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('guild_id', String(255), nullable=False),
    Column('tier_name', String(50), nullable=False),
    Column('discord_role_id', String(255), nullable=True),
    Column('enabled', Boolean, nullable=False, default=True),
    UniqueConstraint('guild_id', 'tier_name', name='uq_guild_tier_guild_name'),
    Index('idx_guild_tier_guild', 'guild_id'),
    Index('idx_guild_tier_name', 'tier_name')
)

guild_config_table = Table(
    'guild_config',
    metadata,
    Column('guild_id', String(255), primary_key=True, nullable=False),
    Column('min_tier_name', String(50), nullable=True),
    Column('alert_channel_id', String(255), nullable=True)
)

guild_alert_settings_table = Table(
    'guild_alert_settings',
    metadata,
    Column('guild_id', String(255), primary_key=True, nullable=False),
    Column('min_margin_gp', Integer, nullable=False, default=0),
    Column('min_score', Integer, nullable=False, default=0),
    Column('enabled_tiers', String(1000), nullable=False, default='[]'),  # JSON array as string
    Column('max_alerts_per_interval', Integer, nullable=False, default=1),
    CheckConstraint('min_margin_gp >= 0', name='chk_min_margin_gp'),
    CheckConstraint('min_score >= 0', name='chk_min_score'),
    CheckConstraint('max_alerts_per_interval > 0', name='chk_max_alerts')
)

def get_db_session():
    """Get a database session (thread-safe)"""
    return SessionLocal()

@contextlib.contextmanager
def db_transaction():
    """Context manager for database transactions with proper error handling"""
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def init_db():
    """Initialize database with proper error handling and schema creation"""
    try:
        # Create all tables if they don't exist
        metadata.create_all(engine, checkfirst=True)
        
        # Seed tiers if table is empty
        with db_transaction() as session:
            count = session.execute(text("SELECT COUNT(*) FROM tiers")).scalar()
            if count == 0:
                seed_tiers(session)
        
        print(f"[+] Database initialized successfully (using {'PostgreSQL' if USE_POSTGRES else 'SQLite'})")
    except SQLAlchemyError as e:
        print(f"[ERROR] Database initialization failed: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error during database initialization: {e}")
        raise

def log_price(item_id, low, high, volume):
    """Log price data with proper error handling and transaction management"""
    try:
        with db_transaction() as session:
            ts = int(datetime.now().timestamp())
            session.execute(
                text("INSERT INTO prices (item_id, timestamp, low, high, volume) VALUES (:item_id, :ts, :low, :high, :volume)"),
                {"item_id": item_id, "ts": ts, "low": low, "high": high, "volume": volume}
            )
            # Clean up old data (older than 7 days)
            week_ago = ts - 7 * 24 * 60 * 60
            session.execute(
                text("DELETE FROM prices WHERE timestamp < :week_ago"),
                {"week_ago": week_ago}
            )
    except SQLAlchemyError:
        print(f"[ERROR] Failed to log price for item {item_id}")
        # Don't raise - allow application to continue

def get_history(item_id, hours=24):
    """Get price history for an item with proper error handling"""
    try:
        session = get_db_session()
        try:
            cutoff = int(datetime.now().timestamp()) - hours * 3600
            result = session.execute(
                text("SELECT timestamp, low, high FROM prices WHERE item_id = :item_id AND timestamp > :cutoff ORDER BY timestamp"),
                {"item_id": item_id, "cutoff": cutoff}
            )
            data = result.fetchall()
            return [{"time": datetime.fromtimestamp(timestamp).strftime("%H:%M"), "low": low_price, "high": high_price} 
                    for timestamp, low_price, high_price in data]
        finally:
            session.close()
    except SQLAlchemyError as e:
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
        session = get_db_session()
        try:
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
                result = session.execute(
                    text("""
                        SELECT AVG((low + high) / 2.0) as avg_price 
                        FROM prices 
                        WHERE item_id = :item_id AND timestamp > :cutoff AND timestamp < :current_time
                    """),
                    {"item_id": item_id, "cutoff": cutoff, "current_time": current_time}
                )
                row = result.fetchone()
                if row and row[0] is not None:
                    historicals[key] = int(row[0])
            
            # Get previous price (most recent before current, excluding the last entry)
            result = session.execute(
                text("""
                    SELECT (low + high) / 2.0 as avg_price, timestamp
                    FROM prices 
                    WHERE item_id = :item_id AND timestamp < :current_time
                    ORDER BY timestamp DESC
                    LIMIT 1 OFFSET 1
                """),
                {"item_id": item_id, "current_time": current_time}
            )
            prev_row = result.fetchone()
            if prev_row and prev_row[0] is not None:
                historicals["prev_price"] = int(prev_row[0])
                historicals["prev_timestamp"] = prev_row[1]
        finally:
            session.close()
    except SQLAlchemyError as e:
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
        session = get_db_session()
        try:
            cutoff = int(datetime.now().timestamp()) - minutes * 60
            result = session.execute(
                text("""
                    SELECT timestamp, low, high, volume
                    FROM prices
                    WHERE item_id = :item_id AND timestamp > :cutoff
                    ORDER BY timestamp DESC
                    LIMIT 20
                """),
                {"item_id": item_id, "cutoff": cutoff}
            )
            
            rows = result.fetchall()
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
        finally:
            session.close()
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to get recent history for item {item_id}: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] Unexpected error getting recent history: {e}")
        return []

def seed_tiers(session=None):
    """Seed tiers table with canonical tier definitions"""
    if session is None:
        session = get_db_session()
        should_close = True
    else:
        should_close = False
    
    try:
        # Check if tiers already exist
        count = session.execute(text("SELECT COUNT(*) FROM tiers")).scalar()
        
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
        
        # Insert tiers (use ON CONFLICT for Postgres, INSERT OR IGNORE for SQLite)
        if USE_POSTGRES:
            insert_stmt = text("""
                INSERT INTO tiers (name, emoji, min_score, max_score, tier_group)
                VALUES (:name, :emoji, :min_score, :max_score, :tier_group)
                ON CONFLICT (name) DO NOTHING
            """)
        else:
            insert_stmt = text("""
                INSERT OR IGNORE INTO tiers (name, emoji, min_score, max_score, tier_group)
                VALUES (:name, :emoji, :min_score, :max_score, :tier_group)
            """)
        
        for tier in TIERS:
            session.execute(insert_stmt, {
                "name": tier["name"],
                "emoji": tier["emoji"],
                "min_score": tier["min"],
                "max_score": tier["max"],
                "tier_group": tier["group"]
            })
        
        if should_close:
            session.commit()
            session.close()
        print(f"[+] Seeded {len(TIERS)} tiers into database")
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to seed tiers: {e}")
        if should_close:
            session.rollback()
            session.close()
        else:
            raise

def get_all_tiers():
    """Get all tiers from database"""
    try:
        session = get_db_session()
        try:
            result = session.execute(
                text("SELECT id, name, emoji, min_score, max_score, tier_group FROM tiers ORDER BY min_score")
            )
            rows = result.fetchall()
            return [{
                "id": row[0],
                "name": row[1],
                "emoji": row[2],
                "min_score": row[3],
                "max_score": row[4],
                "group": row[5]
            } for row in rows]
        finally:
            session.close()
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to get tiers: {e}")
        return []

def update_tier(tier_id, min_score=None, max_score=None):
    """Update tier score ranges"""
    try:
        with db_transaction() as session:
            updates = []
            params = {"tier_id": tier_id}
            
            if min_score is not None:
                updates.append("min_score = :min_score")
                params["min_score"] = min_score
            if max_score is not None:
                updates.append("max_score = :max_score")
                params["max_score"] = max_score
            
            if not updates:
                return False
            
            result = session.execute(
                text(f"UPDATE tiers SET {', '.join(updates)} WHERE id = :tier_id"),
                params
            )
            return result.rowcount > 0
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to update tier: {e}")
        return False

def get_guild_tier_settings(guild_id):
    """Get tier settings for a specific guild"""
    try:
        session = get_db_session()
        try:
            result = session.execute(
                text("SELECT tier_name, discord_role_id, enabled FROM guild_tier_settings WHERE guild_id = :guild_id"),
                {"guild_id": guild_id}
            )
            rows = result.fetchall()
            return {row[0]: {"role_id": row[1], "enabled": bool(row[2])} for row in rows}
        finally:
            session.close()
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to get guild tier settings: {e}")
        return {}

def update_guild_tier_setting(guild_id, tier_name, role_id=None, enabled=None):
    """Update or create guild tier setting"""
    try:
        with db_transaction() as session:
            # Check if setting exists
            result = session.execute(
                text("SELECT id FROM guild_tier_settings WHERE guild_id = :guild_id AND tier_name = :tier_name"),
                {"guild_id": guild_id, "tier_name": tier_name}
            )
            existing = result.fetchone()
            
            if existing:
                # Update existing
                updates = []
                params = {"guild_id": guild_id, "tier_name": tier_name}
                if role_id is not None:
                    updates.append("discord_role_id = :role_id")
                    params["role_id"] = role_id
                if enabled is not None:
                    updates.append("enabled = :enabled")
                    params["enabled"] = enabled
                
                if updates:
                    session.execute(
                        text(f"UPDATE guild_tier_settings SET {', '.join(updates)} WHERE guild_id = :guild_id AND tier_name = :tier_name"),
                        params
                    )
            else:
                # Insert new
                session.execute(
                    text("INSERT INTO guild_tier_settings (guild_id, tier_name, discord_role_id, enabled) VALUES (:guild_id, :tier_name, :role_id, :enabled)"),
                    {
                        "guild_id": guild_id,
                        "tier_name": tier_name,
                        "role_id": role_id,
                        "enabled": 1 if enabled is None else (1 if enabled else 0)
                    }
                )
            return True
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to update guild tier setting: {e}")
        return False

def get_guild_config(guild_id):
    """Get guild configuration (min_tier_name, alert_channel_id)"""
    try:
        session = get_db_session()
        try:
            result = session.execute(
                text("SELECT min_tier_name, alert_channel_id FROM guild_config WHERE guild_id = :guild_id"),
                {"guild_id": guild_id}
            )
            row = result.fetchone()
            if row:
                return {
                    "min_tier_name": row[0],
                    "alert_channel_id": row[1]
                }
            return {"min_tier_name": None, "alert_channel_id": None}
        finally:
            session.close()
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to get guild config: {e}")
        return {"min_tier_name": None, "alert_channel_id": None}

def update_guild_config(guild_id, min_tier_name=None, alert_channel_id=None):
    """Update guild configuration"""
    try:
        with db_transaction() as session:
            # Check if config exists
            result = session.execute(
                text("SELECT guild_id FROM guild_config WHERE guild_id = :guild_id"),
                {"guild_id": guild_id}
            )
            existing = result.fetchone()
            
            if existing:
                updates = []
                params = {"guild_id": guild_id}
                if min_tier_name is not None:
                    updates.append("min_tier_name = :min_tier_name")
                    params["min_tier_name"] = min_tier_name
                if alert_channel_id is not None:
                    updates.append("alert_channel_id = :alert_channel_id")
                    params["alert_channel_id"] = alert_channel_id
                
                if updates:
                    session.execute(
                        text(f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id = :guild_id"),
                        params
                    )
            else:
                session.execute(
                    text("INSERT INTO guild_config (guild_id, min_tier_name, alert_channel_id) VALUES (:guild_id, :min_tier_name, :alert_channel_id)"),
                    {"guild_id": guild_id, "min_tier_name": min_tier_name, "alert_channel_id": alert_channel_id}
                )
            return True
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to update guild config: {e}")
        return False

def get_guild_alert_settings(guild_id):
    """Get alert settings for a specific guild"""
    try:
        session = get_db_session()
        try:
            result = session.execute(
                text("SELECT min_margin_gp, min_score, enabled_tiers, max_alerts_per_interval FROM guild_alert_settings WHERE guild_id = :guild_id"),
                {"guild_id": guild_id}
            )
            row = result.fetchone()
            
            if row:
                enabled_tiers = json.loads(row[2]) if row[2] else []
                return {
                    "min_margin_gp": row[0] if row[0] is not None else 0,
                    "min_score": row[1] if row[1] is not None else 0,
                    "enabled_tiers": enabled_tiers,
                    "max_alerts_per_interval": row[3] if row[3] is not None else 1
                }
            else:
                # Return defaults if no settings exist
                return {
                    "min_margin_gp": 0,
                    "min_score": 0,
                    "enabled_tiers": [],
                    "max_alerts_per_interval": 1
                }
        finally:
            session.close()
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to get guild alert settings: {e}")
        return {
            "min_margin_gp": 0,
            "min_score": 0,
            "enabled_tiers": [],
            "max_alerts_per_interval": 1
        }
    except Exception as e:
        print(f"[ERROR] Unexpected error getting alert settings: {e}")
        return {
            "min_margin_gp": 0,
            "min_score": 0,
            "enabled_tiers": [],
            "max_alerts_per_interval": 1
        }

def update_guild_alert_settings(guild_id, min_margin_gp=None, min_score=None, enabled_tiers=None, max_alerts_per_interval=None):
    """Update or create guild alert settings"""
    try:
        with db_transaction() as session:
            # Check if settings exist
            result = session.execute(
                text("SELECT guild_id FROM guild_alert_settings WHERE guild_id = :guild_id"),
                {"guild_id": guild_id}
            )
            existing = result.fetchone()
            
            if existing:
                # Update existing
                updates = []
                params = {"guild_id": guild_id}
                if min_margin_gp is not None:
                    updates.append("min_margin_gp = :min_margin_gp")
                    params["min_margin_gp"] = min_margin_gp
                if min_score is not None:
                    updates.append("min_score = :min_score")
                    params["min_score"] = min_score
                if enabled_tiers is not None:
                    updates.append("enabled_tiers = :enabled_tiers")
                    params["enabled_tiers"] = json.dumps(enabled_tiers)
                if max_alerts_per_interval is not None:
                    updates.append("max_alerts_per_interval = :max_alerts_per_interval")
                    params["max_alerts_per_interval"] = max_alerts_per_interval
                
                if updates:
                    session.execute(
                        text(f"UPDATE guild_alert_settings SET {', '.join(updates)} WHERE guild_id = :guild_id"),
                        params
                    )
            else:
                # Insert new with provided values or defaults
                min_margin_gp_val = min_margin_gp if min_margin_gp is not None else 0
                min_score_val = min_score if min_score is not None else 0
                enabled_tiers_val = json.dumps(enabled_tiers) if enabled_tiers is not None else '[]'
                max_alerts_val = max_alerts_per_interval if max_alerts_per_interval is not None else 1
                
                session.execute(
                    text("INSERT INTO guild_alert_settings (guild_id, min_margin_gp, min_score, enabled_tiers, max_alerts_per_interval) VALUES (:guild_id, :min_margin_gp, :min_score, :enabled_tiers, :max_alerts_per_interval)"),
                    {
                        "guild_id": guild_id,
                        "min_margin_gp": min_margin_gp_val,
                        "min_score": min_score_val,
                        "enabled_tiers": enabled_tiers_val,
                        "max_alerts_per_interval": max_alerts_val
                    }
                )
            return True
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to update guild alert settings: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error updating alert settings: {e}")
        return False

def get_unified_guild_config(guild_id):
    """Get unified guild configuration combining all settings"""
    try:
        # Get base config
        guild_config = get_guild_config(guild_id)
        
        # Get alert settings
        alert_settings = get_guild_alert_settings(guild_id)
        
        # Get tier settings
        tier_settings = get_guild_tier_settings(guild_id)
        
        # Build role_ids_per_tier mapping
        role_ids_per_tier = {}
        for tier_name, setting in tier_settings.items():
            if setting.get("role_id"):
                role_ids_per_tier[tier_name] = setting.get("role_id")
        
        # Combine into unified config
        unified = {
            "alert_channel_id": guild_config.get("alert_channel_id"),
            "enabled_tiers": alert_settings.get("enabled_tiers", []),
            "min_score": alert_settings.get("min_score", 0),
            "min_margin_gp": alert_settings.get("min_margin_gp", 0),
            "role_ids_per_tier": role_ids_per_tier,
            "min_tier_name": guild_config.get("min_tier_name"),
            "max_alerts_per_interval": alert_settings.get("max_alerts_per_interval", 1)
        }
        
        return unified
    except Exception as e:
        print(f"[ERROR] Failed to get unified guild config: {e}")
        # Return defaults
        return {
            "alert_channel_id": None,
            "enabled_tiers": [],
            "min_score": 0,
            "min_margin_gp": 0,
            "role_ids_per_tier": {},
            "min_tier_name": None,
            "max_alerts_per_interval": 1
        }

def bulk_insert_snapshots(snapshot_data, table_name='ge_prices_5m', batch_size=1000):
    """
    Bulk insert snapshots with optimized batch processing
    
    Args:
        snapshot_data: List of dicts with keys: item_id, timestamp, low, high, volume
        table_name: Table to insert into ('ge_prices_5m' or 'prices')
        batch_size: Number of records per transaction batch
    """
    if not snapshot_data:
        return
    
    try:
        # Process in batches
        for i in range(0, len(snapshot_data), batch_size):
            batch = snapshot_data[i:i + batch_size]
            
            with db_transaction() as session:
                if USE_POSTGRES:
                    # Postgres: use INSERT ... ON CONFLICT for upsert
                    if table_name == 'ge_prices_5m':
                        stmt = text("""
                            INSERT INTO ge_prices_5m (item_id, timestamp, low, high, volume)
                            VALUES (:item_id, :timestamp, :low, :high, :volume)
                            ON CONFLICT (item_id, timestamp) DO UPDATE SET
                                low = EXCLUDED.low,
                                high = EXCLUDED.high,
                                volume = EXCLUDED.volume
                        """)
                    else:
                        stmt = text("""
                            INSERT INTO prices (item_id, timestamp, low, high, volume)
                            VALUES (:item_id, :timestamp, :low, :high, :volume)
                        """)
                else:
                    # SQLite: use INSERT OR REPLACE
                    if table_name == 'ge_prices_5m':
                        stmt = text("""
                            INSERT OR REPLACE INTO ge_prices_5m (item_id, timestamp, low, high, volume)
                            VALUES (:item_id, :timestamp, :low, :high, :volume)
                        """)
                    else:
                        stmt = text("""
                            INSERT INTO prices (item_id, timestamp, low, high, volume)
                            VALUES (:item_id, :timestamp, :low, :high, :volume)
                        """)
                
                session.execute(stmt, batch)
                
                # Clean up old data (older than 7 days) - only once per batch
                if i == 0:
                    week_ago = int(datetime.now().timestamp()) - 7 * 24 * 60 * 60
                    session.execute(
                        text(f"DELETE FROM {table_name} WHERE timestamp < :week_ago"),
                        {"week_ago": week_ago}
                    )
        
        print(f"[+] Bulk inserted {len(snapshot_data)} records into {table_name}")
    except SQLAlchemyError as e:
        print(f"[ERROR] Bulk insert failed: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error during bulk insert: {e}")
        raise

def get_db_connection():
    """
    Legacy compatibility function - returns a raw connection for code that still uses it
    Note: New code should use get_db_session() instead
    """
    return engine.connect()

def get_db_health():
    """
    Get database health status
    Returns dict with:
    - status: 'healthy' or 'unhealthy'
    - db_type: 'PostgreSQL' or 'SQLite'
    - table_counts: dict of table name -> row count
    - connection_pool: pool status info
    """
    health = {
        "status": "unhealthy",
        "db_type": "PostgreSQL" if USE_POSTGRES else "SQLite",
        "table_counts": {},
        "connection_pool": {},
        "error": None
    }
    
    try:
        session = get_db_session()
        try:
            # Test connection
            session.execute(text("SELECT 1"))
            
            # Get table counts
            tables = ['prices', 'ge_prices_5m', 'watchlists', 'tiers', 'guild_tier_settings', 
                     'guild_config', 'guild_alert_settings']
            for table in tables:
                try:
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    health["table_counts"][table] = result.scalar()
                except Exception:
                    health["table_counts"][table] = None
            
            # Get connection pool info
            pool = engine.pool
            health["connection_pool"] = {
                "size": pool.size() if hasattr(pool, 'size') else None,
                "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else None,
                "checked_out": pool.checkedout() if hasattr(pool, 'checkedout') else None,
                "overflow": pool.overflow() if hasattr(pool, 'overflow') else None
            }
            
            health["status"] = "healthy"
        finally:
            session.close()
    except Exception as e:
        health["error"] = str(e)
        health["status"] = "unhealthy"
    
    return health

def prune_old_data(table_name, retention_days=7):
    """
    Prune old data from a table based on retention period
    
    Args:
        table_name: Name of table to prune
        retention_days: Number of days to retain (default 7)
    
    Returns:
        Number of rows deleted
    """
    try:
        with db_transaction() as session:
            cutoff = int(datetime.now().timestamp()) - retention_days * 24 * 60 * 60
            result = session.execute(
                text(f"DELETE FROM {table_name} WHERE timestamp < :cutoff"),
                {"cutoff": cutoff}
            )
            deleted = result.rowcount
            return deleted
    except SQLAlchemyError as e:
        print(f"[ERROR] Failed to prune old data from {table_name}: {e}")
        return 0
