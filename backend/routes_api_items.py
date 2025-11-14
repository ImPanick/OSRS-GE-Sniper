"""
API routes for items, recipes, and decants

NOTE: This module defines JSON APIs only. UI is handled exclusively by the Next.js frontend.
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

bp = Blueprint('api_items', __name__, url_prefix='/api')

@bp.route('/item/<int:item_id>', methods=['GET'])
@bp.route('/item', methods=['GET'])
@rate_limit(max_requests=200, window=60)
def api_item_get(item_id=None):
    """Get item information including metadata, prices, and current opportunity
    
    Supports both ID lookup: /api/item/<id>
    And name lookup: /api/item?name=<item_name>
    """
    try:
        # Handle name-based lookup
        if item_id is None:
            name_query = request.args.get('name', '').strip()
            if not name_query:
                return jsonify({"error": "Missing 'name' parameter or item_id"}), 400
            
            # Search for item by name
            query_lower = name_query.lower()
            best_match = None
            exact_match = None
            
            with get_item_lock():
                item_data = get_item_data()
                for item_id_str, name in item_data['item_names'].items():
                    name_lower = name.lower()
                    if name_lower == query_lower:
                        exact_match = int(item_id_str)
                        break
                    elif query_lower in name_lower and not best_match:
                        best_match = int(item_id_str)
            
            if exact_match:
                item_id = exact_match
            elif best_match:
                item_id = best_match
            else:
                # Try metadata cache as fallback
                from utils.item_metadata import _metadata_cache
                for cached_id, meta in _metadata_cache.items():
                    meta_name = meta.get('name', '').lower()
                    if query_lower == meta_name:
                        item_id = cached_id
                        break
                    elif query_lower in meta_name and not best_match:
                        best_match = cached_id
                
                if not item_id and best_match:
                    item_id = best_match
            
            if not item_id:
                return jsonify({"error": f"Item not found: {name_query}"}), 404
        
        # Get item metadata
        item_meta = get_item_meta(item_id)
        if not item_meta:
            return jsonify({"error": "Item not found"}), 404
        
        max_buy_4h = item_meta.get('buy_limit', 0)
        item_name = item_meta.get('name', f'Item {item_id}')
        examine = item_meta.get('examine', '')
        members = item_meta.get('members', True)
        
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
        
        # Check for dump opportunity from dump engine
        opportunity = None
        try:
            from utils.dump_engine import analyze_dumps
            opportunities = analyze_dumps()
            for opp in opportunities:
                if opp.get('item_id') == item_id or opp.get('id') == item_id:
                    opportunity = {
                        'tier': opp.get('tier'),
                        'score': opp.get('score'),
                        'drop_pct': opp.get('drop_pct'),
                        'vol_spike_pct': opp.get('vol_spike_pct', 0),
                        'oversupply_pct': opp.get('oversupply_pct', 0),
                        'emoji': opp.get('emoji'),
                        'group': opp.get('group'),
                        'flags': opp.get('flags', [])
                    }
                    break
        except (KeyError, ValueError, AttributeError) as e:
            print(f"[ERROR] Failed to process opportunity for item {item_id}: {e}")
        
        # Calculate margin and profit metrics
        margin_gp = None
        max_profit_gp = None
        if high is not None and low is not None:
            margin_gp = high - low
            if max_buy_4h and max_buy_4h > 0:
                max_profit_gp = margin_gp * max_buy_4h
        
        result = {
            "id": item_id,
            "name": item_name,
            "examine": examine,
            "members": members,
            "buy": low,
            "sell": high,
            "high": high,
            "low": low,
            "insta_buy": insta_buy,
            "insta_sell": insta_sell,
            "volume": volume,
            "max_buy_4h": max_buy_4h,
            "limit": max_buy_4h,
            "margin_gp": margin_gp,
            "max_profit_gp": max_profit_gp,
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
    """Get recipe information with current prices and profit calculations"""
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
            ing_quantity = ing.get('quantity', 1)
            
            # Calculate cost for this ingredient (quantity * price)
            ing_cost_low = (ing_low * ing_quantity) if ing_low else 0
            ing_cost_high = (ing_high * ing_quantity) if ing_high else 0
            
            total_ingredient_cost_low += ing_cost_low
            total_ingredient_cost_high += ing_cost_high
            
            ingredient_list.append({
                "id": ing_id,
                "name": ing['name'],
                "quantity": ing_quantity,
                "low": ing_low,
                "high": ing_high,
                "cost_low": ing_cost_low,
                "cost_high": ing_cost_high,
                "max_buy_4h": ing_max_buy_4h
            })
        
        # Calculate profit scenarios
        spread_info = {}
        if product_low is not None and product_high is not None and total_ingredient_cost_low > 0:
            # Best case: buy ingredients at low, sell product at high
            profit_best = product_high - total_ingredient_cost_low
            profit_best_pct = (profit_best / total_ingredient_cost_low * 100) if total_ingredient_cost_low > 0 else 0
            
            # Worst case: buy ingredients at high, sell product at low
            profit_worst = product_low - total_ingredient_cost_high
            profit_worst_pct = (profit_worst / total_ingredient_cost_high * 100) if total_ingredient_cost_high > 0 else 0
            
            # Average case: average of both
            profit_avg = (profit_best + profit_worst) / 2
            avg_cost = (total_ingredient_cost_low + total_ingredient_cost_high) / 2
            profit_avg_pct = (profit_avg / avg_cost * 100) if avg_cost > 0 else 0
            
            # Profit per 4-hour buy limit (using product limit as constraint)
            profit_per_limit = None
            if product_max_buy_4h > 0:
                # Use the minimum of product limit and ingredient limits
                min_limit = product_max_buy_4h
                for ing in ingredient_list:
                    ing_limit = ing.get('max_buy_4h', 0)
                    if ing_limit > 0:
                        # Calculate how many products we can make with this ingredient
                        ing_qty = ing.get('quantity', 1)
                        products_from_ing = ing_limit // ing_qty
                        min_limit = min(min_limit, products_from_ing)
                
                profit_per_limit = profit_avg * min_limit if min_limit > 0 else None
            
            spread_info = {
                "total_ingredient_cost_low": total_ingredient_cost_low,
                "total_ingredient_cost_high": total_ingredient_cost_high,
                "product_low": product_low,
                "product_high": product_high,
                "profit_best": profit_best,
                "profit_best_pct": round(profit_best_pct, 2),
                "profit_worst": profit_worst,
                "profit_worst_pct": round(profit_worst_pct, 2),
                "profit_avg": profit_avg,
                "profit_avg_pct": round(profit_avg_pct, 2),
                "profit_per_limit": profit_per_limit,
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
    """Get decant information for a potion base name with gp_per_dose calculations"""
    name = request.args.get('name', '').strip()
    
    if not name:
        return jsonify({"error": "Missing required parameter: name"}), 400
    
    try:
        decant_set = get_decant_set(name)
        if not decant_set:
            return jsonify({"error": f"Decant set not found for: {name}"}), 404
        
        # Extract base name from first item (e.g., "Prayer potion(4)" -> "Prayer potion")
        base_name = name
        if decant_set:
            first_name = decant_set[0]['name']
            # Remove dose suffix like "(4)", "(3)", etc.
            import re
            base_match = re.match(r'^(.+?)\s*\(\d+\)$', first_name)
            if base_match:
                base_name = base_match.group(1).strip()
        
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
        best_variant = None
        best_gp_per_dose = None
        
        for dose_item in decant_set:
            dose_id = dose_item['id']
            dose_meta = get_item_meta(dose_id)
            dose_price_data = price_data.get(str(dose_id), {})
            dose_low = dose_price_data.get("low")
            dose_high = dose_price_data.get("high")
            dose_max_buy_4h = dose_meta.get('buy_limit', 0) if dose_meta else 0
            
            # Extract dose number from name (e.g., "Prayer potion(4)" -> 4)
            dose_number = 0
            import re
            dose_match = re.search(r'\((\d+)\)', dose_item['name'])
            if dose_match:
                dose_number = int(dose_match.group(1))
            
            # Calculate GP per dose
            gp_per_dose_low = (dose_low / dose_number) if dose_low and dose_number > 0 else None
            gp_per_dose_high = (dose_high / dose_number) if dose_high and dose_number > 0 else None
            
            variant_data = {
                "id": dose_id,
                "name": dose_item['name'],
                "dose": dose_number,
                "low": dose_low,
                "high": dose_high,
                "max_buy_4h": dose_max_buy_4h,
                "gp_per_dose_low": round(gp_per_dose_low, 2) if gp_per_dose_low else None,
                "gp_per_dose_high": round(gp_per_dose_high, 2) if gp_per_dose_high else None
            }
            
            dose_list.append(variant_data)
            
            # Track best variant (lowest GP per dose using low price)
            if gp_per_dose_low is not None:
                if best_gp_per_dose is None or gp_per_dose_low < best_gp_per_dose:
                    best_gp_per_dose = gp_per_dose_low
                    best_variant = variant_data
        
        # Sort by dose (highest first)
        dose_list.sort(key=lambda x: x.get('dose', 0), reverse=True)
        
        return jsonify({
            "base_name": base_name,
            "variants": dose_list,
            "best_gp_per_dose": best_variant
        })
        
    except Exception as e:
        print(f"[ERROR] api_decant: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

