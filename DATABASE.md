# Database Configuration Guide

## Overview

The OSRS-GE-Sniper uses a hardened database layer with support for both PostgreSQL (Docker deployment) and SQLite (local development).

## Database Systems

### Docker Deployment (PostgreSQL)

In Docker deployments, the system uses **PostgreSQL 16** for reliable concurrent access across multiple services (backend, worker, cache-updater).

**Configuration:**
- Database service: `postgres` (defined in `docker/docker-compose.yml`)
- Default credentials (can be overridden via environment variables):
  - User: `osrs_sniper`
  - Password: `osrs_sniper_pass`
  - Database: `osrs_sniper`
- Connection URL format: `postgresql://user:pass@postgres:5432/osrs_sniper`

**Environment Variables:**
- `POSTGRES_USER` - Database user (default: `osrs_sniper`)
- `POSTGRES_PASSWORD` - Database password (default: `osrs_sniper_pass`)
- `POSTGRES_DB` - Database name (default: `osrs_sniper`)
- `POSTGRES_PORT` - External port mapping (default: `5432`)
- `DB_URL` - Full connection URL (auto-generated from above, or can be set directly)

**Connection Pooling:**
- Pool size: 10 connections
- Max overflow: 20 connections
- Connection recycling: 1 hour
- Pre-ping enabled: Yes (verifies connections before use)

### Local Development (SQLite)

For local development, the system falls back to SQLite if `DB_URL` is not set.

**Configuration:**
- Database file: `backend/utils/history.db` (default)
- Can be overridden via `DB_PATH` environment variable
- Connection URL format: `sqlite:///path/to/history.db`

**Note:** SQLite is suitable for development but not recommended for production deployments with multiple services due to concurrency limitations.

## Schema

The database includes the following tables with hardened constraints:

### `prices`
- Stores real-time price data
- Columns: `item_id`, `timestamp`, `low`, `high`, `volume`
- Indexes: `timestamp`, `(item_id, timestamp)`
- Retention: 7 days (automatic cleanup)

### `ge_prices_5m`
- Stores 5-minute snapshots for dump analysis
- Columns: `item_id`, `timestamp`, `low`, `high`, `volume`
- Primary Key: `(item_id, timestamp)` - prevents duplicates
- Indexes: `timestamp`, `(item_id, timestamp)`
- Retention: 7 days (automatic cleanup)

### `watchlists`
- User and guild watchlists
- Columns: `id`, `guild_id`, `user_id`, `item_id`, `item_name`
- Unique constraint: `(guild_id, user_id, item_id)`
- Indexes: `guild_id`, `(guild_id, user_id)`

### `tiers`
- Tier system definitions
- Columns: `id`, `name`, `emoji`, `min_score`, `max_score`, `tier_group`
- Unique constraint: `name`
- Check constraint: `min_score <= max_score`
- Indexes: `name`, `(min_score, max_score)`

### `guild_tier_settings`
- Per-guild tier configuration
- Columns: `id`, `guild_id`, `tier_name`, `discord_role_id`, `enabled`
- Unique constraint: `(guild_id, tier_name)`
- Foreign key: `tier_name` → `tiers(name)`
- Indexes: `guild_id`, `tier_name`

### `guild_config`
- Base guild configuration
- Columns: `guild_id` (PK), `min_tier_name`, `alert_channel_id`
- Foreign key: `min_tier_name` → `tiers(name)`

### `guild_alert_settings`
- Per-guild alert thresholds
- Columns: `guild_id` (PK), `min_margin_gp`, `min_score`, `enabled_tiers`, `max_alerts_per_interval`
- Check constraints:
  - `min_margin_gp >= 0`
  - `min_score >= 0`
  - `max_alerts_per_interval > 0`
- Foreign key: `guild_id` → `guild_config(guild_id)`

## Schema Initialization

The database schema is automatically created on first startup via `init_db()`. This function:

1. Creates all tables if they don't exist
2. Creates indexes for performance
3. Seeds the `tiers` table with default tier definitions
4. Handles migrations (e.g., adding new columns)

**No manual migration steps required** - the system handles schema setup automatically.

## Connection Management

### Thread Safety

- Uses SQLAlchemy's `scoped_session` for thread-safe session management
- Each thread gets its own database session
- Sessions are automatically closed after use

