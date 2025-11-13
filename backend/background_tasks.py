"""
Background tasks for polling GE data and notifications
"""
import time
import threading
import os
import json
from datetime import datetime
from discord_webhook import DiscordWebhook
from utils.shared import (
    get_item_lock, get_item_data, set_item_data, BASE, HEADERS,
    FALLBACK_BASE, FALLBACK_HEADERS, fetch_with_fallback, convert_1h_data_to_dict
)
import utils.shared
from utils.database import log_price, get_price_historicals, init_db
from utils.item_metadata import get_item_meta
from utils.shared import ge_tax

def calculate_risk_metrics(low, high, insta_buy, insta_sell, volume, limit, profit):
    """Calculate risk metrics for an item"""
    if limit > 0:
        liquidity_ratio = volume / limit if limit > 0 else 0
        liquidity_score = min(100, (liquidity_ratio / 10) * 100)
    else:
        liquidity_score = 0
    
    buy_spread = abs(insta_buy - low) / low * 100 if low > 0 else 0
    sell_spread = abs(insta_sell - high) / high * 100 if high > 0 else 0
    avg_spread = (buy_spread + sell_spread) / 2
    spread_risk = min(100, avg_spread * 10)
    volume_velocity = min(100, (volume / 1000) * 10)
    
    if limit > 0 and volume > 0:
        can_buy_full = 1.0 if volume >= limit else volume / limit
        price_confidence = max(0, 1.0 - (avg_spread / 20))
        profitability_confidence = (can_buy_full * 0.6 + price_confidence * 0.4) * 100
    else:
        profitability_confidence = 0
    
    risk_score = (
        (100 - liquidity_score) * 0.3 +
        spread_risk * 0.4 +
        (100 - volume_velocity) * 0.3
    )
    
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
    """Get the OSRS Wiki thumbnail URL for an item"""
    if not item_name:
        return None
    
    import urllib.parse
    wiki_name = item_name.strip().replace(' ', '_')
    parts = wiki_name.split('_')
    wiki_name = '_'.join(part.capitalize() for part in parts)
    wiki_name = urllib.parse.quote(wiki_name, safe='_')
    return f"https://oldschool.runescape.wiki/images/{wiki_name}.png"

def get_dump_quality(drop_pct, volume, low_price):
    """Get dump quality rating"""
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
    """Load item names from cache"""
    import utils.shared
    cache_path = os.path.join(os.path.dirname(__file__), "utils", "item_cache.json")
    if not os.path.exists(cache_path):
        cache_path = "utils/item_cache.json"
        if not os.path.exists(cache_path):
            cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "utils", "item_cache.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                utils.shared.item_names = json.load(f)
            print(f"Loaded {len(utils.shared.item_names)} items from cache")
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ERROR] Failed to load item cache: {e}")
            utils.shared.item_names = {}
    else:
        utils.shared.item_names = {}
        print("[WARNING] Item cache not found, item names will be unavailable")
    
    def updater():
        time.sleep(10)
        try:
            import utils.cache_updater
            utils.cache_updater.update_cache()
        except Exception as e:
            print(f"[ERROR] Cache updater failed: {e}")
    threading.Thread(target=updater, daemon=True).start()

