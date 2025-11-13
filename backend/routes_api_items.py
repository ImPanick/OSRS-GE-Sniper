"""
API routes for items, recipes, and decants
"""
from flask import Blueprint, jsonify, request
from utils.shared import (
    get_item_lock, get_item_data, BASE, HEADERS, FALLBACK_BASE, FALLBACK_HEADERS,
    fetch_with_fallback, convert_1h_data_to_dict
)
import utils.shared
from utils.database import get_price_historicals
from utils.item_metadata import get_item_meta, get_buy_limit
from utils.recipe_data import get_recipe, get_decant_set
from security import rate_limit
import requests

bp = Blueprint('api_items', __name__, url_prefix='/api')

@bp.route('/item/<int:item_id>', methods=['GET'])
@rate_limit(max_requests=200, window=60)
def api_item_get(item_id):
    """Get item information including metadata, prices, and current opportunity"""
    try:
        item_meta = get_item_meta(item_id)
        if not item_meta:
            return jsonify({"error": "Item not found"}), 404
        
        max_buy_4h = item_meta.get('buy_limit', 0)
        item_name = item_meta.get('name', f'Item {item_id}')
        
        try:
            latest, _ = fetch_with_fallback(
                f"{BASE}/latest", HEADERS,
                f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
                FALLBACK_HEADERS if FALLBACK_BASE else None, timeout=10
            )
            
            price_data = latest.get("data", {}).get(str(item_id), {})
            low = price_data.get("low")
            high = price_data.get("high")
            insta_buy = price_data.get("high", low)
            insta_sell = price_data.get("low", high)
            
            h1_raw, _ = fetch_with_fallback(
                f"{BASE}/1h", HEADERS, None, None, timeout=10
            )
            h1 = convert_1h_data_to_dict(h1_raw)
            volume = h1.get(str(item_id), {}).get("volume", 0) or 0
            
        except Exception as e:
            print(f"[WARN] Failed to fetch price data for item {item_id}: {e}")
            low = high = insta_buy = insta_sell = None
            volume = 0
        
        historicals = get_price_historicals(item_id)
        
        opportunity = None
        with get_item_lock():
            item_data = get_item_data()
            for dump in item_data['dump_items']:
                if dump.get('id') == item_id:
                    opportunity = {**dump, 'max_buy_4h': max_buy_4h}
                    break
        
        try:
            from utils.dump_engine import analyze_dumps
            opportunities = analyze_dumps()
            for opp in opportunities:
                if opp.get('item_id') == item_id or opp.get('id') == item_id:
                    opportunity = {
                        'tier': opp.get('tier'),
                        'score': opp.get('score'),
                        'drop_pct': opp.get('drop_pct'),
                        'emoji': opp.get('emoji')
                    }
                    break
        except (KeyError, ValueError, AttributeError) as e:
            print(f"[ERROR] Failed to process opportunity for item {item_id}: {e}")
        
        result = {
            "id": item_id,
            "name": item_name,
            "buy": low,
            "sell": high,
            "high": high,
            "low": low,
            "insta_buy": insta_buy,
            "insta_sell": insta_sell,
            "volume": volume,
            "max_buy_4h": max_buy_4h,
            "limit": max_buy_4h,
            **historicals
        }
        
        if opportunity:
            result['opportunity'] = opportunity
        
        return jsonify(result)
        
    except Exception as e:
        print(f"[ERROR] api_item_get: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@bp.route('/item/search', methods=['GET'])
@rate_limit(max_requests=200, window=60)
def api_item_search():
    """Search for items by name fragment"""
    query = request.args.get('q', '').strip().lower()
    
    if not query or len(query) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400
    
    try:
        matches = []
        with get_item_lock():
            for item_id_str, name in utils.shared.item_names.items():
                if query in name.lower():
                    item_id = int(item_id_str)
                    max_buy_4h = get_buy_limit(item_id)
                    matches.append({
                        "id": item_id,
                        "name": name,
                        "max_buy_4h": max_buy_4h
                    })
                    if len(matches) >= 50:
                        break
        
        matches.sort(key=lambda x: x['name'])
        return jsonify(matches)
        
    except Exception as e:
        print(f"[ERROR] api_item_search: {e}")
        return jsonify({"error": str(e)}), 500

@bp.route('/recipe', methods=['GET'])
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
        
        try:
            latest, _ = fetch_with_fallback(
                f"{BASE}/latest", HEADERS,
                f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
                FALLBACK_HEADERS if FALLBACK_BASE else None, timeout=10
            )
            price_data = latest.get("data", {})
        except Exception as e:
            print(f"[WARN] Failed to fetch prices for recipe: {e}")
            price_data = {}
        
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
        
        spread_info = {}
        if product_low and product_high and total_ingredient_cost_low:
            profit_low_high = product_high - total_ingredient_cost_low
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

@bp.route('/decant', methods=['GET'])
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
        
        try:
            latest, _ = fetch_with_fallback(
                f"{BASE}/latest", HEADERS,
                f"{FALLBACK_BASE}/latest" if FALLBACK_BASE else None,
                FALLBACK_HEADERS if FALLBACK_BASE else None, timeout=10
            )
            price_data = latest.get("data", {})
        except Exception as e:
            print(f"[WARN] Failed to fetch prices for decant: {e}")
            price_data = {}
        
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

