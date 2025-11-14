"""
API routes for dumps, spikes, tiers, and watchlist

NOTE: This module defines JSON APIs only. UI is handled exclusively by the Next.js frontend.
"""
from flask import Blueprint, jsonify, request
from utils.shared import get_item_lock, get_item_data
from utils.database import get_db_session, db_transaction, get_recent_history, get_unified_guild_config
from sqlalchemy import text
from utils.item_metadata import get_item_meta, get_buy_limit
from security import rate_limit, validate_json_payload, sanitize_guild_id, require_admin_key
import os

# Check if using Postgres
USE_POSTGRES = os.getenv('DB_URL', '').startswith('postgresql://') or os.getenv('DB_URL', '').startswith('postgres://')

bp = Blueprint('api_dumps', __name__, url_prefix='/api')

@bp.route('/dumps')
@rate_limit(max_requests=200, window=60)
def api_dumps():
    """
    Get dump opportunities using the dump engine with tier system.
    
    This endpoint returns true dump opportunities (oversupply events) detected
    by analyzing 5-minute price snapshots from prices.runescape.wiki.
    
    Query Parameters:
        guild_id (str, optional): Filter opportunities based on guild configuration:
            - Only includes items with score >= guild's min_score
            - Only includes items with margin_gp >= guild's min_margin_gp
            - Only includes items whose tier is in guild's enabled_tiers
        tier (str, optional): Filter by tier name (iron, copper, bronze, silver, gold, 
                              platinum, ruby, sapphire, emerald, diamond)
        group (str, optional): Filter by tier group (metals, gems)
        special (str, optional): Filter by special flags:
            - slow_buy: Items with slow buy speed (<50% of limit in 5 min)
            - one_gp_dump: Items that dropped to 1 GP
            - super: Platinum tier or higher (score >= 51)
        limit (int, optional): Maximum number of results to return
    
    Returns:
        JSON array of dump opportunities, each containing:
        - id (int): OSRS item ID
        - name (str): Item name
        - tier (str): Tier name (iron, copper, ..., diamond)
        - emoji (str): Tier emoji
        - group (str): Tier group (metals or gems)
        - score (float): Quality score (0-100)
        - drop_pct (float): Price drop percentage
        - vol_spike_pct (float): Volume spike percentage vs baseline
        - oversupply_pct (float): Oversupply percentage (volume vs buy limit)
        - buy_speed (float): Buy speed percentage (volume vs limit per 5 min)
        - volume (int): Current 5-minute volume
        - high (int): Current high price
        - low (int): Current low price
        - buy (int): Alias for low price
        - sell (int): Alias for high price
        - margin_gp (int): Price margin (high - low) in GP
        - max_buy_4h (int): GE buy limit (max units per 4 hours)
        - max_profit_gp (int): Maximum potential profit (margin_gp * max_buy_4h)
        - flags (list): Special flags (e.g., ["slow_buy", "one_gp_dump", "super"])
        - limit (int): Legacy alias for max_buy_4h
        - timestamp (str): ISO timestamp of snapshot
    
    Example:
        GET /api/dumps?tier=gold&limit=10
        GET /api/dumps?group=gems&special=super
        GET /api/dumps?guild_id=123456789012345678
    """
    guild_id = request.args.get('guild_id', '').strip()
    tier = request.args.get('tier', '').strip().lower()
    group = request.args.get('group', '').strip().lower()
    special = request.args.get('special', '').strip().lower()
    limit = request.args.get('limit', type=int)
    
    # Get guild config if guild_id is provided
    guild_config = None
    if guild_id:
        guild_id = sanitize_guild_id(guild_id)
        if guild_id:
            try:
                guild_config = get_unified_guild_config(guild_id)
            except Exception as e:
                print(f"[ERROR] Failed to get guild config for filtering: {e}")
                guild_config = None
    
    try:
        # Import dump engine (uses cached results by default)
        from utils.dump_engine import analyze_dumps
        
        # Get opportunities from dump engine (uses cache if available)
        opportunities_raw = analyze_dumps(use_cache=True)
        
        # Apply filters
        opportunities = []
        for opp in opportunities_raw:
            # Apply guild-specific filters if guild_id is provided
            if guild_config:
                # Filter by enabled_tiers
                enabled_tiers = guild_config.get('enabled_tiers', [])
                if enabled_tiers and len(enabled_tiers) > 0:
                    opp_tier = opp.get('tier', '').lower()
                    if opp_tier not in enabled_tiers:
                        continue
                
                # Filter by min_score
                min_score = guild_config.get('min_score', 0)
                opp_score = opp.get('score', 0)
                if opp_score < min_score:
                    continue
                
                # Filter by min_margin_gp
                min_margin_gp = guild_config.get('min_margin_gp', 0)
                # Calculate margin_gp if not present
                high = opp.get('high', 0)
                low = opp.get('low', 0)
                margin_gp = opp.get('margin_gp')
                if margin_gp is None and high and low:
                    margin_gp = high - low
                if margin_gp is None or margin_gp < min_margin_gp:
                    continue
            
            # Filter by tier (manual filter, still works)
            if tier and opp.get('tier', '').lower() != tier:
                continue
            
            # Filter by group
            if group and opp.get('group', '').lower() != group:
                continue
            
            # Filter by special flags
            if special:
                flags = opp.get('flags', [])
                if special == 'slow_buy' and 'slow_buy' not in flags:
                    continue
                elif special == 'one_gp_dump' and 'one_gp_dump' not in flags:
                    continue
                elif special == 'super' and 'super' not in flags:
                    continue
            
            # Format opportunity (ensure all required fields are present)
            # Compute buy_speed from oversupply_pct for backward compatibility
            # buy_speed is essentially the same as oversupply_pct (volume vs limit per 5 min)
            oversupply_pct = opp.get('oversupply_pct', 0.0)
            buy_speed = oversupply_pct  # Same metric, different name for compatibility
            
            # Calculate margin_gp and max_profit_gp if not present
            high = opp.get('high', 0)
            low = opp.get('low', 0)
            max_buy_4h = opp.get('max_buy_4h', 0) or opp.get('limit', 0)
            margin_gp = opp.get('margin_gp')
            if margin_gp is None and high and low:
                margin_gp = high - low
            max_profit_gp = opp.get('max_profit_gp')
            if max_profit_gp is None and margin_gp and max_buy_4h:
                max_profit_gp = margin_gp * max_buy_4h
            
            formatted_opp = {
                'id': opp.get('id') or opp.get('item_id'),
                'item_id': opp.get('item_id') or opp.get('id'),  # For compatibility
                'name': opp.get('name', 'Unknown'),
                'tier': opp.get('tier', 'iron'),
                'emoji': opp.get('emoji', '🔩'),
                'group': opp.get('group', 'metals'),
                'score': opp.get('score', 0.0),
                # All underlying metrics (for explainability)
                'drop_pct': opp.get('drop_pct', 0.0),
                'vol_spike_pct': opp.get('vol_spike_pct', 0.0),
                'oversupply_pct': oversupply_pct,
                'buy_speed': buy_speed,  # Backward compatibility (same as oversupply_pct)
                'slow_buy': opp.get('slow_buy', False),
                'one_gp_dump': opp.get('one_gp_dump', False),
                'volume': opp.get('volume', 0),
                'high': high,
                'low': low,
                'buy': opp.get('buy') or low,  # Alias for compatibility
                'sell': opp.get('sell') or high,  # Alias for compatibility
                'margin_gp': margin_gp or 0,
                'max_buy_4h': max_buy_4h,
                'max_profit_gp': max_profit_gp or 0,
                'flags': opp.get('flags', []),
                'limit': max_buy_4h,  # Legacy alias
                'timestamp': opp.get('timestamp', '')
            }
            opportunities.append(formatted_opp)
        
        # Apply limit if specified
        if limit and limit > 0:
            opportunities = opportunities[:limit]
        
        # Return JSON format
        return jsonify(opportunities)
        
    except Exception as e:
        print(f"[ERROR] api_dumps failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to old system if dump engine fails
        try:
            with get_item_lock():
                item_data = get_item_data()
                opportunities = []
                for dump in item_data.get('dump_items', []):
                    max_buy_4h = get_buy_limit(dump.get('id', 0))
                    dump_with_limit = {
                        **dump,
                        'max_buy_4h': max_buy_4h,
                        'limit': max_buy_4h
                    }
                    opportunities.append(dump_with_limit)
                
                if limit and limit > 0:
                    opportunities = opportunities[:limit]
                
                return jsonify(opportunities)
        except Exception as fallback_error:
            print(f"[ERROR] Fallback system also failed: {fallback_error}")
            return jsonify({"error": "Failed to fetch dump opportunities"}), 500

@bp.route('/dumps/<int:item_id>')
@rate_limit(max_requests=200, window=60)
def api_dumps_item(item_id):
    """
    Get dump opportunity for a specific item with recent history.
    
    Args:
        item_id: OSRS item ID
    
    Returns:
        JSON object with:
        - opportunity: Dump opportunity data (if item is currently dumping)
        - recent_history: List of recent 5-minute price snapshots
    """
    try:
        # Try to get opportunity from dump engine first
        from utils.dump_engine import analyze_dumps
        opportunities = analyze_dumps(use_cache=True)
        
        opportunity = None
        for opp in opportunities:
            if opp.get('id') == item_id or opp.get('item_id') == item_id:
                opportunity = opp
                break
        
        # If not found in dump engine, try legacy system
        if not opportunity:
            with get_item_lock():
                item_data = get_item_data()
                for dump in item_data.get('dump_items', []):
                    if dump.get('id') == item_id:
                        max_buy_4h = get_buy_limit(item_id)
                        high = dump.get('high', dump.get('sell', 0))
                        low = dump.get('low', dump.get('buy', 0))
                        margin_gp = high - low
                        max_profit_gp = margin_gp * max_buy_4h
                        opportunity = {
                            **dump,
                            'max_buy_4h': max_buy_4h,
                            'margin_gp': margin_gp,
                            'max_profit_gp': max_profit_gp
                        }
                        break
        
        # Get recent history (last 5 minutes of snapshots)
        recent_history = get_recent_history(item_id, minutes=5)
        
        return jsonify({
            'opportunity': opportunity,
            'recent_history': recent_history
        })
    except Exception as e:
        print(f"[ERROR] api_dumps_item failed for item {item_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to fetch dump data for item {item_id}"}), 500

