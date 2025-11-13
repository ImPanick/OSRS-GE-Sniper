"""
Core routes blueprint - index, dashboard, volume tracker, health checks
"""
from flask import Blueprint, jsonify, redirect, render_template_string, request
from utils.shared import (
    get_item_lock, get_item_data, BASE, HEADERS, FALLBACK_BASE, FALLBACK_HEADERS,
    fetch_with_fallback, convert_1h_data_to_dict, TIME_WINDOWS, needs_setup, item_names
)
from utils.database import get_db_connection, get_price_historicals
from security import rate_limit
from datetime import datetime
import requests

# Import helper functions from background_tasks
from background_tasks import calculate_risk_metrics, ge_tax

# HTML template for dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OSRS GE Sniper - Tiered Control Panel</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="https://cdn.jsdelivr.net/npm/htmx.org@1.9.10/dist/htmx.min.js"></script>
  <style>
    .tier-filters {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      padding: 1.5rem;
      margin-bottom: 2rem;
      box-shadow: var(--shadow-md);
    }
    .filter-section {
      margin-bottom: 1.5rem;
    }
    .filter-section:last-child {
      margin-bottom: 0;
    }
    .filter-section h3 {
      font-size: 0.875rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
      margin-bottom: 0.75rem;
    }
    .filter-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
    }
    .filter-btn {
      padding: 0.5rem 1rem;
      border-radius: var(--radius-md);
      border: 1px solid var(--border-color);
      background: var(--bg-tertiary);
      color: var(--text-secondary);
      cursor: pointer;
      transition: var(--transition);
      font-size: 0.875rem;
      font-weight: 500;
    }
    .filter-btn:hover {
      background: var(--bg-hover);
      border-color: var(--accent-primary);
      color: var(--accent-primary);
      transform: translateY(-2px);
    }
    .filter-btn.active {
      background: rgba(0, 212, 255, 0.1);
      border-color: var(--accent-primary);
      color: var(--accent-primary);
    }
    .watch-btn.watching {
      background: var(--bg-tertiary);
      color: var(--accent-success);
      border-color: var(--accent-success);
      cursor: default;
    }
    .watch-btn.watching:hover {
      transform: none;
    }
  </style>
