"""
API routes for dumps, spikes, tiers, and watchlist
"""
from flask import Blueprint, jsonify, request, render_template_string
from utils.shared import get_item_lock, get_item_data
import utils.shared
from utils.database import get_db_connection, get_recent_history
from utils.item_metadata import get_item_meta, get_buy_limit
from config_manager import get_config
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
        <th>Max Buy / 4h</th>
        <th>High / Low</th>
        <th>Flags</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% if dumps %}
        {% for dump in dumps %}
        <tr>
          <td>
            {% if dump.tier_emoji and dump.tier %}
              {{ dump.tier_emoji }} {{ dump.tier|title }}
            {% else %}
              —
            {% endif %}
          </td>
          <td>
            <a href="https://prices.runescape.wiki/osrs/item/{{ dump.id }}" target="_blank" style="color: var(--accent-primary); text-decoration: none;">
              {{ dump.name }}
            </a>
          </td>
          <td>{{ dump.score or '—' }}</td>
          <td class="dump">-{{ "%.1f"|format(dump.drop_pct) }}%</td>
          <td>{{ "%.1f"|format(dump.vol_spike_pct) }}%</td>
          <td>{{ "%.1f"|format(dump.oversupply_pct) }}%</td>
          <td>{{ "{:,}".format(dump.max_buy_4h) if dump.max_buy_4h else "—" }}</td>
          <td>
            <span class="price-buy">{{ "{:,}".format(dump.buy) }}</span> / 
            <span class="price-sell">{{ "{:,}".format(dump.sell) }}</span>
          </td>
          <td>
            {% if dump.flags %}
              {{ ', '.join(dump.flags) }}
            {% else %}
              —
            {% endif %}
          </td>
          <td>
            <button 
              class="btn secondary watch-btn" 
              data-item-id="{{ dump.id }}"
              data-item-name="{{ dump.name }}"
              onclick="
                fetch('/api/watchlist/add', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({guild_id: 'default', item_id: {{ dump.id }}, item_name: '{{ dump.name|e }}'})
                }).then(r => r.json()).then(data => {
                  if (data.success) {
                    this.textContent = 'Watching';
                    this.classList.add('watching');
                    this.disabled = true;
                  }
                });
                return false;
              ">
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
"""

bp = Blueprint('api_dumps', __name__, url_prefix='/api')

@bp.route('/dumps')
@rate_limit(max_requests=200, window=60)
def api_dumps():
    """Get dump opportunities using new dump engine with tier system"""
    tier = request.args.get('tier', '').lower()
    group = request.args.get('group', '').lower()
    special = request.args.get('special', '').lower()
    limit = request.args.get('limit', type=int)
    response_format = request.args.get('format', 'json').lower()
    
    try:
        from utils.dump_engine import analyze_dumps
        opportunities_raw = analyze_dumps()
        
        opportunities = []
        for opp in opportunities_raw:
            if tier and opp.get('tier', '').lower() != tier:
                continue
            if group and opp.get('group', '').lower() != group:
                continue
            if special:
                flags = opp.get('flags', [])
                if special == 'slow_buy' and 'slow_buy' not in flags:
                    continue
                elif special == 'one_gp_dump' and 'one_gp_dump' not in flags:
                    continue
                elif special == 'super' and 'super' not in flags:
                    continue
            
            formatted_opp = {
                'id': opp.get('item_id') or opp.get('id'),
                'name': opp.get('name'),
                'tier': opp.get('tier'),
                'emoji': opp.get('emoji'),
                'tier_emoji': opp.get('emoji'),
                'group': opp.get('group'),
                'score': opp.get('score'),
                'drop_pct': opp.get('drop_pct'),
                'vol_spike_pct': opp.get('vol_spike_pct'),
                'oversupply_pct': opp.get('oversupply_pct'),
                'volume': opp.get('volume'),
                'high': opp.get('high'),
                'low': opp.get('low'),
                'buy': opp.get('low'),
                'sell': opp.get('high'),
                'flags': opp.get('flags', []),
                'max_buy_4h': opp.get('max_buy_4h', 0),
                'limit': opp.get('max_buy_4h', 0),
                'timestamp': opp.get('timestamp')
            }
            opportunities.append(formatted_opp)
        
        if limit and limit > 0:
            opportunities = opportunities[:limit]
        
        if response_format == 'html':
            try:
                return render_template_string(DUMPS_TABLE_TEMPLATE, dumps=opportunities)
            except (KeyError, ValueError, TypeError) as e:
                print(f"[ERROR] Failed to render template: {e}")
        
        return jsonify(opportunities)
        
    except Exception as e:
        print(f"[ERROR] api_dumps failed with new engine: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to old system
        with get_item_lock():
            item_data = get_item_data()
            opportunities = []
            for dump in item_data['dump_items']:
                max_buy_4h = get_buy_limit(dump.get('id', 0))
                dump_with_limit = {**dump, 'max_buy_4h': max_buy_4h}
                opportunities.append(dump_with_limit)
            
            if limit and limit > 0:
                opportunities = opportunities[:limit]
            
            if response_format == 'html':
                try:
                    return render_template_string(DUMPS_TABLE_TEMPLATE, dumps=opportunities)
                except (KeyError, ValueError, TypeError) as e:
                    print(f"[ERROR] Failed to render template: {e}")
            
            return jsonify(opportunities)

@bp.route('/dumps/<int:item_id>')
@rate_limit(max_requests=200, window=60)
def api_dumps_item(item_id):
    """Get dump opportunity for specific item with recent history"""
    with get_item_lock():
        item_data = get_item_data()
        opportunity = None
        for dump in item_data['dump_items']:
            if dump.get('id') == item_id:
                max_buy_4h = get_buy_limit(item_id)
                opportunity = {**dump, 'max_buy_4h': max_buy_4h}
                break
        
        recent_history = get_recent_history(item_id, minutes=5)
        
        return jsonify({
            'opportunity': opportunity,
            'recent_history': recent_history
        })

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
    
    config = get_config(guild_id)
    tiers_config = config.get("tiers", {})
    
    if not tiers_config:
        from utils.dump_engine import TIERS
        default_tiers = {}
        for tier in TIERS:
            default_tiers[tier["name"]] = {
                "role_id": None,
                "enabled": True,
                "group": tier["group"],
                "min_score": tier["min"],
                "max_score": tier["max"],
                "emoji": tier["emoji"]
            }
        return jsonify(default_tiers)
    
    return jsonify(tiers_config)

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

