"""
API routes for dumps, spikes, tiers, and watchlist
"""
from flask import Blueprint, jsonify, request, render_template_string
from utils.shared import get_item_lock, get_item_data
from utils.database import get_db_connection, get_recent_history
from utils.item_metadata import get_item_meta, get_buy_limit
from security import rate_limit, validate_json_payload, sanitize_guild_id, require_admin_key
import sqlite3

# HTML template for dumps table (used by HTMX)
DUMPS_TABLE_TEMPLATE = """
<div class="table-container">
  <table>
    <thead>
      <tr>
        <th>Tier</th>
        <th>Item Name</th>
        <th>Score</th>
        <th>Drop %</th>
        <th>Volume Spike %</th>
        <th>Oversupply %</th>
        <th>Flags</th>
        <th>High / Low</th>
        <th>Max Buy / 4h</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% if dumps %}
        {% for dump in dumps %}
        <tr>
          <td>
            {% if dump.tier_emoji and dump.tier %}
              <strong>{{ dump.tier_emoji }} {{ dump.tier|title }}</strong>
            {% elif dump.emoji and dump.tier %}
              <strong>{{ dump.emoji }} {{ dump.tier|title }}</strong>
            {% else %}
              —
            {% endif %}
          </td>
          <td>
            <a href="https://prices.runescape.wiki/osrs/item/{{ dump.id }}" target="_blank" style="color: var(--accent-primary); text-decoration: none; font-weight: 500;">
              {{ dump.name }}
            </a>
          </td>
          <td><strong>{{ dump.score or '—' }}</strong></td>
          <td class="dump">-{{ "%.1f"|format(dump.drop_pct) if dump.drop_pct else 0 }}%</td>
          <td>{{ "%.1f"|format(dump.vol_spike_pct) if dump.vol_spike_pct else 0 }}%</td>
          <td>{{ "%.1f"|format(dump.oversupply_pct) if dump.oversupply_pct else 0 }}%</td>
          <td>
            {% if dump.flags %}
              {% for flag in dump.flags %}
                {% if flag == 'slow_buy' %}
                  <span style="color: var(--accent-warning);">🐌</span>
                {% elif flag == 'one_gp_dump' %}
                  <span style="color: var(--accent-danger);">💰</span>
                {% elif flag == 'super' %}
                  <span style="color: var(--accent-success);">⭐</span>
                {% endif %}
              {% endfor %}
            {% else %}
              —
            {% endif %}
          </td>
          <td>
            <span class="price-buy">{{ "{:,}".format(dump.high) if dump.high else "—" }}</span> / 
            <span class="price-sell">{{ "{:,}".format(dump.low) if dump.low else "—" }}</span>
          </td>
          <td><strong>{{ "{:,}".format(dump.max_buy_4h) if dump.max_buy_4h else "—" }}</strong></td>
          <td>
            <button 
              class="btn secondary watch-btn" 
              data-item-id="{{ dump.id }}"
              data-item-name="{{ dump.name }}"
              onclick="watchItem(this, {{ dump.id }}, '{{ dump.name|e }}'); return false;">
              Watch
            </button>
          </td>
        </tr>
        {% endfor %}
      {% else %}
        <tr>
          <td colspan="10" style="text-align: center; color: var(--text-muted); padding: 2rem;">
            No dump opportunities found
          </td>
        </tr>
      {% endif %}
    </tbody>
  </table>
</div>
<script>
  async function watchItem(btn, itemId, itemName) {
    try {
      const response = await fetch('/api/watchlist/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          guild_id: 'default',
          item_id: itemId,
          item_name: itemName
        })
      });
      
      const data = await response.json();
      if (data.success) {
        btn.textContent = 'Watching';
        btn.classList.add('watching');
        btn.disabled = true;
        // Update global watchlist set
        if (typeof watchlistItems !== 'undefined') {
          watchlistItems.add(itemId);
        }
      } else {
        alert('Failed to add to watchlist: ' + (data.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Watch error:', error);
      alert('Error adding to watchlist: ' + error.message);
    }
  }
</script>
"""

bp = Blueprint('api_dumps', __name__, url_prefix='/api')