</head>
<body>
  <h1>⚔️ OSRS GE Sniper - Tiered Control Panel</h1>
  <nav>
    <a href="/dashboard" class="active">📊 Dashboard</a>
    <a href="/volume_tracker">📈 Volume Tracker</a>
    <a href="/admin">🔒 Admin</a>
  </nav>
  
  <div style="max-width: 1400px; margin: 0 auto; padding: 0 2rem;">
    <div class="tier-filters">
      <div class="filter-section">
        <h3>Groups</h3>
        <div class="filter-buttons">
          <button class="filter-btn" onclick="filterDumps('group', 'metals')">🔩 All Metals</button>
          <button class="filter-btn" onclick="filterDumps('group', 'gems')">💎 All Gems</button>
        </div>
      </div>
      <div class="filter-section">
        <h3>Metal Tiers</h3>
        <div class="filter-buttons">
          <button class="filter-btn" onclick="filterDumps('tier', 'iron')">🔩 Iron</button>
          <button class="filter-btn" onclick="filterDumps('tier', 'copper')">🪙 Copper</button>
          <button class="filter-btn" onclick="filterDumps('tier', 'bronze')">🏅 Bronze</button>
          <button class="filter-btn" onclick="filterDumps('tier', 'silver')">🥈 Silver</button>
          <button class="filter-btn" onclick="filterDumps('tier', 'gold')">🥇 Gold</button>
          <button class="filter-btn" onclick="filterDumps('tier', 'platinum')">⚪ Platinum</button>
        </div>
      </div>
      <div class="filter-section">
        <h3>Gem Tiers</h3>
        <div class="filter-buttons">
          <button class="filter-btn" onclick="filterDumps('tier', 'ruby')">💎🔴 Ruby</button>
          <button class="filter-btn" onclick="filterDumps('tier', 'sapphire')">💎🔵 Sapphire</button>
          <button class="filter-btn" onclick="filterDumps('tier', 'emerald')">💎🟢 Emerald</button>
          <button class="filter-btn" onclick="filterDumps('tier', 'diamond')">💎 Diamond</button>
        </div>
      </div>
      <div class="filter-section">
        <h3>Special Filters</h3>
        <div class="filter-buttons">
          <button class="filter-btn" onclick="filterDumps('special', 'slow_buy')">🐌 Slow Buy</button>
          <button class="filter-btn" onclick="filterDumps('special', 'one_gp_dump')">💰 1GP Dumps</button>
          <button class="filter-btn" onclick="filterDumps('special', 'super')">⭐ Super</button>
          <button class="filter-btn" onclick="filterDumps('', '')">🔄 Show All</button>
        </div>
      </div>
    </div>
    
    <div id="dumps-table" 
         hx-get="/api/dumps?format=html" 
         hx-trigger="load"
         hx-swap="innerHTML">
      <div style="text-align: center; padding: 2rem;">Loading...</div>
    </div>
  </div>
  
  <script>
    let currentFilter = {type: '', value: ''};
    
    function filterDumps(type, value) {
      currentFilter = {type: type, value: value};
      
      // Update active button
      document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');
      
      // Build query string
      let url = '/api/dumps?format=html';
      if (type && value) {
        if (type === 'tier') {
          url += `&tier=${value}`;
        } else if (type === 'group') {
          url += `&group=${value}`;
        } else if (type === 'special') {
          url += `&special=${value}`;
        }
      }
      
      // Update table via HTMX
      htmx.ajax('GET', url, {target: '#dumps-table', swap: 'innerHTML'});
    }
    
    // Load watchlist on page load
    let watchlistItems = new Set();
    async function loadWatchlist() {
      try {
        const response = await fetch('/api/watchlist?guild_id=default');
        if (response.ok) {
          const items = await response.json();
          watchlistItems = new Set(items.map(item => item.item_id));
          updateWatchButtons();
        }
      } catch (e) {
        console.error('Failed to load watchlist:', e);
      }
    }
    
    function updateWatchButtons() {
      document.querySelectorAll('.watch-btn').forEach(btn => {
        const itemId = parseInt(btn.dataset.itemId);
        if (watchlistItems.has(itemId)) {
          btn.textContent = 'Watching';
          btn.classList.add('watching');
          btn.disabled = true;
        }
      });
    }
    
    // Load watchlist when page loads
    loadWatchlist();
    
    // Listen for HTMX swaps to update watch buttons
    document.body.addEventListener('htmx:afterSwap', function(event) {
      if (event.detail.target.id === 'dumps-table') {
        updateWatchButtons();
      }
    });
  </script>
</body>
</html>
"""

bp = Blueprint('core', __name__)

@bp.route('/')
def index():
    """Redirect to Next.js frontend"""
    return redirect('http://localhost:3000')

@bp.route('/dashboard')
@rate_limit(max_requests=100, window=60)
def dashboard():
    """Tiered control panel dashboard with HTMX filters"""
    return render_template_string(DASHBOARD_TEMPLATE)

@bp.route('/api/setup/status', methods=['GET'])
@rate_limit(max_requests=30, window=60)
def setup_status():
    """Check if setup is needed"""
    return jsonify({"needs_setup": needs_setup()})

@bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for Docker"""
    return jsonify({"status": "healthy", "service": "backend"})

@bp.route('/api/top')
@rate_limit(max_requests=200, window=60)
def api_top():
    """Get top flips with thread-safe access"""
    with get_item_lock():
        item_data = get_item_data()
        return jsonify(item_data['top_items'][:20])