### Transaction Management

All write operations use transactions via the `db_transaction()` context manager:

```python
with db_transaction() as session:
    # Database operations
    # Automatically commits on success, rolls back on error
```

### Bulk Operations

Bulk inserts are optimized with batch processing:

```python
from utils.database import bulk_insert_snapshots

snapshot_data = [
    {"item_id": 1, "timestamp": 1234567890, "low": 100, "high": 200, "volume": 50},
    # ... more records
]

bulk_insert_snapshots(snapshot_data, table_name='ge_prices_5m', batch_size=1000)
```

## Data Retention

### Automatic Cleanup

- `prices` table: Automatically prunes data older than 7 days
- `ge_prices_5m` table: Automatically prunes data older than 7 days

### Manual Pruning

Use the admin API endpoint to manually prune old data:

```bash
POST /api/admin/db_prune
Headers: X-Admin-Key: <your-admin-key>
Body: {
  "table": "ge_prices_5m",
  "retention_days": 7
}
```

## Health Monitoring

### Health Check Endpoint

Monitor database health via the admin API:

```bash
GET /api/admin/db_health
Headers: X-Admin-Key: <your-admin-key>
```

**Response:**
```json
{
  "status": "healthy",
  "db_type": "PostgreSQL",
  "table_counts": {
    "prices": 12345,
    "ge_prices_5m": 67890,
    "watchlists": 10,
    "tiers": 10,
    "guild_tier_settings": 5,
    "guild_config": 3,
    "guild_alert_settings": 3
  },
  "connection_pool": {
    "size": 10,
    "checked_in": 8,
    "checked_out": 2,
    "overflow": 0
  }
}
```

## Migration from SQLite to PostgreSQL

If you're migrating from an existing SQLite database:

1. **Export data from SQLite:**
   ```bash
   sqlite3 history.db .dump > backup.sql
   ```

2. **Start PostgreSQL service:**
   ```bash
   docker compose up -d postgres
   ```

3. **Import data (manual process):**
   - The schema will auto-create on first startup
   - You may need to manually migrate data using `pgloader` or similar tools
   - Or use SQLAlchemy's migration tools if you add Alembic

4. **Update environment:**
   - Set `DB_URL=postgresql://osrs_sniper:osrs_sniper_pass@postgres:5432/osrs_sniper`
   - Restart services

## Troubleshooting

### Connection Issues

**Problem:** Services can't connect to PostgreSQL

**Solutions:**
1. Check PostgreSQL is running: `docker compose ps postgres`
2. Check logs: `docker compose logs postgres`
3. Verify `DB_URL` environment variable is set correctly
4. Ensure services wait for PostgreSQL (entrypoint scripts handle this)

### Locking Issues (SQLite)

**Problem:** Database is locked errors

**Solutions:**
1. Migrate to PostgreSQL (recommended for production)
2. Ensure only one service accesses SQLite file
3. Check file permissions

### Schema Errors

**Problem:** Table doesn't exist or column errors

**Solutions:**
1. Check `init_db()` is called on startup
2. Review logs for initialization errors
3. Manually run `init_db()` if needed:
   ```python
   from utils.database import init_db
   init_db()
   ```

### Performance Issues

**Problem:** Slow queries or connection pool exhaustion

**Solutions:**
1. Check connection pool status via `/api/admin/db_health`
2. Increase pool size in `database.py` if needed
3. Add indexes for frequently queried columns
4. Review query patterns and optimize

## Best Practices

1. **Always use transactions** for write operations
2. **Use bulk inserts** for large datasets
3. **Monitor connection pool** via health endpoint
4. **Set appropriate retention periods** to control database size
5. **Use PostgreSQL in production** - SQLite is for development only
6. **Backup regularly** - PostgreSQL data is in Docker volume `postgres_data`

## Backup and Restore

### Backup PostgreSQL

```bash
# Backup database
docker compose exec postgres pg_dump -U osrs_sniper osrs_sniper > backup.sql

# Or backup entire volume
docker run --rm -v osrs-sniper_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data
```

### Restore PostgreSQL

```bash
# Restore from SQL dump
docker compose exec -T postgres psql -U osrs_sniper osrs_sniper < backup.sql

# Or restore entire volume
docker run --rm -v osrs-sniper_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

