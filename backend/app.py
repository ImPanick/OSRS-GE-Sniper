# backend/app.py
import requests
import time
import json
import threading
from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
from discord_webhook import DiscordWebhook
from config_manager import get_config, save_config, is_banned, ban_server, unban_server, list_servers
import os
import urllib.parse
from utils.database import log_price, get_price_historicals, init_db
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
BASE = "https://prices.runescape.wiki/api/v1/osrs"
HEADERS = {"User-Agent": "OSRS-Sniper (+your-discord)"}

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

def fetch_all():
    global top_items, dump_items, spike_items, all_items
    try:
        latest = requests.get(f"{BASE}/latest", headers=HEADERS, timeout=30).json()
        h1 = requests.get(f"{BASE}/1h", headers=HEADERS, timeout=30).json()
        mapping = requests.get(f"{BASE}/mapping", headers=HEADERS, timeout=30).json()
        
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
                time.sleep(8)
        else:
            time.sleep(8)

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
    """Get dumps with thread-safe access"""
    with _item_lock:
        return jsonify(dump_items)

@app.route('/api/spikes')
@rate_limit(max_requests=200, window=60)
def api_spikes():
    """Get spikes with thread-safe access"""
    with _item_lock:
        return jsonify(spike_items)

@app.route('/api/all_items')
@rate_limit(max_requests=100, window=60)
def api_all_items():
    """API endpoint for volume tracker - returns all items with filtering support"""
    with _item_lock:
        return jsonify(all_items)

@app.route('/api/nightly')
@rate_limit(max_requests=50, window=60)
def api_nightly():
    """
    API endpoint for overnight flip recommendations
    Analyzes items for best 8-16 hour profit potential
    """
    min_profit = request.args.get('min_profit', 1_000_000, type=int)
    
    try:
        # Get all items with their data
        latest = requests.get(f"{BASE}/latest", headers=HEADERS, timeout=30).json()
        h1 = requests.get(f"{BASE}/1h", headers=HEADERS, timeout=30).json()
        mapping = requests.get(f"{BASE}/mapping", headers=HEADERS, timeout=30).json()
        
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
    except Exception as e:
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
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


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