@bp.route('/api/all_items')
@rate_limit(max_requests=100, window=60)
def api_all_items():
    """API endpoint for volume tracker - returns all items with filtering support"""
    time_window = request.args.get('time_window', '1h', type=str)
    
    time_data = {}
    if time_window in TIME_WINDOWS:
        try:
            if time_window == "1h":
                endpoint = f"{BASE}/1h"
                fallback_endpoint = None
            else:
                endpoint = f"{BASE}/{time_window}"
                fallback_endpoint = f"{FALLBACK_BASE}/{time_window}" if FALLBACK_BASE else None
            
            time_data_raw, _ = fetch_with_fallback(
                endpoint, HEADERS, fallback_endpoint,
                FALLBACK_HEADERS if FALLBACK_BASE else None, timeout=30
            )
            
            if time_window == "1h" and isinstance(time_data_raw, dict) and "data" in time_data_raw:
                time_data = {"data": {}}
                for item in time_data_raw["data"]:
                    item_id = str(item.get("id"))
                    time_data["data"][item_id] = {
                        "volume": item.get("volume", 0),
                        "avgHighPrice": item.get("avgHighPrice"),
                        "avgLowPrice": item.get("avgLowPrice"),
                        "highTime": item.get("timestamp"),
                        "lowTime": item.get("timestamp")
                    }
            else:
                time_data = time_data_raw
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"[WARNING] Failed to fetch {time_window} data: {e}")
            time_data = {}
    
    with get_item_lock():
        item_data = get_item_data()
        items_with_volume = []
        for item in item_data['all_items']:
            item_id_str = str(item['id'])
            if item_id_str in time_data.get('data', {}):
                vol_data = time_data['data'][item_id_str]
                item['volume_' + time_window] = vol_data.get('volume', 0)
                item['avgHighPrice_' + time_window] = vol_data.get('avgHighPrice')
                item['avgLowPrice_' + time_window] = vol_data.get('avgLowPrice')
                item['highTime_' + time_window] = vol_data.get('highTime')
                item['lowTime_' + time_window] = vol_data.get('lowTime')
            items_with_volume.append(item)
        
        return jsonify(items_with_volume)

@bp.route('/api/osrs_status')
@rate_limit(max_requests=30, window=60)
def api_osrs_status():
    """Check OSRS Wiki API connection status with fallback"""
    try:
        data, source = fetch_with_fallback(
            f"{BASE}/latest", HEADERS,
            f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None, timeout=10
        )
        item_count = len(data.get("data", {}))
        return jsonify({
            "status": "connected",
            "online": True,
            "item_count": item_count,
            "source": source,
            "last_check": int(datetime.now().timestamp())
        })
    except requests.exceptions.Timeout:
        return jsonify({
            "status": "timeout",
            "online": False,
            "error": "Connection timeout (both APIs)",
            "last_check": int(datetime.now().timestamp())
        }), 500
    except Exception as e:
        return jsonify({
            "status": "error",
            "online": False,
            "error": str(e),
            "last_check": int(datetime.now().timestamp())
        }), 500

