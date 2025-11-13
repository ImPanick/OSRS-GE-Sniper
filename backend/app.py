# backend/app.py
import requests
import time
import json
import threading
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request, redirect, render_template_string
from flask_cors import CORS
from discord_webhook import DiscordWebhook
from config_manager import get_config, save_config, is_banned, ban_server, unban_server, list_servers
import os
import urllib.parse
from utils.database import log_price, get_price_historicals, init_db, get_db_connection, get_recent_history
from utils.item_metadata import get_item_meta, get_buy_limit
from utils.recipe_data import get_recipe, get_decant_set
import secrets
from security import (
    sanitize_guild_id, sanitize_channel_id, sanitize_webhook_url, sanitize_token,
    validate_json_payload, rate_limit, require_admin_key, escape_html,
    validate_numeric
)

app = Flask(__name__, static_folder='static', static_url_path='/static')
# CORS configuration: restrict origins in production
# Allow all origins in development, but should be restricted in production
cors_origins = os.getenv('CORS_ORIGINS', '*').split(',')
CORS(app, resources={r"/api/*": {"origins": cors_origins}})
# Primary OSRS API (official)
BASE = "https://prices.runescape.wiki/api/v1/osrs"
# Fallback API
FALLBACK_BASE = "https://grandexchange.tools/api"
# Improved User-Agent as required by API documentation
USER_AGENT = os.getenv('OSRS_API_USER_AGENT', "OSRS-GE-Sniper/1.0 (https://github.com/ImPanick/OSRS-GE-Sniper; contact@example.com)")
HEADERS = {"User-Agent": USER_AGENT}
FALLBACK_HEADERS = {"User-Agent": USER_AGENT}

# Load config with fallback paths for Docker and local development
CONFIG_PATH = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(__file__), '..', 'config.json'))
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')

CONFIG = {}
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r') as f:
            CONFIG = json.load(f)
    except (json.JSONDecodeError, IOError):
        CONFIG = {}

# Set default thresholds if not present
if "thresholds" not in CONFIG:
    CONFIG["thresholds"] = {}
CONFIG["thresholds"].setdefault("margin_min", 100000)  # 100k profit (was 2M - too high!)
CONFIG["thresholds"].setdefault("dump_drop_pct", 5)     # 5% drop (was 18% - too high!)
CONFIG["thresholds"].setdefault("spike_rise_pct", 5)    # 5% rise (was 20% - too high!)
CONFIG["thresholds"].setdefault("min_volume", 100)      # 100 volume (was 400 - reasonable)

# Thread-safe storage for item data
_item_lock = threading.Lock()
item_names = {}
top_items = []
dump_items = []
spike_items = []
all_items = []  # All items for volume tracker

def ge_tax(sell): return min(0.01 * sell, 5_000_000)

def calculate_risk_metrics(low, high, insta_buy, insta_sell, volume, limit, profit):
    """
    Calculate risk metrics for an item based on volume, margins, and liquidity
    
    Returns:
        dict with risk_score, liquidity_score, spread_risk, volume_velocity, profitability_confidence
    """
    # Liquidity Score: Can you actually buy/sell enough?
    # Higher volume relative to limit = better liquidity
    if limit > 0:
        liquidity_ratio = volume / limit if limit > 0 else 0
        # If volume is 10x the limit, you can flip multiple times = high liquidity
        liquidity_score = min(100, (liquidity_ratio / 10) * 100)  # 0-100, 100 = 10x+ volume
    else:
        liquidity_score = 0
    
    # Spread Risk: Difference between instant and regular prices
    # Large spread = higher risk (might not get the listed price)
    buy_spread = abs(insta_buy - low) / low * 100 if low > 0 else 0
    sell_spread = abs(insta_sell - high) / high * 100 if high > 0 else 0
    avg_spread = (buy_spread + sell_spread) / 2
    # Lower spread = lower risk (0-100, where 0 = no spread, 100 = huge spread)
    spread_risk = min(100, avg_spread * 10)  # 10% spread = 100 risk
    
    # Volume Velocity: How fast items are moving
    # Higher volume = faster movement = lower risk
    volume_velocity = min(100, (volume / 1000) * 10)  # 100k volume = 100 score
    
    # Profitability Confidence: Can you actually make the profit?
    # Factors: volume, liquidity, spread
    if limit > 0 and volume > 0:
        # Can you buy your limit? (volume must be >= limit for full flip)
        can_buy_full = 1.0 if volume >= limit else volume / limit
        
        # Will you get the listed price? (spread risk)
        price_confidence = max(0, 1.0 - (avg_spread / 20))  # 20% spread = 0 confidence
        
        # Combined confidence
        profitability_confidence = (can_buy_full * 0.6 + price_confidence * 0.4) * 100
    else:
        profitability_confidence = 0
    
    # Overall Risk Score (0-100, lower is better)
    # Combines all factors: lower liquidity, higher spread, lower volume = higher risk
    risk_score = (
        (100 - liquidity_score) * 0.3 +  # 30% weight on liquidity
        spread_risk * 0.4 +                # 40% weight on spread
        (100 - volume_velocity) * 0.3      # 30% weight on volume velocity
    )
    
    # Risk level label
    if risk_score < 20:
        risk_level = "LOW"
    elif risk_score < 40:
        risk_level = "MEDIUM"
    elif risk_score < 60:
        risk_level = "HIGH"
    else:
        risk_level = "VERY HIGH"
    
    return {
        "risk_score": round(risk_score, 1),
        "risk_level": risk_level,
        "liquidity_score": round(liquidity_score, 1),
        "spread_risk": round(spread_risk, 1),
        "buy_spread_pct": round(buy_spread, 2),
        "sell_spread_pct": round(sell_spread, 2),
        "volume_velocity": round(volume_velocity, 1),
        "profitability_confidence": round(profitability_confidence, 1)
    }

def get_item_thumbnail_url(item_name: str) -> str:
    """
    Get the OSRS Wiki thumbnail URL for an item
    """
    if not item_name:
        return None
    
    # Format item name for wiki URL
    wiki_name = item_name.strip().replace(' ', '_')
    parts = wiki_name.split('_')
    wiki_name = '_'.join(part.capitalize() for part in parts)
    wiki_name = urllib.parse.quote(wiki_name, safe='_')
    
    # OSRS Wiki image URL format
    return f"https://oldschool.runescape.wiki/images/{wiki_name}.png"

def get_dump_quality(drop_pct, volume, low_price):
    if volume > 1_500_000:
        return "NUCLEAR DUMP", "WHALE PANIC — 1.5M+ DUMPED"
    score = (drop_pct / 10) * (volume / 1000) * (low_price / 1_000_000)
    if score >= 100:
        return "GOD-TIER", "INSANE BUY OPPORTUNITY"
    elif score >= 40:
        return "ELITE", "HIGH VOLUME CRASH"
    elif score >= 15:
        return "PREMIUM", "STRONG DUMP"
    elif score >= 5:
        return "GOOD", "SOLID DIP"
    elif score >= 1:
        return "DEAL", "WORTH A LOOK"
    else:
        return "", ""

def get_item_tier(item_name):
    """
    Determine item tier based on name
    Returns: (tier_name, emoji) or (None, None)
    """
    name_lower = item_name.lower()
    
    # Metal tiers
    if 'iron' in name_lower and 'bar' in name_lower:
        return 'iron', '⚙️'
    if 'bronze' in name_lower and 'bar' in name_lower:
        return 'bronze', '🥉'
    if 'copper' in name_lower:
        return 'copper', '🟤'
    if 'silver' in name_lower and 'bar' in name_lower:
        return 'silver', '🥈'
    if 'gold' in name_lower and 'bar' in name_lower:
        return 'gold', '🥇'
    if 'platinum' in name_lower:
        return 'platinum', '💎'
    
    # Gem tiers
    if 'ruby' in name_lower:
        return 'ruby', '💎'
    if 'sapphire' in name_lower:
        return 'sapphire', '💠'
    if 'emerald' in name_lower:
        return 'emerald', '💚'
    if 'diamond' in name_lower:
        return 'diamond', '💠'
    
    return None, None

def get_item_group(item_name):
    """
    Determine item group (metals, gems, etc.)
    Returns: group_name or None
    """
    name_lower = item_name.lower()
    
    # Metals
    metals = ['iron', 'bronze', 'copper', 'silver', 'gold', 'platinum', 'steel', 'mithril', 'adamant', 'rune', 'bar']
    if any(metal in name_lower for metal in metals):
        return 'metals'
    
    # Gems
    gems = ['diamond', 'ruby', 'emerald', 'sapphire', 'opal', 'jade', 'topaz', 'dragonstone']
    if any(gem in name_lower for gem in gems):
        return 'gems'
    
    return None