@bp.route('/dumps')
@rate_limit(max_requests=200, window=60)
def api_dumps():
    """
    Get dump opportunities using the dump engine with tier system.
    
    This endpoint returns true dump opportunities (oversupply events) detected
    by analyzing 5-minute price snapshots from prices.runescape.wiki.
    
    Query Parameters:
        tier (str, optional): Filter by tier name (iron, copper, bronze, silver, gold, 
                              platinum, ruby, sapphire, emerald, diamond)
        group (str, optional): Filter by tier group (metals, gems)
        special (str, optional): Filter by special flags:
            - slow_buy: Items with slow buy speed (<50% of limit in 5 min)
            - one_gp_dump: Items that dropped to 1 GP
            - super: Platinum tier or higher (score >= 51)
        limit (int, optional): Maximum number of results to return
        format (str, optional): Response format - 'json' (default) or 'html'
    
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
        - flags (list): Special flags (e.g., ["slow_buy", "super"])
        - max_buy_4h (int): GE buy limit (max units per 4 hours)
        - limit (int): Legacy alias for max_buy_4h
        - timestamp (str): ISO timestamp of snapshot
    
    Example:
        GET /api/dumps?tier=gold&limit=10
        GET /api/dumps?group=gems&special=super
        GET /api/dumps?format=html
    """
    tier = request.args.get('tier', '').strip().lower()
    group = request.args.get('group', '').strip().lower()
    special = request.args.get('special', '').strip().lower()
    limit = request.args.get('limit', type=int)
    response_format = request.args.get('format', 'json').lower()
    
    # Validate format parameter
    if response_format not in ['json', 'html']:
        response_format = 'json'
    
    try:
        # Import dump engine (uses cached results by default)
        from utils.dump_engine import analyze_dumps
        
        # Get opportunities from dump engine (uses cache if available)
        opportunities_raw = analyze_dumps(use_cache=True)
        
        # Apply filters
        opportunities = []
        for opp in opportunities_raw:
            # Filter by tier
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
            formatted_opp = {
                'id': opp.get('id') or opp.get('item_id'),
                'item_id': opp.get('item_id') or opp.get('id'),  # For compatibility
                'name': opp.get('name', 'Unknown'),
                'tier': opp.get('tier', 'iron'),
                'emoji': opp.get('emoji', '🔩'),
                'tier_emoji': opp.get('emoji', '🔩'),  # For HTML template compatibility
                'group': opp.get('group', 'metals'),
                'score': opp.get('score', 0.0),
                'drop_pct': opp.get('drop_pct', 0.0),
                'vol_spike_pct': opp.get('vol_spike_pct', 0.0),
                'oversupply_pct': opp.get('oversupply_pct', 0.0),
                'buy_speed': opp.get('buy_speed', 0.0),
                'volume': opp.get('volume', 0),
                'high': opp.get('high', 0),
                'low': opp.get('low', 0),
                'buy': opp.get('buy') or opp.get('low', 0),  # Alias for compatibility
                'sell': opp.get('sell') or opp.get('high', 0),  # Alias for compatibility
                'flags': opp.get('flags', []),
                'max_buy_4h': opp.get('max_buy_4h', 0),
                'limit': opp.get('limit') or opp.get('max_buy_4h', 0),  # Legacy alias
                'timestamp': opp.get('timestamp', '')
            }
            opportunities.append(formatted_opp)
        
        # Apply limit if specified
        if limit and limit > 0:
            opportunities = opportunities[:limit]
        
        # Return HTML format if requested
        if response_format == 'html':
            try:
                return render_template_string(DUMPS_TABLE_TEMPLATE, dumps=opportunities)
            except (KeyError, ValueError, TypeError) as e:
                print(f"[ERROR] Failed to render template: {e}")
                # Fallback to JSON on template error
                return jsonify(opportunities)
        
        # Return JSON format (default)
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
                
                if response_format == 'html':
                    try:
                        return render_template_string(DUMPS_TABLE_TEMPLATE, dumps=opportunities)
                    except (KeyError, ValueError, TypeError) as e:
                        print(f"[ERROR] Failed to render template: {e}")
                
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
                        opportunity = {**dump, 'max_buy_4h': max_buy_4h}
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
        
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            c.execute("""
                INSERT OR IGNORE INTO watchlists (guild_id, user_id, item_id, item_name)
                VALUES (?, ?, ?, ?)
            """, (guild_id, user_id, item_id, item_name))
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": "Item added to watchlist"
            })
        except sqlite3.Error as e:
            conn.rollback()
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
        
        conn = get_db_connection()
        c = conn.cursor()
        
        if user_id:
            c.execute("""
                DELETE FROM watchlists
                WHERE guild_id = ? AND user_id = ? AND item_id = ?
            """, (guild_id, user_id, item_id))
        else:
            c.execute("""
                DELETE FROM watchlists
                WHERE guild_id = ? AND user_id IS NULL AND item_id = ?
            """, (guild_id, item_id))
        
        conn.commit()
        
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
        
        conn = get_db_connection()
        c = conn.cursor()
        
        if user_id:
            c.execute("""
                SELECT item_id, item_name
                FROM watchlists
                WHERE guild_id = ? AND user_id = ?
                ORDER BY item_name
            """, (guild_id, user_id))
        else:
            c.execute("""
                SELECT item_id, item_name
                FROM watchlists
                WHERE guild_id = ?
                ORDER BY item_name
            """, (guild_id,))
        
        rows = c.fetchall()
        watchlist = [
            {
                "item_id": row[0],
                "item_name": row[1]
            }
            for row in rows
        ]
        
        return jsonify(watchlist)
        
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