@bp.route('/spikes')
@rate_limit(max_requests=200, window=60)
def api_spikes():
    """Get spikes with thread-safe access"""
    with get_item_lock():
        item_data = get_item_data()
        return jsonify(item_data['spike_items'])

@bp.route('/tiers')
@rate_limit(max_requests=100, window=60)
def api_tiers():
    """Get tier configuration for a guild"""
    guild_id = sanitize_guild_id(request.args.get('guild_id', ''))
    if not guild_id:
        return jsonify({"error": "Missing required parameter: guild_id"}), 400
    
    try:
        from utils.database import get_all_tiers, get_guild_tier_settings, get_guild_config
        
        tiers = get_all_tiers()
        guild_settings = get_guild_tier_settings(guild_id)
        guild_config = get_guild_config(guild_id)
        
        # Format tiers with guild-specific settings
        tiers_list = []
        for tier in tiers:
            setting = guild_settings.get(tier["name"], {})
            tiers_list.append({
                "id": tier["id"],
                "name": tier["name"],
                "emoji": tier["emoji"],
                "min_score": tier["min_score"],
                "max_score": tier["max_score"],
                "group": tier["group"],
                "role_id": setting.get("role_id"),
                "enabled": setting.get("enabled", True)
            })
        
        return jsonify({
            "tiers": tiers_list,
            "guild_tier_settings": guild_settings,
            "min_tier_name": guild_config.get("min_tier_name")
        })
    except Exception as e:
        print(f"[ERROR] api_tiers failed: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to default tiers
        from utils.dump_engine import TIERS
        default_tiers = []
        for tier in TIERS:
            default_tiers.append({
                "name": tier["name"],
                "emoji": tier["emoji"],
                "min_score": tier["min"],
                "max_score": tier["max"],
                "group": tier["group"],
                "role_id": None,
                "enabled": True
            })
        return jsonify({
            "tiers": default_tiers,
            "guild_tier_settings": {},
            "min_tier_name": None
        })

@bp.route('/watchlist/add', methods=['POST'])
@rate_limit(max_requests=100, window=60)
@validate_json_payload(max_size=1000)
def api_watchlist_add():
    """Add item to watchlist"""
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        guild_id = sanitize_guild_id(data.get('guild_id', ''))
        user_id = data.get('user_id')
        item_id = data.get('item_id')
        item_name = data.get('item_name', '')
        
        if not guild_id or not item_id:
            return jsonify({"error": "Missing required fields: guild_id, item_id"}), 400
        
        if not item_name:
            item_meta = get_item_meta(item_id)
            if item_meta:
                item_name = item_meta.get('name', f'Item {item_id}')
            else:
                item_name = f'Item {item_id}'
        
        try:
            with db_transaction() as session:
                if USE_POSTGRES:
                    stmt = text("""
                        INSERT INTO watchlists (guild_id, user_id, item_id, item_name)
                        VALUES (:guild_id, :user_id, :item_id, :item_name)
                        ON CONFLICT (guild_id, user_id, item_id) DO NOTHING
                    """)
                else:
                    stmt = text("""
                        INSERT OR IGNORE INTO watchlists (guild_id, user_id, item_id, item_name)
                        VALUES (:guild_id, :user_id, :item_id, :item_name)
                    """)
                session.execute(stmt, {
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "item_id": item_id,
                    "item_name": item_name
                })
            
            return jsonify({
                "success": True,
                "message": "Item added to watchlist"
            })
        except Exception as e:
            return jsonify({"error": f"Database error: {str(e)}"}), 500
            
    except Exception as e:
        print(f"[ERROR] api_watchlist_add: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/watchlist/remove', methods=['POST'])
@rate_limit(max_requests=100, window=60)
@validate_json_payload(max_size=1000)
def api_watchlist_remove():
    """Remove item from watchlist"""
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        guild_id = sanitize_guild_id(data.get('guild_id', ''))
        user_id = data.get('user_id')
        item_id = data.get('item_id')
        
        if not guild_id or not item_id:
            return jsonify({"error": "Missing required fields: guild_id, item_id"}), 400
        
        with db_transaction() as session:
            if user_id:
                session.execute(
                    text("DELETE FROM watchlists WHERE guild_id = :guild_id AND user_id = :user_id AND item_id = :item_id"),
                    {"guild_id": guild_id, "user_id": user_id, "item_id": item_id}
                )
            else:
                session.execute(
                    text("DELETE FROM watchlists WHERE guild_id = :guild_id AND user_id IS NULL AND item_id = :item_id"),
                    {"guild_id": guild_id, "item_id": item_id}
                )
        
        return jsonify({
            "success": True,
            "message": "Item removed from watchlist"
        })
        
    except Exception as e:
        print(f"[ERROR] api_watchlist_remove: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/watchlist', methods=['GET'])
@rate_limit(max_requests=200, window=60)
def api_watchlist_get():
    """Get watchlist items for a guild"""
    try:
        guild_id = sanitize_guild_id(request.args.get('guild_id', ''))
        user_id = request.args.get('user_id')
        
        if not guild_id:
            return jsonify({"error": "Missing required parameter: guild_id"}), 400
        
        session = get_db_session()
        try:
            if user_id:
                result = session.execute(
                    text("SELECT item_id, item_name FROM watchlists WHERE guild_id = :guild_id AND user_id = :user_id ORDER BY item_name"),
                    {"guild_id": guild_id, "user_id": user_id}
                )
            else:
                result = session.execute(
                    text("SELECT item_id, item_name FROM watchlists WHERE guild_id = :guild_id ORDER BY item_name"),
                    {"guild_id": guild_id}
                )
            
            rows = result.fetchall()
            watchlist = [
                {
                    "item_id": row[0],
                    "item_name": row[1]
                }
                for row in rows
            ]
            
            return jsonify(watchlist)
        finally:
            session.close()
        
    except Exception as e:
        print(f"[ERROR] api_watchlist_get: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/update_cache', methods=['POST'])
@require_admin_key()
@rate_limit(max_requests=5, window=300)
def api_update_cache():
    """Manually trigger cache update"""
    from utils.shared import is_local_request
    
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    try:
        import utils.cache_updater
        item_map = utils.cache_updater.update_cache()
        
        # Reload names after update
        from background_tasks import load_names
        load_names()
        
        if item_map:
            return jsonify({
                "success": True,
                "message": f"Cache updated successfully! {len(item_map)} items cached.",
                "item_count": len(item_map)
            })
        else:
            return jsonify({
                "success": False,
                "message": "Cache update failed. Using existing cache."
            }), 500
    except Exception as e:
        print(f"[ERROR] api_update_cache: {e}")
        return jsonify({
            "success": False,
            "message": "Error updating cache"
        }), 500

