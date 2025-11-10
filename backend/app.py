# backend/app.py
import requests, time, json, threading
from flask import Flask, render_template_string, jsonify, request
from discord_webhook import DiscordWebhook
from config_manager import get_config, save_config, is_banned, ban_server, unban_server, list_servers
import sqlite3, os
from utils.database import log_price

app = Flask(__name__)
BASE = "https://prices.runescape.wiki/api/v1/osrs"
HEADERS = {"User-Agent": "OSRS-Sniper-Empire/3.0 (+your-discord)"}
CONFIG = json.load(open('../config.json'))

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
    
    import urllib.parse
    
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
    if score >= 100: return "GOD-TIER", "INSANE BUY OPPORTUNITY"
    elif score >= 40: return "ELITE", "HIGH VOLUME CRASH"
    elif score >= 15: return "PREMIUM", "STRONG DUMP"
    elif score >= 5: return "GOOD", "SOLID DIP"
    elif score >= 1: return "DEAL", "WORTH A LOOK"
    else: return "", ""

def load_names():
    global item_names
    cache_path = "utils/item_cache.json"
    if os.path.exists(cache_path):
        try:
            item_names = json.load(open(cache_path))
            print(f"Loaded {len(item_names)} items from cache")
        except:
            item_names = {}
    else:
        item_names = {}
    # Auto-update in background
    def updater():
        time.sleep(10)
        import utils.cache_updater
        utils.cache_updater.update_cache()
    threading.Thread(target=updater, daemon=True).start()

def fetch_all():
    global top_items, dump_items, spike_items, all_items
    try:
        latest = requests.get(f"{BASE}/latest", headers=HEADERS).json()
        h1 = requests.get(f"{BASE}/1h", headers=HEADERS).json()
        mapping = requests.get(f"{BASE}/mapping", headers=HEADERS).json()
        
        # Build ID → limit map
        limit_map = {str(m['id']): m.get('limit', 0) for m in mapping}
        
        margins, dumps, spikes, all_items = [], [], [], []
        for id_str, data in latest.get("data", {}).items():
            if not data.get("high") or not data.get("low"): continue
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
            if profit > CONFIG["thresholds"]["margin_min"] and low > 1000:
                margins.append({
                    "id": int(id_str), "name": name, "buy": low, "sell": high,
                    "insta_buy": insta_buy, "insta_sell": insta_sell,
                    "profit": profit, "roi": roi, "volume": vol, "limit": limit,
                    **risk_metrics  # Add risk metrics to margins
                })
            
            # === DUMPS & SPIKES ===
            if vol > CONFIG["thresholds"]["min_volume"] and low > 500000:
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
                    dumps.append({
                        "id": int(id_str),
                        "name": name,
                        "buy": low,
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
                        **dump_risk  # Add risk metrics
                    })

                # === SPIKE DETECTION ===
                if rise_pct > CONFIG["thresholds"]["spike_rise_pct"]:
                    # Calculate risk for spikes
                    spike_risk = calculate_risk_metrics(low, high, insta_buy, insta_sell, vol, limit, profit)
                    spikes.append({
                        "id": int(id_str),
                        "name": name,
                        "sell": high,
                        "rise_pct": rise_pct,
                        "volume": vol,
                        "prev": prev_avg,
                        "limit": limit,
                        "insta_buy": insta_buy,
                        "insta_sell": insta_sell,
                        **spike_risk  # Add risk metrics
                    })
        
        top_items = sorted(margins, key=lambda x: x["profit"], reverse=True)[:50]
        dump_items = sorted(dumps, key=lambda x: x["volume"] * x["drop_pct"], reverse=True)[:20]
        spike_items = sorted(spikes, key=lambda x: x["rise_pct"], reverse=True)[:20]
        print(f"[+] {len(top_items)} flips | {len(dump_items)} dumps | {len(spike_items)} spikes")
    except Exception as e:
        print(f"[ERROR] {e}")

def notify(title, items, color):
    if not items: return
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
        
        embed = {
            "title": f"{title} {item.get('quality', '')}",
            "description": f"**{item_name}**\n"
                          f"{price_desc}\n"
                          f"Move: {item.get('drop_pct', item.get('rise_pct', 0)):.1f}%\n"
                          f"Vol: **{item['volume']:,}** | {item.get('quality_label', '')}"
                          f"{risk_info}",
            "url": f"https://prices.runescape.wiki/osrs/item/{item_id}",
            "color": color
        }
        
        # Add thumbnail if available
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
        
        webhook.add_embed(embed)
    threading.Thread(target=webhook.execute).start()