# HTML template for dashboard page
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
    .dashboard-layout {
      display: flex;
      gap: 2rem;
      max-width: 1600px;
      margin: 0 auto;
      padding: 2rem;
    }
    .sidebar {
      width: 280px;
      flex-shrink: 0;
    }
    .sidebar h3 {
      margin-bottom: 1rem;
      color: var(--accent-primary);
      font-size: 1.1rem;
    }
    .filter-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 0.75rem;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      padding: 1.5rem;
      box-shadow: var(--shadow-md);
    }
    .filter-btn {
      background: var(--bg-tertiary);
      color: var(--text-primary);
      border: 1px solid var(--border-color);
      padding: 0.75rem 1rem;
      border-radius: var(--radius-md);
      cursor: pointer;
      transition: var(--transition);
      text-align: left;
      font-weight: 500;
    }
    .filter-btn:hover {
      background: var(--bg-hover);
      border-color: var(--accent-primary);
      color: var(--accent-primary);
      transform: translateX(4px);
    }
    .filter-btn.active {
      background: rgba(0, 212, 255, 0.1);
      border-color: var(--accent-primary);
      color: var(--accent-primary);
    }
    .main-content {
      flex: 1;
      min-width: 0;
    }
    #dumps-table {
      min-height: 400px;
    }
    .watch-btn.watching {
      background: var(--accent-success);
      color: var(--bg-primary);
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

  <div class="dashboard-layout">
    <aside class="sidebar">
      <h3>Filters</h3>
      <div class="filter-grid">
        <button 
          class="filter-btn active"
          hx-get="/api/dumps?format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          All Dumps
        </button>
        
        <h4 style="margin-top: 1rem; margin-bottom: 0.5rem; color: var(--text-secondary); font-size: 0.9rem;">Groups</h4>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?group=metals&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          All Metals
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?group=gems&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          All Gems
        </button>
        
        <h4 style="margin-top: 1rem; margin-bottom: 0.5rem; color: var(--text-secondary); font-size: 0.9rem;">Metal Tiers</h4>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=iron&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          ⚙️ Iron
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=bronze&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          🥉 Bronze
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=copper&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          🟤 Copper
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=silver&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          🥈 Silver
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=gold&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          🥇 Gold
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=platinum&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          💎 Platinum
        </button>
        
        <h4 style="margin-top: 1rem; margin-bottom: 0.5rem; color: var(--text-secondary); font-size: 0.9rem;">Gem Tiers</h4>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=ruby&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          💎 Ruby
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=sapphire&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          💠 Sapphire
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=emerald&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          💚 Emerald
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?tier=diamond&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          💠 Diamond
        </button>
        
        <h4 style="margin-top: 1rem; margin-bottom: 0.5rem; color: var(--text-secondary); font-size: 0.9rem;">Special</h4>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?special=slow_buy&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          Slow Buy
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?special=one_gp_dump&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          1GP Dumps
        </button>
        <button 
          class="filter-btn"
          hx-get="/api/dumps?special=super&format=html"
          hx-target="#dumps-table"
          hx-swap="innerHTML"
          onclick="document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); this.classList.add('active');">
          Super
        </button>
      </div>
    </aside>
    
    <main class="main-content">
      <div id="dumps-table" 
           hx-get="/api/dumps?format=html" 
           hx-trigger="load"
           hx-swap="innerHTML">
        <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
          Loading dump opportunities...
        </div>
      </div>
    </main>
  </div>

  <footer>
    <p>Auto-refreshes every 10 seconds • Last updated: <span id="lastUpdate"></span></p>
  </footer>

  <script>
    // Update last update time
    function updateTime() {
      const now = new Date();
      document.getElementById('lastUpdate').textContent = now.toLocaleTimeString();
    }
    updateTime();
    setInterval(updateTime, 1000);

    // Auto-refresh table every 10 seconds
    setInterval(() => {
      const activeBtn = document.querySelector('.filter-btn.active');
      if (activeBtn && activeBtn.getAttribute('hx-get')) {
        htmx.trigger(activeBtn, 'click');
      } else {
        htmx.trigger('#dumps-table', 'load');
      }
    }, 10000);

    // Handle watch button success
    document.body.addEventListener('htmx:afterSwap', function(event) {
      if (event.detail.target.classList.contains('watch-btn')) {
        event.detail.target.textContent = 'Watching';
        event.detail.target.classList.add('watching');
        event.detail.target.disabled = true;
      }
    });
  </script>
</body>
</html>
"""

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
          <td>{{ dump.quality or '—' }}</td>
          <td class="dump">-{{ "%.1f"|format(dump.drop_pct) }}%</td>
          <td>{{ "%.1f"|format((dump.volume / dump.prev * 100) if dump.prev and dump.prev > 0 else 0) }}%</td>
          <td>{{ "%.1f"|format((dump.volume / dump.limit * 100) if dump.limit and dump.limit > 0 else 0) }}%</td>
          <td>{{ "{:,}".format(dump.max_buy_4h) if dump.max_buy_4h else "—" }}</td>
          <td>
            <span class="price-buy">{{ "{:,}".format(dump.buy) }}</span> / 
            <span class="price-sell">{{ "{:,}".format(dump.sell) }}</span>
          </td>
          <td>
            {% if dump.quality %}
              <span class="status-badge {{ 'danger' if 'NUCLEAR' in dump.quality or 'GOD-TIER' in dump.quality else 'warning' if 'ELITE' in dump.quality else 'success' }}">
                {{ dump.quality }}
              </span>
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

def load_names():
    """Load item names from cache with proper error handling"""
    global item_names
    cache_path = os.path.join(os.path.dirname(__file__), "utils", "item_cache.json")
    if not os.path.exists(cache_path):
        # Try alternative paths
        cache_path = "utils/item_cache.json"
        if not os.path.exists(cache_path):
            cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "utils", "item_cache.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                item_names = json.load(f)
            print(f"Loaded {len(item_names)} items from cache")
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ERROR] Failed to load item cache: {e}")
            item_names = {}
    else:
        item_names = {}
        print("[WARNING] Item cache not found, item names will be unavailable")
    
    # Auto-update in background
    def updater():
        time.sleep(10)
        try:
            import utils.cache_updater
            utils.cache_updater.update_cache()
        except Exception as e:
            print(f"[ERROR] Cache updater failed: {e}")
    threading.Thread(target=updater, daemon=True).start()

# Time window endpoints mapping
TIME_WINDOWS = {
    "5m": "5m",
    "10m": "10m", 
    "15m": "15m",
    "20m": "20m",
    "25m": "25m",
    "30m": "30m",
    "1h": "1h",
    "3h": "3h",
    "8h": "8h",
    "12h": "12h",
    "24h": "24h",
    "7d": "7d",
    "14d": "14d"
}

def fetch_with_fallback(url, headers, fallback_url=None, fallback_headers=None, timeout=30):
    """
    Fetch data from primary API with automatic fallback to secondary API.
    Returns (data, source) where source is 'primary' or 'fallback'
    """
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json(), 'primary'
    except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
        print(f"[WARN] Primary API failed ({url}): {e}")
        if fallback_url and fallback_headers:
            try:
                print(f"[INFO] Attempting fallback API: {fallback_url}")
                response = requests.get(fallback_url, headers=fallback_headers, timeout=timeout)
                response.raise_for_status()
                return response.json(), 'fallback'
            except Exception as fallback_error:
                print(f"[ERROR] Fallback API also failed: {fallback_error}")
                raise
        raise

def convert_1h_data_to_dict(h1_data):
    """
    Convert 1h price data to dict format for easier access.
    OSRS API /1h endpoint returns: {"data": {"2": {"avgHighPrice": 2550, "highPriceVolume": 100, ...}}}
    We need: {"2": {"avgHighPrice": 2550, "volume": 500, ...}}
    """
    if isinstance(h1_data, dict) and "data" in h1_data:
        data = h1_data["data"]
        # Check if data is already a dict (new format) or array (old format)
        if isinstance(data, dict):
            # Already in dict format - just convert to our expected structure
            result = {}
            for item_id, item_data in data.items():
                # Calculate volume from highPriceVolume and lowPriceVolume
                volume = (item_data.get("highPriceVolume", 0) or 0) + (item_data.get("lowPriceVolume", 0) or 0)
                result[str(item_id)] = {
                    "avgHighPrice": item_data.get("avgHighPrice"),
                    "avgLowPrice": item_data.get("avgLowPrice"),
                    "volume": volume,
                    "timestamp": item_data.get("timestamp")
                }
            return result
        elif isinstance(data, list):
            # Array format (legacy) - convert to dict
            result = {}
            for item in data:
                item_id = str(item.get("id"))
                result[item_id] = {
                    "avgHighPrice": item.get("avgHighPrice"),
                    "avgLowPrice": item.get("avgLowPrice"),
                    "volume": item.get("volume", 0),
                    "timestamp": item.get("timestamp")
                }
            return result
    elif isinstance(h1_data, dict):
        # Already in dict format (fallback API might return different format)
        return h1_data
    return {}

def fetch_all():
    global top_items, dump_items, spike_items, all_items
    try:
        # Fetch latest prices with fallback
        latest, latest_source = fetch_with_fallback(
            f"{BASE}/latest",
            HEADERS,
            f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None,
            timeout=30
        )
        if latest_source == 'fallback':
            print("[INFO] Using fallback API for latest prices")
        
        # Fetch 1-hour prices with fallback - use correct endpoint /1h
        h1_raw, h1_source = fetch_with_fallback(
            f"{BASE}/1h",
            HEADERS,
            None,  # Fallback API doesn't support 1h endpoint
            None,
            timeout=30
        )
        if h1_source == 'fallback':
            print("[INFO] Using fallback API for 1h prices")
        
        # Convert 1h data from array format to dict format
        h1 = convert_1h_data_to_dict(h1_raw)
        
        # Fetch mapping with fallback
        mapping, mapping_source = fetch_with_fallback(
            f"{BASE}/mapping",
            HEADERS,
            f"{FALLBACK_BASE}/mapping" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None,
            timeout=30
        )
        if mapping_source == 'fallback':
            print("[INFO] Using fallback API for mapping")
        
        # Build ID → limit map
        limit_map = {str(m['id']): m.get('limit', 0) for m in mapping}
        
        margins, dumps, spikes, all_items = [], [], [], []
        for id_str, data in latest.get("data", {}).items():
            if not data.get("high") or not data.get("low"):
                continue
            low, high = data["low"], data["high"]
            name = item_names.get(id_str, f"Item {id_str}")
            vol = h1.get(id_str, {}).get("volume", 0) or 1
            limit = limit_map.get(id_str, 0)
            
            log_price(int(id_str), low, high, vol)
            
            # INSTA BUY/SELL (instant buy = high, instant sell = low)
            insta_buy = data.get('high', low)  # Highest price to buy instantly
            insta_sell = data.get('low', high)  # Lowest price to sell instantly
            
            # Calculate profit and ROI
            profit = high - low - ge_tax(high)
            roi = (profit / low * 100) if low > 0 else 0
            
            # Calculate risk metrics
            risk_metrics = calculate_risk_metrics(low, high, insta_buy, insta_sell, vol, limit, profit)
            
            # Add to all_items for volume tracker
            all_items.append({
                "id": int(id_str),
                "name": name,
                "buy": low,
                "sell": high,
                "insta_buy": insta_buy,
                "insta_sell": insta_sell,
                "profit": profit,
                "roi": roi,
                "volume": vol,
                "limit": limit,
                **risk_metrics  # Add all risk metrics
            })
            
            # === MARGINS ===
            # Lowered minimum price from 1k to allow cheaper items
            if profit > CONFIG["thresholds"]["margin_min"] and low > 100:
                # Get price historicals for margins/flips
                historicals = get_price_historicals(int(id_str))
                margins.append({
                    "id": int(id_str), "name": name, "buy": low, "sell": high,
                    "insta_buy": insta_buy, "insta_sell": insta_sell,
                    "profit": profit, "roi": roi, "volume": vol, "limit": limit,
                    **risk_metrics,  # Add risk metrics to margins
                    **historicals  # Add price historicals
                })
            
            # === DUMPS & SPIKES ===
            # Lowered price threshold from 500k to 10k to catch more items
            if vol > CONFIG["thresholds"]["min_volume"] and low > 10000:
                h1_data = h1.get(id_str, {})
                prev_avg = h1_data.get("avgHighPrice", high) or high
                drop_pct = (prev_avg - low) / prev_avg * 100
                rise_pct = (high - prev_avg) / prev_avg * 100
                
                # PROFIT CALCS
                max_profit_4h = (high - low) * min(vol, limit * 4) * 0.99
                realistic_profit = (high - low) * limit * 0.99

                # === DUMP DETECTION ===
                if drop_pct > CONFIG["thresholds"]["dump_drop_pct"]:
                    quality_stars, quality_label = get_dump_quality(drop_pct, vol, low)
                    # Calculate risk for dumps
                    dump_risk = calculate_risk_metrics(low, high, insta_buy, insta_sell, vol, limit, profit)
                    # Get price historicals
                    historicals = get_price_historicals(int(id_str))
                    dumps.append({
                        "id": int(id_str),
                        "name": name,
                        "buy": low,
                        "sell": high,
                        "drop_pct": drop_pct,
                        "volume": vol,
                        "prev": prev_avg,
                        "quality": quality_stars,
                        "quality_label": quality_label,
                        "limit": limit,
                        "insta_buy": insta_buy,
                        "insta_sell": insta_sell,
                        "max_profit_4h": max_profit_4h,
                        "realistic_profit": realistic_profit,
                        "cost_per_limit": low * limit,
                        **dump_risk,  # Add risk metrics
                        **historicals  # Add price historicals
                    })

                # === SPIKE DETECTION ===
                if rise_pct > CONFIG["thresholds"]["spike_rise_pct"]:
                    # Calculate risk for spikes
                    spike_risk = calculate_risk_metrics(low, high, insta_buy, insta_sell, vol, limit, profit)
                    # Get price historicals
                    historicals = get_price_historicals(int(id_str))
                    spikes.append({
                        "id": int(id_str),
                        "name": name,
                        "buy": low,
                        "sell": high,
                        "rise_pct": rise_pct,
                        "volume": vol,
                        "prev": prev_avg,
                        "limit": limit,
                        "insta_buy": insta_buy,
                        "insta_sell": insta_sell,
                        **spike_risk,  # Add risk metrics
                        **historicals  # Add price historicals
                    })
        
        # Use lock to ensure thread-safe updates to global variables
        with _item_lock:
            top_items = sorted(margins, key=lambda x: x["profit"], reverse=True)[:50]
            dump_items = sorted(dumps, key=lambda x: x["volume"] * x["drop_pct"], reverse=True)[:20]
            spike_items = sorted(spikes, key=lambda x: x["rise_pct"], reverse=True)[:20]
            # all_items is already updated in the loop above
        print(f"[+] {len(top_items)} flips | {len(dump_items)} dumps | {len(spike_items)} spikes")
    except Exception as e:
        print(f"[ERROR] fetch_all: {e}")
        import traceback
        traceback.print_exc()

def notify(title, items, color):
    if not items:
        return
    webhook = DiscordWebhook(url=CONFIG["discord_webhook"], rate_limit_retry=True)
    for item in items[:5]:
        item_name = item.get('name', 'Unknown')
        item_id = item.get('id', 0)
        thumbnail_url = get_item_thumbnail_url(item_name)
        
        # Get prices
        buy_price = item.get('buy', 0)
        sell_price = item.get('sell', 0)
        insta_buy = item.get('insta_buy', buy_price)
        insta_sell = item.get('insta_sell', sell_price)
        
        # Build price description with instant buy/sell if different
        price_desc = f"Price: {buy_price:,} GP → {sell_price:,} GP"
        if insta_buy != buy_price or insta_sell != sell_price:
            price_desc += f"\n**Insta Buy:** {insta_buy:,} GP | **Insta Sell:** {insta_sell:,} GP"
        
        # Add risk information
        risk_score = item.get('risk_score', 0)
        risk_level = item.get('risk_level', 'UNKNOWN')
        profitability_confidence = item.get('profitability_confidence', 0)
        liquidity_score = item.get('liquidity_score', 0)
        
        risk_info = f"\n**Risk:** {risk_level} ({risk_score:.1f}/100) | **Confidence:** {profitability_confidence:.1f}% | **Liquidity:** {liquidity_score:.1f}%"
        
        # Build price historicals
        historicals_text = ""
        avg_7d = item.get('avg_7d')
        avg_24h = item.get('avg_24h')
        avg_12h = item.get('avg_12h')
        avg_6h = item.get('avg_6h')
        avg_1h = item.get('avg_1h')
        prev_price = item.get('prev_price')
        prev_timestamp = item.get('prev_timestamp')
        
        if avg_7d or avg_24h or avg_12h or avg_6h or avg_1h or prev_price:
            historicals_text = "\n\n**Price Historicals:**\n"
            if avg_7d:
                historicals_text += f"7d: {avg_7d:,} GP | "
            if avg_24h:
                historicals_text += f"24h: {avg_24h:,} GP | "
            if avg_12h:
                historicals_text += f"12h: {avg_12h:,} GP | "
            if avg_6h:
                historicals_text += f"6h: {avg_6h:,} GP | "
            if avg_1h:
                historicals_text += f"1h: {avg_1h:,} GP"
            if prev_price:
                from datetime import datetime
                if prev_timestamp:
                    hours_ago = (datetime.now().timestamp() - prev_timestamp) / 3600
                    historicals_text += f"\nPrev: {prev_price:,} GP ({hours_ago:.1f} hours ago)"
        
        embed = {
            "title": f"{title} {item.get('quality', '')}",
            "description": f"**{item_name}**\n"
                          f"{price_desc}\n"
                          f"Move: {item.get('drop_pct', item.get('rise_pct', 0)):.1f}%\n"
                          f"Vol: **{item['volume']:,}** | {item.get('quality_label', '')}"
                          f"{risk_info}"
                          f"{historicals_text}",
            "url": f"https://prices.runescape.wiki/osrs/item/{item_id}",
            "color": color
        }
        
        # Add thumbnail if available
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
        
        webhook.add_embed(embed)
    threading.Thread(target=webhook.execute).start()

def poll():
    """Main polling loop with proper error handling"""
    print("[POLL] Starting GE activity tracking...")
    load_names()
    last_dumps = []
    last_spikes = []
    consecutive_errors = 0
    max_consecutive_errors = 10
    poll_count = 0
    
    while True:
        try:
            poll_count += 1
            if poll_count % 10 == 0:  # Log every 10 polls (every ~80 seconds)
                print(f"[POLL] Tracking active - completed {poll_count} polls")
            fetch_all()
            consecutive_errors = 0  # Reset error counter on success
            
            # Thread-safe access to items
            with _item_lock:
                current_dumps = dump_items[:10]
                current_spikes = spike_items[:10]
            
            # Find new items (compare by ID to avoid false positives)
            new_dumps = [d for d in current_dumps if d.get('id') not in [ld.get('id') for ld in last_dumps]]
            new_spikes = [s for s in current_spikes if s.get('id') not in [ls.get('id') for ls in last_spikes]]
            
            if new_dumps:
                notify("DUMP DETECTED — BUY THE PANIC", new_dumps, 0x8B0000)
            if new_spikes:
                notify("SPIKE DETECTED — SELL NOW", new_spikes, 0x00FF00)
            
            last_dumps = current_dumps
            last_spikes = current_spikes
            
        except Exception as e:
            consecutive_errors += 1
            print(f"[ERROR] poll error ({consecutive_errors}/{max_consecutive_errors}): {e}")
            import traceback
            traceback.print_exc()
            
            # If too many consecutive errors, wait longer before retrying
            if consecutive_errors >= max_consecutive_errors:
                print(f"[ERROR] Too many consecutive errors, waiting 60 seconds before retry")
                time.sleep(60)
                consecutive_errors = 0
            else:
                time.sleep(2)  # Fast polling rate - 2 seconds
        else:
            time.sleep(2)  # Fast polling rate - 2 seconds

def needs_setup():
    """Check if initial setup is needed"""
    if not CONFIG:
        return True
    
    # Check if config has placeholder values
    token = CONFIG.get('discord_token', '')
    admin_key = CONFIG.get('admin_key', '')
    
    # Check for placeholder values
    if (token in ['YOUR_BOT_TOKEN_HERE', '', None] or
        admin_key in ['CHANGE_THIS_TO_A_SECURE_RANDOM_STRING', '', None]):
        return True
    
    return False

def is_local_request():
    """Check if request is from local network (LAN only)"""
    if not request.remote_addr:
        return False
    
    if request.remote_addr in ['127.0.0.1', 'localhost', '::1']:
        return True
    
    # Check if it's a local IP (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    try:
        ip_parts = request.remote_addr.split('.')
        if len(ip_parts) == 4:
            first_octet = ip_parts[0]
            second_octet = int(ip_parts[1]) if len(ip_parts) > 1 else 0
            
            if first_octet == '192' and ip_parts[1] == '168':
                return True
            if first_octet == '10':
                return True
            if first_octet == '172' and 16 <= second_octet <= 31:
                return True
    except (ValueError, IndexError):
        pass
    
    return False

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Only add CSP for HTML responses
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
    return response

@app.before_request
def check_setup():
    """Check setup status - frontend handles redirects"""
    # Allow access to API endpoints
    if request.path.startswith('/api'):
        return None
    
    # Allow access to static files
    if request.path.startswith('/static'):
        return None
    
    # For admin endpoints, check LAN-only access
    if request.path.startswith('/admin') or request.path.startswith('/config'):
        if not is_local_request():
            return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    return None

@app.route('/')
def index():
    # Redirect to Next.js frontend
    return redirect('http://localhost:3000')

@app.route('/dashboard')
@rate_limit(max_requests=100, window=60)
def dashboard():
    """Tiered control panel dashboard with HTMX filters"""
    return render_template_string(DASHBOARD_TEMPLATE)

@app.route('/api/setup/status', methods=['GET'])
@rate_limit(max_requests=30, window=60)
def setup_status():
    """Check if setup is needed"""
    return jsonify({"needs_setup": needs_setup()})

# Initial setup now handled by Next.js frontend at /setup

# Legacy HTML routes removed - now using Next.js frontend
# Dashboard, volume tracker, admin, and config are now served by Next.js frontend

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for Docker"""
    return jsonify({"status": "healthy", "service": "backend"})

@app.route('/api/top')
@rate_limit(max_requests=200, window=60)
def api_top():
    """Get top flips with thread-safe access"""
    with _item_lock:
        return jsonify(top_items[:20])

@app.route('/api/dumps')
@rate_limit(max_requests=200, window=60)
def api_dumps():
    """
    Get dump opportunities using new dump engine with tier system
    Query params:
    - tier: iron, copper, bronze, silver, gold, platinum, ruby, sapphire, emerald, diamond
    - group: metals, gems (filters by item group)
    - special: slow_buy, one_gp_dump, super (filters by special type)
    - limit: max number of results
    - format: json (default) or html (for HTMX)
    """
    tier = request.args.get('tier', '').lower()
    group = request.args.get('group', '').lower()
    special = request.args.get('special', '').lower()
    limit = request.args.get('limit', type=int)
    response_format = request.args.get('format', 'json').lower()
    
    try:
        # Use new dump engine
        from utils.dump_engine import analyze_dumps
        opportunities_raw = analyze_dumps()
        
        opportunities = []
        for opp in opportunities_raw:
            # Filter by tier
            if tier and opp.get('tier', '').lower() != tier:
                continue
            
            # Filter by group
            if group and opp.get('group', '').lower() != group:
                continue
            
            # Filter by special type
            if special:
                flags = opp.get('flags', [])
                if special == 'slow_buy' and 'slow_buy' not in flags:
                    continue
                elif special == 'one_gp_dump' and 'one_gp_dump' not in flags:
                    continue
                elif special == 'super' and 'super' not in flags:
                    continue
            
            # Format opportunity for API response
            formatted_opp = {
                'id': opp.get('item_id'),
                'name': opp.get('name'),
                'tier': opp.get('tier'),
                'emoji': opp.get('emoji'),
                'tier_emoji': opp.get('emoji'),  # For compatibility
                'group': opp.get('group'),
                'score': opp.get('score'),
                'drop_pct': opp.get('drop_pct'),
                'vol_spike_pct': opp.get('vol_spike_pct'),
                'oversupply_pct': opp.get('oversupply_pct'),
                'volume': opp.get('volume'),
                'high': opp.get('high'),
                'low': opp.get('low'),
                'buy': opp.get('low'),  # For compatibility
                'sell': opp.get('high'),  # For compatibility
                'flags': opp.get('flags', []),
                'max_buy_4h': opp.get('max_buy_4h', 0),
                'limit': opp.get('max_buy_4h', 0),  # For compatibility
                'timestamp': opp.get('timestamp')
            }
            
            opportunities.append(formatted_opp)
        
        # Apply limit if specified
        if limit and limit > 0:
            opportunities = opportunities[:limit]
        
        # Return HTML for HTMX if requested
        if response_format == 'html':
            # Fallback to old format for HTML rendering
            from flask import render_template_string
            try:
                return render_template_string(DUMPS_TABLE_TEMPLATE, dumps=opportunities)
            except:
                pass
        
        return jsonify(opportunities)
        
    except Exception as e:
        print(f"[ERROR] api_dumps failed with new engine: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to old system if new engine fails
        with _item_lock:
            opportunities = []
            for dump in dump_items:
                max_buy_4h = get_buy_limit(dump.get('id', 0))
                dump_with_limit = {**dump, 'max_buy_4h': max_buy_4h}
                opportunities.append(dump_with_limit)
            
            if limit and limit > 0:
                opportunities = opportunities[:limit]
            
            if response_format == 'html':
                try:
                    from flask import render_template_string
                    return render_template_string(DUMPS_TABLE_TEMPLATE, dumps=opportunities)
                except:
                    pass
            
            return jsonify(opportunities)

@app.route('/api/dumps/<int:item_id>')
@rate_limit(max_requests=200, window=60)
def api_dumps_item(item_id):
    """Get dump opportunity for specific item with recent history"""
    with _item_lock:
        # Find opportunity for this item
        opportunity = None
        for dump in dump_items:
            if dump.get('id') == item_id:
                max_buy_4h = get_buy_limit(item_id)
                opportunity = {**dump, 'max_buy_4h': max_buy_4h}
                break
        
        # Get recent 5-minute history
        recent_history = get_recent_history(item_id, minutes=5)
        
        return jsonify({
            'opportunity': opportunity,
            'recent_history': recent_history
        })

@app.route('/api/spikes')
@rate_limit(max_requests=200, window=60)
def api_spikes():
    """Get spikes with thread-safe access"""
    with _item_lock:
        return jsonify(spike_items)

@app.route('/api/tiers')
@rate_limit(max_requests=100, window=60)
def api_tiers():
    """
    Get tier configuration for a guild
    Query params:
    - guild_id: Discord guild ID (required)
    
    Returns tier configuration with role mappings
    """
    guild_id = sanitize_guild_id(request.args.get('guild_id', ''))
    if not guild_id:
        return jsonify({"error": "Missing required parameter: guild_id"}), 400
    
    config = get_config(guild_id)
    
    # Extract tier configuration from server config
    # Default tier structure based on dump_engine.py tiers
    tiers_config = config.get("tiers", {})
    
    # If no tier config exists, return default structure
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

@app.route('/api/item/<int:item_id>')
@app.route('/api/item/search')
@rate_limit(max_requests=200, window=60)
def api_item(item_id=None):
    """
    Get item information by ID or search by name
    Query params:
    - q: Search query (item name fragment) - used when item_id not provided
    - item_id: Item ID (path parameter)
    
    Returns item details including max_buy_4h
    """
    # Handle search query
    if item_id is None:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({"error": "Missing query parameter 'q' or item_id"}), 400
        
        # Search for item by name
        with _item_lock:
            matching_items = []
            query_lower = query.lower()
            
            # Try to find exact match first
            for item in all_items:
                if item.get('name', '').lower() == query_lower:
                    matching_items = [item]
                    break
                elif query_lower in item.get('name', '').lower():
                    matching_items.append(item)
            
            # If no match in all_items, try metadata cache
            if not matching_items:
                from utils.item_metadata import _metadata_cache
                for cached_id, meta in _metadata_cache.items():
                    if query_lower in meta.get('name', '').lower():
                        # Build item dict from cache
                        item_data = {
                            'id': cached_id,
                            'name': meta.get('name', ''),
                            'limit': meta.get('buy_limit', 0)
                        }
                        # Try to get current prices
                        latest_data = {}
                        try:
                            latest, _ = fetch_with_fallback(
                                f"{BASE}/latest",
                                HEADERS,
                                f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
                                FALLBACK_HEADERS if FALLBACK_BASE else None,
                                timeout=10
                            )
                            latest_data = latest.get("data", {}).get(str(cached_id), {})
                        except:
                            pass
                        
                        item_data.update({
                            'buy': latest_data.get('low'),
                            'sell': latest_data.get('high'),
                            'volume': 0
                        })
                        matching_items.append(item_data)
                        if len(matching_items) >= 5:  # Limit results
                            break
            
            if not matching_items:
                return jsonify({"error": f"No items found matching '{query}'"}), 404
            
            # Return first match or list of matches
            if len(matching_items) == 1:
                item = matching_items[0]
            else:
                # Return list of matches
                return jsonify({
                    "matches": matching_items[:10],
                    "count": len(matching_items)
                })
    
    # Handle item ID lookup
    else:
        # Get item from all_items or metadata
        item = None
        with _item_lock:
            for i in all_items:
                if i.get('id') == item_id:
                    item = i
                    break
        
        if not item:
            # Try metadata cache
            from utils.item_metadata import get_item_meta
            meta = get_item_meta(item_id)
            if not meta:
                return jsonify({"error": f"Item {item_id} not found"}), 404
            
            # Build item dict
            item = {
                'id': item_id,
                'name': meta.get('name', ''),
                'limit': meta.get('buy_limit', 0)
            }
            
            # Get current prices
            try:
                latest, _ = fetch_with_fallback(
                    f"{BASE}/latest",
                    HEADERS,
                    f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
                    FALLBACK_HEADERS if FALLBACK_BASE else None,
                    timeout=10
                )
                latest_data = latest.get("data", {}).get(str(item_id), {})
                item.update({
                    'buy': latest_data.get('low'),
                    'sell': latest_data.get('high'),
                    'volume': 0
                })
            except:
                pass
    
    # Add max_buy_4h (buy limit)
    max_buy_4h = get_buy_limit(item.get('id', 0))
    item['max_buy_4h'] = max_buy_4h
    
    # Check if there's a current dump opportunity
    opportunity = None
    with _item_lock:
        for dump in dump_items:
            if dump.get('id') == item.get('id'):
                opportunity = dump
                break
    
    # Also check new dump engine
    try:
        from utils.dump_engine import analyze_dumps
        opportunities = analyze_dumps()
        for opp in opportunities:
            if opp.get('item_id') == item.get('id'):
                opportunity = {
                    'tier': opp.get('tier'),
                    'score': opp.get('score'),
                    'drop_pct': opp.get('drop_pct'),
                    'emoji': opp.get('emoji')
                }
                break
    except:
        pass
    
    result = {
        'id': item.get('id'),
        'name': item.get('name'),
        'buy': item.get('buy'),
        'sell': item.get('sell'),
        'high': item.get('sell'),
        'low': item.get('buy'),
        'volume': item.get('volume', 0),
        'max_buy_4h': max_buy_4h,
        'limit': max_buy_4h
    }
    
    if opportunity:
        result['opportunity'] = opportunity
    
    return jsonify(result)

# Recipe and Decant API endpoints
@app.route('/api/recipe', methods=['GET'])
@rate_limit(max_requests=200, window=60)
def api_recipe():
    """Get recipe information with current prices"""
    name = request.args.get('name', '').strip()
    
    if not name:
        return jsonify({"error": "Missing required parameter: name"}), 400
    
    try:
        recipe = get_recipe(name)
        if not recipe:
            return jsonify({"error": f"Recipe not found for: {name}"}), 404
        
        product_id = recipe['product_id']
        ingredients = recipe['ingredients']
        
        # Fetch latest prices
        try:
            latest, _ = fetch_with_fallback(
                f"{BASE}/latest",
                HEADERS,
                f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
                FALLBACK_HEADERS if FALLBACK_BASE else None,
                timeout=10
            )
            price_data = latest.get("data", {})
        except Exception as e:
            print(f"[WARN] Failed to fetch prices for recipe: {e}")
            price_data = {}
        
        # Get product info
        product_meta = get_item_meta(product_id)
        product_price_data = price_data.get(str(product_id), {})
        product_low = product_price_data.get("low")
        product_high = product_price_data.get("high")
        product_max_buy_4h = product_meta.get('buy_limit', 0) if product_meta else 0
        
        product_info = {
            "id": product_id,
            "name": product_meta.get('name', f'Item {product_id}') if product_meta else f'Item {product_id}',
            "low": product_low,
            "high": product_high,
            "max_buy_4h": product_max_buy_4h
        }
        
        # Get ingredient info
        ingredient_list = []
        total_ingredient_cost_low = 0
        total_ingredient_cost_high = 0
        
        for ing in ingredients:
            ing_id = ing['id']
            ing_meta = get_item_meta(ing_id)
            ing_price_data = price_data.get(str(ing_id), {})
            ing_low = ing_price_data.get("low")
            ing_high = ing_price_data.get("high")
            ing_max_buy_4h = ing_meta.get('buy_limit', 0) if ing_meta else 0
            
            if ing_low:
                total_ingredient_cost_low += ing_low
            if ing_high:
                total_ingredient_cost_high += ing_high
            
            ingredient_list.append({
                "id": ing_id,
                "name": ing['name'],
                "low": ing_low,
                "high": ing_high,
                "max_buy_4h": ing_max_buy_4h
            })
        
        # Calculate spread info
        spread_info = {}
        if product_low and product_high and total_ingredient_cost_low:
            # Profit if buying ingredients low and selling product high
            profit_low_high = product_high - total_ingredient_cost_low
            # Profit if buying ingredients high and selling product low
            profit_high_low = product_low - total_ingredient_cost_high
            
            spread_info = {
                "total_ingredient_cost_low": total_ingredient_cost_low,
                "total_ingredient_cost_high": total_ingredient_cost_high,
                "product_low": product_low,
                "product_high": product_high,
                "profit_low_high": profit_low_high,
                "profit_high_low": profit_high_low,
                "spread": product_high - product_low if product_high and product_low else None
            }
        
        return jsonify({
            "product": product_info,
            "ingredients": ingredient_list,
            "spread_info": spread_info
        })
        
    except Exception as e:
        print(f"[ERROR] api_recipe: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/decant', methods=['GET'])
@rate_limit(max_requests=200, window=60)
def api_decant():
    """Get decant information for a potion base name"""
    name = request.args.get('name', '').strip()
    
    if not name:
        return jsonify({"error": "Missing required parameter: name"}), 400
    
    try:
        decant_set = get_decant_set(name)
        if not decant_set:
            return jsonify({"error": f"Decant set not found for: {name}"}), 404
        
        # Fetch latest prices
        try:
            latest, _ = fetch_with_fallback(
                f"{BASE}/latest",
                HEADERS,
                f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
                FALLBACK_HEADERS if FALLBACK_BASE else None,
                timeout=10
            )
            price_data = latest.get("data", {})
        except Exception as e:
            print(f"[WARN] Failed to fetch prices for decant: {e}")
            price_data = {}
        
        # Build dose list with prices
        dose_list = []
        for dose_item in decant_set:
            dose_id = dose_item['id']
            dose_meta = get_item_meta(dose_id)
            dose_price_data = price_data.get(str(dose_id), {})
            dose_low = dose_price_data.get("low")
            dose_high = dose_price_data.get("high")
            dose_max_buy_4h = dose_meta.get('buy_limit', 0) if dose_meta else 0
            
            dose_list.append({
                "id": dose_id,
                "name": dose_item['name'],
                "low": dose_low,
                "high": dose_high,
                "max_buy_4h": dose_max_buy_4h
            })
        
        return jsonify(dose_list)
        
    except Exception as e:
        print(f"[ERROR] api_decant: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Watchlist API endpoints
@app.route('/api/watchlist/add', methods=['POST'])
@rate_limit(max_requests=100, window=60)
@validate_json_payload(max_size=1000)
def api_watchlist_add():
    """Add item to watchlist"""
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        guild_id = sanitize_guild_id(data.get('guild_id', ''))
        user_id = data.get('user_id')  # Optional, can be None
        item_id = data.get('item_id')
        item_name = data.get('item_name', '')
        
        if not guild_id or not item_id:
            return jsonify({"error": "Missing required fields: guild_id, item_id"}), 400
        
        # Get item name if not provided
        if not item_name:
            item_meta = get_item_meta(item_id)
            if item_meta:
                item_name = item_meta.get('name', f'Item {item_id}')
            else:
                item_name = f'Item {item_id}'
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Insert or ignore (if already exists)
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

@app.route('/api/watchlist/remove', methods=['POST'])
@rate_limit(max_requests=100, window=60)
@validate_json_payload(max_size=1000)
def api_watchlist_remove():
    """Remove item from watchlist"""
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        guild_id = sanitize_guild_id(data.get('guild_id', ''))
        user_id = data.get('user_id')  # Optional
        item_id = data.get('item_id')
        
        if not guild_id or not item_id:
            return jsonify({"error": "Missing required fields: guild_id, item_id"}), 400
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Remove matching entry
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

@app.route('/api/watchlist', methods=['GET'])
@rate_limit(max_requests=200, window=60)
def api_watchlist_get():
    """Get watchlist items for a guild (optionally filtered by user)"""
    try:
        guild_id = sanitize_guild_id(request.args.get('guild_id', ''))
        user_id = request.args.get('user_id')
        
        if not guild_id:
            return jsonify({"error": "Missing required parameter: guild_id"}), 400
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Query watchlist
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

# Item lookup API endpoints
@app.route('/api/item/<int:item_id>', methods=['GET'])
@rate_limit(max_requests=200, window=60)
def api_item_get(item_id):
    """Get item information including metadata, prices, and current opportunity"""
    try:
        # Get item metadata
        item_meta = get_item_meta(item_id)
        if not item_meta:
            return jsonify({"error": "Item not found"}), 404
        
        max_buy_4h = item_meta.get('buy_limit', 0)
        item_name = item_meta.get('name', f'Item {item_id}')
        
        # Get latest price data
        try:
            latest, _ = fetch_with_fallback(
                f"{BASE}/latest",
                HEADERS,
                f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
                FALLBACK_HEADERS if FALLBACK_BASE else None,
                timeout=10
            )
            
            price_data = latest.get("data", {}).get(str(item_id), {})
            low = price_data.get("low")
            high = price_data.get("high")
            insta_buy = price_data.get("high", low)  # Instant buy = high price
            insta_sell = price_data.get("low", high)  # Instant sell = low price
            
            # Get 1h volume
            h1_raw, _ = fetch_with_fallback(
                f"{BASE}/1h",
                HEADERS,
                None,
                None,
                timeout=10
            )
            h1 = convert_1h_data_to_dict(h1_raw)
            volume = h1.get(str(item_id), {}).get("volume", 0) or 0
            
        except Exception as e:
            print(f"[WARN] Failed to fetch price data for item {item_id}: {e}")
            low = None
            high = None
            insta_buy = None
            insta_sell = None
            volume = 0
        
        # Get price historicals
        historicals = get_price_historicals(item_id)
        
        # Check for current dump opportunity
        opportunity = None
        with _item_lock:
            for dump in dump_items:
                if dump.get('id') == item_id:
                    opportunity = {**dump, 'max_buy_4h': max_buy_4h}
                    break
        
        # Build response
        result = {
            "id": item_id,
            "name": item_name,
            "max_buy_4h": max_buy_4h,
            "low": low,
            "high": high,
            "insta_buy": insta_buy,
            "insta_sell": insta_sell,
            "volume": volume,
            "opportunity": opportunity,
            **historicals
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"[ERROR] api_item_get: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/item/search', methods=['GET'])
@rate_limit(max_requests=200, window=60)
def api_item_search():
    """Search for items by name fragment"""
    query = request.args.get('q', '').strip().lower()
    
    if not query or len(query) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400
    
    try:
        # Search in item_names cache
        matches = []
        with _item_lock:
            for item_id_str, name in item_names.items():
                if query in name.lower():
                    item_id = int(item_id_str)
                    max_buy_4h = get_buy_limit(item_id)
                    matches.append({
                        "id": item_id,
                        "name": name,
                        "max_buy_4h": max_buy_4h
                    })
                    # Limit results
                    if len(matches) >= 50:
                        break
        
        # Sort by name
        matches.sort(key=lambda x: x['name'])
        
        return jsonify(matches)
        
    except Exception as e:
        print(f"[ERROR] api_item_search: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/all_items')
@rate_limit(max_requests=100, window=60)
def api_all_items():
    """API endpoint for volume tracker - returns all items with filtering support"""
    time_window = request.args.get('time_window', '1h', type=str)
    
    # Fetch data for the requested time window (validated against allowlist)
    time_data = {}
    if time_window in TIME_WINDOWS:
        try:
            # Use correct endpoint path for 1h: /1h
            if time_window == "1h":
                endpoint = f"{BASE}/1h"
                fallback_endpoint = None  # Fallback API doesn't support 1h endpoint
            else:
                endpoint = f"{BASE}/{time_window}"
                fallback_endpoint = f"{FALLBACK_BASE}/{time_window}" if FALLBACK_BASE else None
            
            time_data_raw, _ = fetch_with_fallback(
                endpoint,
                HEADERS,
                fallback_endpoint,
                FALLBACK_HEADERS if FALLBACK_BASE else None,
                timeout=30
            )
            # Convert to expected format if needed
            if time_window == "1h" and isinstance(time_data_raw, dict) and "data" in time_data_raw:
                # Convert array format to dict format
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
    
    with _item_lock:
        # Merge time window data with existing items
        items_with_volume = []
        for item in all_items:
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

@app.route('/api/osrs_status')
@rate_limit(max_requests=30, window=60)
def api_osrs_status():
    """Check OSRS Wiki API connection status with fallback"""
    try:
        data, source = fetch_with_fallback(
            f"{BASE}/latest",
            HEADERS,
            f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None,
            timeout=10
        )
        item_count = len(data.get("data", {}))
        return jsonify({
            "status": "connected",
            "online": True,
            "item_count": item_count,
            "source": source,  # 'primary' or 'fallback'
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

@app.route('/api/recent_trades')
@rate_limit(max_requests=100, window=60)
def api_recent_trades():
    """Get recent trades from database"""
    limit = request.args.get('limit', 50, type=int)
    if limit not in [25, 50, 100, 200]:
        limit = 50
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get recent trades
        c.execute("""
            SELECT item_id, timestamp, low, high, volume
            FROM prices
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        rows = c.fetchall()
        trades = []
        for row in rows:
            item_id = row[0]
            timestamp = row[1]
            low = row[2]
            high = row[3]
            volume = row[4]
            
            # Get item name from cache
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

@app.route('/api/nightly')
@rate_limit(max_requests=50, window=60)
def api_nightly():
    """
    API endpoint for overnight flip recommendations
    Analyzes items for best 8-16 hour profit potential
    """
    min_profit = request.args.get('min_profit', 1_000_000, type=int)
    
    try:
        # Get all items with their data using fallback
        latest, _ = fetch_with_fallback(
            f"{BASE}/latest",
            HEADERS,
            f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None,
            timeout=30
        )
        
        # Fetch 1-hour prices - use correct endpoint /1h
        h1_raw, _ = fetch_with_fallback(
            f"{BASE}/1h",
            HEADERS,
            None,  # Fallback API doesn't support 1h endpoint
            None,
            timeout=30
        )
        h1 = convert_1h_data_to_dict(h1_raw)
        
        mapping, _ = fetch_with_fallback(
            f"{BASE}/mapping",
            HEADERS,
            f"{FALLBACK_BASE}/mapping" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None,
            timeout=30
        )
        
        limit_map = {str(m['id']): m.get('limit', 0) for m in mapping}
        
        overnight_opportunities = []
        
        for id_str, data in latest.get("data", {}).items():
            if not data.get("high") or not data.get("low"):
                continue
            
            low, high = data["low"], data["high"]
            name = item_names.get(id_str, f"Item {id_str}")
            vol = h1.get(id_str, {}).get("volume", 0) or 1
            limit = limit_map.get(id_str, 0)
            
            # Skip items with no limit or very low volume
            if limit == 0 or vol < 1000:
                continue
            
            # Get price historicals
            historicals = get_price_historicals(int(id_str))
            avg_24h = historicals.get('avg_24h')
            avg_12h = historicals.get('avg_12h')
            avg_6h = historicals.get('avg_6h')
            avg_1h = historicals.get('avg_1h')
            
            # Skip if we don't have enough historical data
            if not avg_24h or not avg_12h:
                continue
            
            # INSTA BUY/SELL
            insta_buy = data.get('high', low)
            insta_sell = data.get('low', high)
            
            # Calculate current profit
            current_profit = high - low - ge_tax(high)
            current_roi = (current_profit / low * 100) if low > 0 else 0
            
            # Calculate risk metrics
            risk_metrics = calculate_risk_metrics(low, high, insta_buy, insta_sell, vol, limit, current_profit)
            
            # Overnight prediction logic:
            # 1. Items that are currently below their 24h average (potential recovery)
            # 2. Items with consistent volume (reliable)
            # 3. Items with good liquidity (can actually flip)
            # 4. Items with low risk (safer overnight)
            
            # Calculate price deviation from 24h average
            price_deviation = ((avg_24h - low) / avg_24h * 100) if avg_24h > 0 else 0
            
            # Calculate trend (is price recovering?)
            trend_score = 0
            if avg_6h and avg_12h and avg_24h:
                # Positive trend if current price is higher than 6h average
                if avg_6h > 0:
                    trend_6h = ((low - avg_6h) / avg_6h * 100) if avg_6h > 0 else 0
                    trend_12h = ((avg_6h - avg_12h) / avg_12h * 100) if avg_12h > 0 else 0
                    # Positive trend if both are positive or recovering
                    if trend_6h > -2 and trend_12h > -5:  # Not dropping too fast
                        trend_score = 50
                    if trend_6h > 0:  # Actually recovering
                        trend_score = 75
            
            # Volume consistency (higher is better for overnight)
            volume_consistency = min(100, (vol / 10000) * 20)  # 50k volume = 100 score
            
            # Overnight profit prediction
            # Base prediction on: current profit + recovery potential
            recovery_potential = (avg_24h - low) * limit * 0.99 if price_deviation > 0 else 0
            overnight_profit = current_profit * limit + recovery_potential * 0.5  # Conservative estimate
            
            # Skip if overnight profit is too low
            if overnight_profit < min_profit:
                continue
            
            overnight_roi = (overnight_profit / (low * limit) * 100) if low * limit > 0 else 0
            
            # Overnight confidence calculation
            # Factors: price deviation, trend, volume consistency, liquidity, risk
            confidence = 0
            confidence += min(30, price_deviation * 2) if price_deviation > 0 else 0  # Up to 30% for undervalued
            confidence += trend_score * 0.2  # Up to 15% for positive trend
            confidence += volume_consistency * 0.2  # Up to 20% for consistent volume
            confidence += risk_metrics.get('liquidity_score', 0) * 0.15  # Up to 15% for liquidity
            confidence += max(0, 100 - risk_metrics.get('risk_score', 50)) * 0.2  # Up to 20% for low risk
            
            # Only include items with reasonable confidence
            if confidence < 40:
                continue
            
            # Generate reasoning
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
        
        # Sort by overnight profit potential (weighted by confidence)
        overnight_opportunities.sort(
            key=lambda x: x['overnight_profit'] * (x['overnight_confidence'] / 100),
            reverse=True
        )
        
        return jsonify(overnight_opportunities[:10])  # Return top 10
        
    except Exception as e:
        print(f"[ERROR] api_nightly: {e}")
        return jsonify({"error": "Failed to calculate overnight recommendations"}), 500

@app.route('/api/update_cache', methods=['POST'])
@require_admin_key()
@rate_limit(max_requests=5, window=300)
def api_update_cache():
    """Manually trigger cache update from the internet"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    try:
        import utils.cache_updater
        item_map = utils.cache_updater.update_cache()
        
        # Reload names after update
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

@app.route('/api/server_config/<guild_id>', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_server_config(guild_id):
    """API endpoint for bot to fetch server config"""
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if is_banned(guild_id):
        return jsonify({"error": "banned"}), 403
    
    config = get_config(guild_id)
    return jsonify(config)

@app.route('/api/server_banned/<guild_id>', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_server_banned(guild_id):
    """API endpoint for bot to check if server is banned"""
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"banned": False})  # Return False for invalid IDs
    
    return jsonify({"banned": is_banned(guild_id)})

@app.route('/api/server_info/<guild_id>', methods=['POST'])
@rate_limit(max_requests=50, window=60)
def api_server_info_update(guild_id):
    """API endpoint for bot to update server information (roles, members, channels, etc.)"""
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Store server info in a separate file
        server_info_path = os.path.join("server_configs", f"{guild_id}_info.json")
        # Ensure path is safe
        if not os.path.abspath(server_info_path).startswith(os.path.abspath("server_configs")):
            return jsonify({"error": "Invalid path"}), 400
        
        # Save server info
        with open(server_info_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({"status": "updated"})
    except Exception as e:
        print(f"[ERROR] api_server_info_update: {e}")
        return jsonify({"error": "Failed to update server info"}), 500

@app.route('/api/server_info/<guild_id>', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_server_info_get(guild_id):
    """API endpoint to get server information for admin panel"""
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    # LAN-only access for admin panel
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    try:
        server_info_path = os.path.join("server_configs", f"{guild_id}_info.json")
        # Ensure path is safe
        if not os.path.abspath(server_info_path).startswith(os.path.abspath("server_configs")):
            return jsonify({"error": "Invalid path"}), 400
        
        if os.path.exists(server_info_path):
            with open(server_info_path, 'r') as f:
                return jsonify(json.load(f))
        else:
            return jsonify({"error": "Server info not available"}), 404
    except Exception as e:
        print(f"[ERROR] api_server_info_get: {e}")
        return jsonify({"error": "Failed to get server info"}), 500

@app.route('/api/server_info/<guild_id>/assign_role', methods=['POST'])
@rate_limit(max_requests=30, window=60)
def api_assign_role(guild_id):
    """API endpoint to assign a role to a member (via bot)"""
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    # LAN-only access for admin panel
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        action = data.get('action', 'add')  # 'add' or 'remove'
        
        if not user_id or not role_id:
            return jsonify({"error": "Missing user_id or role_id"}), 400
        
        # This will be handled by the bot - we'll send a request to the bot
        # For now, we'll store the assignment request and the bot will poll for it
        assignment_path = os.path.join("server_configs", f"{guild_id}_assignments.json")
        if not os.path.abspath(assignment_path).startswith(os.path.abspath("server_configs")):
            return jsonify({"error": "Invalid path"}), 400
        
        assignments = []
        if os.path.exists(assignment_path):
            with open(assignment_path, 'r') as f:
                assignments = json.load(f)
        
        # Add assignment request
        assignment = {
            "user_id": str(user_id),
            "role_id": str(role_id),
            "action": action,
            "timestamp": int(datetime.now().timestamp())
        }
        assignments.append(assignment)
        
        # Keep only last 100 assignments
        assignments = assignments[-100:]
        
        with open(assignment_path, 'w') as f:
            json.dump(assignments, f, indent=2)
        
        return jsonify({"status": "queued"})
    except Exception as e:
        print(f"[ERROR] api_assign_role: {e}")
        return jsonify({"error": "Failed to queue role assignment"}), 500

@app.route('/api/server_info/<guild_id>/assignments', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_get_assignments(guild_id):
    """API endpoint for bot to get pending role assignments"""
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    try:
        assignment_path = os.path.join("server_configs", f"{guild_id}_assignments.json")
        if not os.path.abspath(assignment_path).startswith(os.path.abspath("server_configs")):
            return jsonify({"error": "Invalid path"}), 400
        
        if os.path.exists(assignment_path):
            with open(assignment_path, 'r') as f:
                assignments = json.load(f)
            # Clear processed assignments (older than 1 minute)
            current_time = int(datetime.now().timestamp())
            assignments = [a for a in assignments if current_time - a.get('timestamp', 0) < 60]
            
            # Save back (remove processed ones)
            with open(assignment_path, 'w') as f:
                json.dump(assignments, f, indent=2)
            
            return jsonify(assignments)
        else:
            return jsonify([])
    except Exception as e:
        print(f"[ERROR] api_get_assignments: {e}")
        return jsonify({"error": "Failed to get assignments"}), 500
@app.route('/config/<guild_id>', methods=['GET', 'POST'])
@rate_limit(max_requests=30, window=60)
def server_config(guild_id):
    # LAN-only access for configuration
    if not is_local_request():
        return jsonify({"error": "Access denied. Configuration interface is LAN-only."}), 403
    
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    # Check if server is banned
    if is_banned(guild_id):
        return jsonify({"error": "This server has been banned from using the sniper bot."}), 403
    
    config = get_config(guild_id)
    
    # Ensure roles dict exists for older configs
    if "roles" not in config:
        config["roles"] = {}
    
    if request.method == 'POST':
        try:
            data = request.get_json(force=True)
            if not data:
                return jsonify({"error": "Invalid JSON"}), 400
            
            # Sanitize channel inputs
            channels = {}
            if 'channels' in data:
                for key, value in data.get('channels', {}).items():
                    if value:
                        sanitized = sanitize_channel_id(str(value))
                        if sanitized:
                            channels[key] = sanitized
                        else:
                            channels[key] = None
                    else:
                        channels[key] = None
            
            # Validate thresholds
            thresholds = config.get("thresholds", {})
            if 'thresholds' in data:
                for key, value in data.get('thresholds', {}).items():
                    num_val = validate_numeric(value, min_val=0)
                    if num_val is not None:
                        thresholds[key] = num_val
            
            config["channels"] = channels
            config["thresholds"] = thresholds
            config["roles"] = data.get("roles", config.get("roles", {}))
            config["enabled"] = bool(data.get("enabled", True))
            save_config(guild_id, config)
            return jsonify({"status": "saved"})
        except Exception as e:
            print(f"[ERROR] server_config POST: {e}")
            return jsonify({"error": "Invalid request data"}), 400
    
    # Config page now handled by Next.js frontend at /config/[guildId]
    # Return JSON for API access
    return jsonify(config)

# Setup API endpoints
@app.route('/api/setup/save-token', methods=['POST'])
@validate_json_payload(max_size=5000)
@rate_limit(max_requests=5, window=300)  # 5 attempts per 5 minutes
def setup_save_token():
    """Save Discord bot token"""
    global CONFIG  # Declare global at the top of the function
    
    if not is_local_request():
        return jsonify({"error": "Setup can only be done from local network"}), 403
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        token = data.get('discord_token', '').strip()
        
        # Validate token format
        token = sanitize_token(token)
        if not token:
            return jsonify({"error": "Invalid token format"}), 400
        
        CONFIG['discord_token'] = token
        
        # Generate admin key if not set
        if not CONFIG.get('admin_key') or CONFIG.get('admin_key') == 'CHANGE_THIS_TO_A_SECURE_RANDOM_STRING':
            CONFIG['admin_key'] = secrets.token_urlsafe(32)
        
        # Save config
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(CONFIG, f, indent=2)
        except IOError:
            return jsonify({"error": "Failed to save configuration"}), 500
        
        # Reload global CONFIG
        with open(CONFIG_PATH, 'r') as f:
            CONFIG = json.load(f)
        
        return jsonify({"status": "saved"})
    except Exception:
        return jsonify({"error": "Invalid request"}), 400

@app.route('/api/setup/test-bot', methods=['GET'])
@rate_limit(max_requests=10, window=60)
def setup_test_bot():
    """Test Discord bot connection"""
    if not is_local_request():
        return jsonify({"error": "Setup can only be done from local network"}), 403
    
    token = CONFIG.get('discord_token', '')
    
    if not token or token == 'YOUR_BOT_TOKEN_HERE':
        return jsonify({"error": "Bot token not configured"}), 400
    
    # Validate token format
    if not sanitize_token(token):
        return jsonify({"error": "Invalid token format"}), 400
    
    try:
        # Test bot connection via Discord API
        headers = {"Authorization": f"Bot {token}"}
        response = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=10)
        
        if response.status_code == 200:
            bot_data = response.json()
            return jsonify({
                "success": True,
                "bot_username": escape_html(bot_data.get('username', 'Unknown')),
                "bot_id": bot_data.get('id', 'Unknown')
            })
        else:
            # Don't leak detailed error info
            return jsonify({"error": "Failed to connect to Discord API"}), 400
    except requests.exceptions.Timeout:
        return jsonify({"error": "Connection timeout"}), 400
    except Exception as e:
        print(f"[ERROR] setup_test_bot: {e}")
        return jsonify({"error": "Connection failed"}), 400

@app.route('/api/setup/save-server', methods=['POST'])
@validate_json_payload(max_size=10000)
@rate_limit(max_requests=10, window=60)
def setup_save_server():
    """Save first server configuration"""
    if not is_local_request():
        return jsonify({"error": "Setup can only be done from local network"}), 403
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        guild_id = data.get('guild_id', '').strip()
        guild_id = sanitize_guild_id(guild_id)
        
        if not guild_id:
            return jsonify({"error": "Invalid server ID"}), 400
        
        # Sanitize channel inputs
        channels = {}
        if 'channels' in data:
            for key, value in data.get('channels', {}).items():
                if value:
                    sanitized = sanitize_channel_id(str(value))
                    channels[key] = sanitized if sanitized else None
                else:
                    channels[key] = None
        
        # Create server config
        server_config = get_config(guild_id)
        server_config['channels'] = channels
        save_config(guild_id, server_config)
        
        return jsonify({"status": "saved", "guild_id": guild_id})
    except Exception as e:
        print(f"[ERROR] setup_save_server: {e}")
        return jsonify({"error": "Invalid request data"}), 400

@app.route('/api/setup/save-webhook', methods=['POST'])
@validate_json_payload(max_size=1000)
@rate_limit(max_requests=10, window=60)
def setup_save_webhook():
    """Save Discord webhook"""
    global CONFIG  # Declare global at the top of the function
    
    if not is_local_request():
        return jsonify({"error": "Setup can only be done from local network"}), 403
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        webhook = data.get('discord_webhook', '').strip()
        
        if webhook:
            webhook = sanitize_webhook_url(webhook)
            if not webhook:
                return jsonify({"error": "Invalid webhook URL"}), 400
            
            CONFIG['discord_webhook'] = webhook
            try:
                with open(CONFIG_PATH, 'w') as f:
                    json.dump(CONFIG, f, indent=2)
            except IOError:
                return jsonify({"error": "Failed to save configuration"}), 500
            
            # Reload global CONFIG
            with open(CONFIG_PATH, 'r') as f:
                CONFIG = json.load(f)
        
        return jsonify({"status": "saved"})
    except Exception as e:
        print(f"[ERROR] setup_save_webhook: {e}")
        return jsonify({"error": "Invalid request data"}), 400

@app.route('/api/setup/complete', methods=['POST'])
@rate_limit(max_requests=10, window=60)
def setup_complete():
    """Mark setup as complete"""
    if not is_local_request():
        return jsonify({"error": "Setup can only be done from local network"}), 403
    
    # Setup is complete when config is saved
    return jsonify({"status": "complete"})

# Admin endpoints (LAN-only)
@app.route('/admin/servers', methods=['GET'])
@require_admin_key()
@rate_limit(max_requests=30, window=60)
def admin_list_servers():
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    servers = list_servers()
    server_data = []
    for guild_id in servers:
        config = get_config(guild_id)
        server_data.append({
            "guild_id": guild_id,
            "enabled": config.get("enabled", True),
            "banned": is_banned(guild_id),
            "channels_configured": sum(1 for ch in config.get("channels", {}).values() if ch)
        })
    return jsonify(server_data)

@app.route('/admin/ban/<guild_id>', methods=['POST'])
@require_admin_key()
@rate_limit(max_requests=20, window=60)
def admin_ban_server(guild_id):
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    ban_server(guild_id)
    return jsonify({"status": "banned", "guild_id": guild_id})

@app.route('/admin/unban/<guild_id>', methods=['POST'])
@require_admin_key()
@rate_limit(max_requests=20, window=60)
def admin_unban_server(guild_id):
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    unban_server(guild_id)
    return jsonify({"status": "unbanned", "guild_id": guild_id})

@app.route('/admin/delete/<guild_id>', methods=['DELETE'])
@require_admin_key()
@rate_limit(max_requests=10, window=60)
def admin_delete_server(guild_id):
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    from config_manager import delete_config
    delete_config(guild_id)
    return jsonify({"status": "deleted", "guild_id": guild_id})

# Tier management admin routes
@app.route('/admin/tiers', methods=['GET'])
@require_admin_key()
@rate_limit(max_requests=30, window=60)
def admin_get_tiers():
    """Get all tiers with optional guild-specific settings"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    guild_id = request.args.get('guild_id')
    if guild_id:
        guild_id = sanitize_guild_id(guild_id)
        if not guild_id:
            return jsonify({"error": "Invalid server ID"}), 400
    
    try:
        tiers = get_all_tiers()
        guild_settings = {}
        guild_config = {}
        
        if guild_id:
            guild_settings = get_guild_tier_settings(guild_id)
            guild_config = get_guild_config(guild_id)
        
        # Merge tier data with guild settings
        result = []
        for tier in tiers:
            tier_data = {
                "id": tier["id"],
                "name": tier["name"],
                "emoji": tier["emoji"],
                "min_score": tier["min_score"],
                "max_score": tier["max_score"],
                "group": tier["group"]
            }
            
            if guild_id:
                setting = guild_settings.get(tier["name"], {})
                tier_data["role_id"] = setting.get("role_id")
                tier_data["enabled"] = setting.get("enabled", True)
            
            result.append(tier_data)
        
        response = {
            "tiers": result,
            "guild_id": guild_id
        }
        
        if guild_id:
            response["min_tier_name"] = guild_config.get("min_tier_name")
        
        return jsonify(response)
    except Exception as e:
        print(f"[ERROR] admin_get_tiers: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to get tiers"}), 500

@app.route('/admin/tiers', methods=['POST'])
@require_admin_key()
@rate_limit(max_requests=20, window=60)
def admin_update_tiers():
    """Update tier score ranges and guild tier settings"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        guild_id = data.get('guild_id')
        if guild_id:
            guild_id = sanitize_guild_id(guild_id)
            if not guild_id:
                return jsonify({"error": "Invalid server ID"}), 400
        
        # Update tier score ranges
        tier_updates = data.get('tiers', [])
        for tier_update in tier_updates:
            tier_id = tier_update.get('id')
            min_score = tier_update.get('min_score')
            max_score = tier_update.get('max_score')
            
            if tier_id is not None:
                if min_score is not None or max_score is not None:
                    update_tier(tier_id, min_score, max_score)
        
        # Update guild tier settings
        if guild_id:
            guild_tier_settings = data.get('guild_tier_settings', [])
            for setting in guild_tier_settings:
                tier_name = setting.get('tier_name')
                role_id = setting.get('role_id')
                enabled = setting.get('enabled')
                
                if tier_name:
                    # Allow empty string to clear role_id
                    if role_id == "":
                        role_id = None
                    update_guild_tier_setting(guild_id, tier_name, role_id=role_id, enabled=enabled)
            
            # Update guild config (min_tier_name)
            min_tier_name = data.get('min_tier_name')
            if min_tier_name is not None:
                if min_tier_name == "":
                    min_tier_name = None
                update_guild_config(guild_id, min_tier_name=min_tier_name)
        
        return jsonify({"status": "updated"})
    except Exception as e:
        print(f"[ERROR] admin_update_tiers: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to update tiers"}), 500

# API endpoint for Discord bot
@app.route('/api/tiers', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_get_tiers():
    """API endpoint for Discord bot to get tier configuration for a guild"""
    guild_id = request.args.get('guild_id')
    if not guild_id:
        return jsonify({"error": "Missing guild_id parameter"}), 400
    
    # Sanitize guild_id
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    try:
        tiers = get_all_tiers()
        guild_settings = get_guild_tier_settings(guild_id)
        guild_config = get_guild_config(guild_id)
        
        # Build response with tier list and guild-specific settings
        tier_list = []
        for tier in tiers:
            setting = guild_settings.get(tier["name"], {})
            tier_list.append({
                "name": tier["name"],
                "emoji": tier["emoji"],
                "min_score": tier["min_score"],
                "max_score": tier["max_score"],
                "group": tier["group"],
                "role_id": setting.get("role_id"),
                "enabled": setting.get("enabled", True)
            })
        
        response = {
            "tiers": tier_list,
            "min_tier_name": guild_config.get("min_tier_name")
        }
        
        return jsonify(response)
    except Exception as e:
        print(f"[ERROR] api_get_tiers: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to get tiers"}), 500

# Admin panel now handled by Next.js frontend at /admin

# Auto-updater endpoints
@app.route('/api/update/check', methods=['GET'])
@require_admin_key()
def check_updates():
    """Check if updates are available"""
    try:
        from utils.auto_updater import get_update_status
        status = get_update_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update/status', methods=['GET'])
@require_admin_key()
def update_status():
    """Get update status and history"""
    try:
        from utils.auto_updater import get_update_status
        return jsonify(get_update_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update/pull', methods=['POST'])
@require_admin_key()
def pull_updates():
    """Pull latest updates from GitHub"""
    try:
        from utils.auto_updater import update_code
        restart = request.json.get('restart_services', True) if request.json else True
        result = update_code(restart_services=restart)
        # Ensure we always return a proper response
        if not isinstance(result, dict):
            return jsonify({"success": False, "message": "Update function returned invalid response"}), 500
        return jsonify(result)
    except Exception as e:
        import traceback
        import logging
        error_trace = traceback.format_exc()
        logging.error(f"Update error: {str(e)}\n{error_trace}")
        return jsonify({
            "success": False, 
            "message": f"Update failed: {str(e)}",
            "error": str(e)
        }), 500


# Initialize database and start polling thread on module import
# This ensures tracking works regardless of how Flask is started (direct run, WSGI, etc.)
_poll_thread_started = False

def _start_background_tasks():
    """Start background tasks (database init and polling thread)"""
    global _poll_thread_started
    
    if _poll_thread_started:
        return  # Already started
    
    # Initialize database on startup
    try:
        init_db()
        print("[+] Database initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
    
    # Start polling thread
    try:
        poll_thread = threading.Thread(target=poll, daemon=True)
        poll_thread.start()
        _poll_thread_started = True
        print("[+] GE tracking thread started")
    except Exception as e:
        print(f"[ERROR] Failed to start polling thread: {e}")

# Start background tasks when module is imported
_start_background_tasks()

if __name__ == '__main__':
    # Note: host='0.0.0.0' is required for Docker container networking
    # In production, ensure proper firewall/network security
    # This is safe when running in Docker with proper network isolation
    app.run(host='0.0.0.0', port=5000)