def fetch_all():
    """Fetch all GE data and update global item lists"""
    try:
        latest, latest_source = fetch_with_fallback(
            f"{BASE}/latest", HEADERS,
            f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None, timeout=30
        )
        if latest_source == 'fallback':
            print("[INFO] Using fallback API for latest prices")
        
        h1_raw, h1_source = fetch_with_fallback(
            f"{BASE}/1h", HEADERS, None, None, timeout=30
        )
        if h1_source == 'fallback':
            print("[INFO] Using fallback API for 1h prices")
        
        h1 = convert_1h_data_to_dict(h1_raw)
        
        mapping, mapping_source = fetch_with_fallback(
            f"{BASE}/mapping", HEADERS,
            f"{FALLBACK_BASE}/mapping" if FALLBACK_BASE else None,
            FALLBACK_HEADERS if FALLBACK_BASE else None, timeout=30
        )
        if mapping_source == 'fallback':
            print("[INFO] Using fallback API for mapping")
        
        limit_map = {str(m['id']): m.get('limit', 0) for m in mapping}
        
        margins, dumps, spikes, all_items_list = [], [], [], []
        threshold_margin_min = utils.shared.CONFIG.get("thresholds", {}).get("margin_min", 100000)
        threshold_dump_drop_pct = utils.shared.CONFIG.get("thresholds", {}).get("dump_drop_pct", 5)
        threshold_spike_rise_pct = utils.shared.CONFIG.get("thresholds", {}).get("spike_rise_pct", 5)
        threshold_min_volume = utils.shared.CONFIG.get("thresholds", {}).get("min_volume", 100)
        
        for id_str, data in latest.get("data", {}).items():
            if not data.get("high") or not data.get("low"):
                continue
            low, high = data["low"], data["high"]
            name = utils.shared.item_names.get(id_str, f"Item {id_str}")
            vol = h1.get(id_str, {}).get("volume", 0) or 1
            limit = limit_map.get(id_str, 0)
            
            log_price(int(id_str), low, high, vol)
            
            insta_buy = data.get('high', low)
            insta_sell = data.get('low', high)
            profit = high - low - ge_tax(high)
            roi = (profit / low * 100) if low > 0 else 0
            risk_metrics = calculate_risk_metrics(low, high, insta_buy, insta_sell, vol, limit, profit)
            
            all_items_list.append({
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
                **risk_metrics
            })
            
            if profit > threshold_margin_min and low > 100:
                historicals = get_price_historicals(int(id_str))
                margins.append({
                    "id": int(id_str), "name": name, "buy": low, "sell": high,
                    "insta_buy": insta_buy, "insta_sell": insta_sell,
                    "profit": profit, "roi": roi, "volume": vol, "limit": limit,
                    **risk_metrics,
                    **historicals
                })
            
            if vol > threshold_min_volume and low > 10000:
                h1_data = h1.get(id_str, {})
                prev_avg = h1_data.get("avgHighPrice", high) or high
                drop_pct = (prev_avg - low) / prev_avg * 100
                rise_pct = (high - prev_avg) / prev_avg * 100
                
                max_profit_4h = (high - low) * min(vol, limit * 4) * 0.99
                realistic_profit = (high - low) * limit * 0.99

                if drop_pct > threshold_dump_drop_pct:
                    quality_stars, quality_label = get_dump_quality(drop_pct, vol, low)
                    dump_risk = calculate_risk_metrics(low, high, insta_buy, insta_sell, vol, limit, profit)
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
                        **dump_risk,
                        **historicals
                    })

                if rise_pct > threshold_spike_rise_pct:
                    spike_risk = calculate_risk_metrics(low, high, insta_buy, insta_sell, vol, limit, profit)
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
                        **spike_risk,
                        **historicals
                    })
        
        with get_item_lock():
            set_item_data(
                top_items=sorted(margins, key=lambda x: x["profit"], reverse=True)[:50],
                dump_items=sorted(dumps, key=lambda x: x["volume"] * x["drop_pct"], reverse=True)[:20],
                spike_items=sorted(spikes, key=lambda x: x["rise_pct"], reverse=True)[:20],
                all_items=all_items_list
            )
        
        item_data = get_item_data()
        print(f"[+] {len(item_data['top_items'])} flips | {len(item_data['dump_items'])} dumps | {len(item_data['spike_items'])} spikes")
    except Exception as e:
        print(f"[ERROR] fetch_all: {e}")
        import traceback
        traceback.print_exc()

def notify(title, items, color):
    """Send Discord notification"""
    if not items:
        return
    webhook = DiscordWebhook(url=utils.shared.CONFIG.get("discord_webhook"), rate_limit_retry=True)
    for item in items[:5]:
        item_name = item.get('name', 'Unknown')
        item_id = item.get('id', 0)
        thumbnail_url = get_item_thumbnail_url(item_name)
        
        buy_price = item.get('buy', 0)
        sell_price = item.get('sell', 0)
        insta_buy = item.get('insta_buy', buy_price)
        insta_sell = item.get('insta_sell', sell_price)
        
        price_desc = f"Price: {buy_price:,} GP → {sell_price:,} GP"
        if insta_buy != buy_price or insta_sell != sell_price:
            price_desc += f"\n**Insta Buy:** {insta_buy:,} GP | **Insta Sell:** {insta_sell:,} GP"
        
        risk_score = item.get('risk_score', 0)
        risk_level = item.get('risk_level', 'UNKNOWN')
        profitability_confidence = item.get('profitability_confidence', 0)
        liquidity_score = item.get('liquidity_score', 0)
        
        risk_info = f"\n**Risk:** {risk_level} ({risk_score:.1f}/100) | **Confidence:** {profitability_confidence:.1f}% | **Liquidity:** {liquidity_score:.1f}%"
        
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
        
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
        
        webhook.add_embed(embed)
    threading.Thread(target=webhook.execute).start()

def poll():
    """Main polling loop"""
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
            if poll_count % 10 == 0:
                print(f"[POLL] Tracking active - completed {poll_count} polls")
            fetch_all()
            consecutive_errors = 0
            
            with get_item_lock():
                item_data = get_item_data()
                current_dumps = item_data['dump_items'][:10]
                current_spikes = item_data['spike_items'][:10]
            
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
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"[ERROR] Too many consecutive errors, waiting 60 seconds before retry")
                time.sleep(60)
                consecutive_errors = 0
            else:
                time.sleep(2)
        else:
            time.sleep(2)

def start_background_tasks():
    """Start background tasks (database init and polling thread)"""
    try:
        init_db()
        print("[+] Database initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
    
    try:
        poll_thread = threading.Thread(target=poll, daemon=True)
        poll_thread.start()
        print("[+] GE tracking thread started")
    except Exception as e:
        print(f"[ERROR] Failed to start polling thread: {e}")