@bp.route('/api/recent_trades')
@rate_limit(max_requests=100, window=60)
def api_recent_trades():
    """Get recent trades from database"""
    limit = request.args.get('limit', 50, type=int)
    if limit not in [25, 50, 100, 200]:
        limit = 50
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            SELECT item_id, timestamp, low, high, volume
            FROM prices
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        rows = c.fetchall()
        trades = []
        for row in rows:
            item_id, timestamp, low, high, volume = row
            name = item_names.get(str(item_id), f"Item {item_id}")
            trades.append({
                "item_id": item_id,
                "name": name,
                "timestamp": timestamp,
                "time": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "low": low,
                "high": high,
                "volume": volume,
                "avg_price": (low + high) // 2
            })
        
        return jsonify({
            "trades": trades,
            "count": len(trades),
            "limit": limit
        })
    except Exception as e:
        print(f"[ERROR] api_recent_trades: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@bp.route('/api/nightly')
@rate_limit(max_requests=50, window=60)
def api_nightly():
    """API endpoint for overnight flip recommendations"""
    min_profit = request.args.get('min_profit', 1_000_000, type=int)
    
    try:
        latest, _ = fetch_with_fallback(
            f"{BASE}/latest", HEADERS,
            f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None, timeout=30
        )
        
        h1_raw, _ = fetch_with_fallback(
            f"{BASE}/1h", HEADERS, None, None, timeout=30
        )
        h1 = convert_1h_data_to_dict(h1_raw)
        
        mapping, _ = fetch_with_fallback(
            f"{BASE}/mapping", HEADERS,
            f"{FALLBACK_BASE}/mapping" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None, timeout=30
        )
        
        limit_map = {str(m['id']): m.get('limit', 0) for m in mapping}
        overnight_opportunities = []
        
        for id_str, data in latest.get("data", {}).items():
            if not data.get("high") or not data.get("low"):
                continue
            
            low, high = data["low"], data["high"]
            name = utils.shared.item_names.get(id_str, f"Item {id_str}")
            vol = h1.get(id_str, {}).get("volume", 0) or 1
            limit = limit_map.get(id_str, 0)
            
            if limit == 0 or vol < 1000:
                continue
            
            historicals = get_price_historicals(int(id_str))
            avg_24h = historicals.get('avg_24h')
            avg_12h = historicals.get('avg_12h')
            avg_6h = historicals.get('avg_6h')
            
            if not avg_24h or not avg_12h:
                continue
            
            insta_buy = data.get('high', low)
            insta_sell = data.get('low', high)
            current_profit = high - low - ge_tax(high)
            current_roi = (current_profit / low * 100) if low > 0 else 0
            risk_metrics = calculate_risk_metrics(low, high, insta_buy, insta_sell, vol, limit, current_profit)
            
            price_deviation = ((avg_24h - low) / avg_24h * 100) if avg_24h > 0 else 0
            
            trend_score = 0
            if avg_6h and avg_12h and avg_24h:
                if avg_6h > 0:
                    trend_6h = ((low - avg_6h) / avg_6h * 100) if avg_6h > 0 else 0
                    trend_12h = ((avg_6h - avg_12h) / avg_12h * 100) if avg_12h > 0 else 0
                    if trend_6h > -2 and trend_12h > -5:
                        trend_score = 50
                    if trend_6h > 0:
                        trend_score = 75
            
            volume_consistency = min(100, (vol / 10000) * 20)
            recovery_potential = (avg_24h - low) * limit * 0.99 if price_deviation > 0 else 0
            overnight_profit = current_profit * limit + recovery_potential * 0.5
            
            if overnight_profit < min_profit:
                continue
            
            overnight_roi = (overnight_profit / (low * limit) * 100) if low * limit > 0 else 0
            
            confidence = 0
            confidence += min(30, price_deviation * 2) if price_deviation > 0 else 0
            confidence += trend_score * 0.2
            confidence += volume_consistency * 0.2
            confidence += risk_metrics.get('liquidity_score', 0) * 0.15
            confidence += max(0, 100 - risk_metrics.get('risk_score', 50)) * 0.2
            
            if confidence < 40:
                continue
            
            reasoning_parts = []
            if price_deviation > 5:
                reasoning_parts.append(f"{price_deviation:.1f}% below 24h average")
            if trend_score > 50:
                reasoning_parts.append("showing recovery trend")
            if volume_consistency > 70:
                reasoning_parts.append("consistent volume")
            if risk_metrics.get('liquidity_score', 0) > 70:
                reasoning_parts.append("high liquidity")
            if risk_metrics.get('risk_score', 100) < 30:
                reasoning_parts.append("low risk")
            
            reasoning = ", ".join(reasoning_parts) if reasoning_parts else "good fundamentals"
            
            overnight_opportunities.append({
                "id": int(id_str),
                "name": name,
                "buy": low,
                "sell": high,
                "insta_buy": insta_buy,
                "insta_sell": insta_sell,
                "profit": current_profit,
                "roi": current_roi,
                "volume": vol,
                "limit": limit,
                "overnight_profit": int(overnight_profit),
                "overnight_roi": overnight_roi,
                "overnight_confidence": confidence,
                "reasoning": reasoning,
                **risk_metrics,
                **historicals
            })
        
        overnight_opportunities.sort(
            key=lambda x: x['overnight_profit'] * (x['overnight_confidence'] / 100),
            reverse=True
        )
        
        return jsonify(overnight_opportunities[:10])
        
    except Exception as e:
        print(f"[ERROR] api_nightly: {e}")
        return jsonify({"error": "Failed to calculate overnight recommendations"}), 500