def poll():
    load_names()
    last_dumps = last_spikes = []
    while True:
        fetch_all()
        new_dumps = [d for d in dump_items if d not in last_dumps]
        new_spikes = [s for s in spike_items if s not in last_spikes]
        if new_dumps: notify("DUMP DETECTED — BUY THE PANIC", new_dumps, 0x8B0000)
        if new_spikes: notify("SPIKE DETECTED — SELL NOW", new_spikes, 0x00FF00)
        last_dumps = dump_items[:10]
        last_spikes = spike_items[:10]
        time.sleep(8)

@app.route('/dashboard')
def dashboard():
    web_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dashboard.html")
    with open(web_path) as f: html = f.read()
    return render_template_string(html, 
        top_items=top_items, dump_items=dump_items, spike_items=spike_items)

@app.route('/volume_tracker')
def volume_tracker():
    """Volume tracker page"""
    web_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "volume_tracker.html")
    with open(web_path) as f: html = f.read()
    return render_template_string(html)

@app.route('/api/top')
def api_top(): return jsonify(top_items[:20])
@app.route('/api/dumps')
def api_dumps(): return jsonify(dump_items)
@app.route('/api/spikes')
def api_spikes(): return jsonify(spike_items)
@app.route('/api/all_items')
def api_all_items(): 
    """API endpoint for volume tracker - returns all items with filtering support"""
    return jsonify(all_items)

@app.route('/api/server_config/<guild_id>', methods=['GET'])
def api_server_config(guild_id):
    """API endpoint for bot to fetch server config"""
    if is_banned(guild_id):
        return jsonify({"error": "banned"}), 403
    config = get_config(guild_id)
    return jsonify(config)

@app.route('/api/server_banned/<guild_id>', methods=['GET'])
def api_server_banned(guild_id):
    """API endpoint for bot to check if server is banned"""
    return jsonify({"banned": is_banned(guild_id)})
@app.route('/config/<guild_id>', methods=['GET', 'POST'])
def server_config(guild_id):
    # Check if server is banned
    if is_banned(guild_id):
        return jsonify({"error": "This server has been banned from using the sniper bot."}), 403
    
    config = get_config(guild_id)
    
    if request.method == 'POST':
        data = request.json
        config["channels"] = data.get("channels", config["channels"])
        config["thresholds"] = data.get("thresholds", config["thresholds"])
        config["enabled"] = data.get("enabled", True)
        save_config(guild_id, config)
        return jsonify({"status": "saved"})
    
    web_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "config.html")
    with open(web_path) as f:
        html = f.read()
    return render_template_string(html, config=config, guild_id=guild_id)

# Admin endpoints
@app.route('/admin/servers', methods=['GET'])
def admin_list_servers():
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != CONFIG.get('admin_key'):
        return jsonify({"error": "Unauthorized"}), 401
    
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
def admin_ban_server(guild_id):
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != CONFIG.get('admin_key'):
        return jsonify({"error": "Unauthorized"}), 401
    
    ban_server(guild_id)
    return jsonify({"status": "banned", "guild_id": guild_id})

@app.route('/admin/unban/<guild_id>', methods=['POST'])
def admin_unban_server(guild_id):
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != CONFIG.get('admin_key'):
        return jsonify({"error": "Unauthorized"}), 401
    
    unban_server(guild_id)
    return jsonify({"status": "unbanned", "guild_id": guild_id})

@app.route('/admin/delete/<guild_id>', methods=['DELETE'])
def admin_delete_server(guild_id):
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != CONFIG.get('admin_key'):
        return jsonify({"error": "Unauthorized"}), 401
    
    from config_manager import delete_config
    delete_config(guild_id)
    return jsonify({"status": "deleted", "guild_id": guild_id})

@app.route('/admin')
def admin_panel():
    """Admin web interface"""
    web_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "admin.html")
    with open(web_path) as f:
        html = f.read()
    return render_template_string(html)

if __name__ == '__main__':
    threading.Thread(target=poll, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)