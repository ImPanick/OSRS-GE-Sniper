"""
Admin and configuration routes blueprint

NOTE: This module defines JSON APIs only. UI is handled exclusively by the Next.js frontend.
"""
from flask import Blueprint, jsonify, request
from utils.shared import CONFIG_PATH, is_local_request
import utils.shared
from config_manager import (
    get_config, save_config, is_banned, ban_server, unban_server, 
    list_servers, delete_config
)
from utils.database import (
    get_all_tiers, get_guild_tier_settings, get_guild_config,
    update_tier, update_guild_tier_setting, update_guild_config,
    get_guild_alert_settings, update_guild_alert_settings,
    get_unified_guild_config
)
from security import (
    rate_limit, validate_json_payload, require_admin_key,
    sanitize_guild_id, sanitize_channel_id, sanitize_webhook_url,
    sanitize_token, escape_html, encrypt_token
)
from datetime import datetime
import json
import os
import secrets
import requests

bp = Blueprint('admin', __name__)

# Server config routes
@bp.route('/api/server_config/<guild_id>', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_server_config(guild_id):
    """API endpoint for bot to fetch server config"""
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if is_banned(guild_id):
        return jsonify({"error": "banned"}), 403
    
    config = get_config(guild_id)
    return jsonify(config)

@bp.route('/api/server_banned/<guild_id>', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_server_banned(guild_id):
    """API endpoint for bot to check if server is banned"""
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"banned": False})
    
    return jsonify({"banned": is_banned(guild_id)})

@bp.route('/api/server_info/<guild_id>', methods=['POST'])
@rate_limit(max_requests=50, window=60)
def api_server_info_update(guild_id):
    """API endpoint for bot to update server information"""
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        server_info_path = os.path.join("server_configs", f"{guild_id}_info.json")
        if not os.path.abspath(server_info_path).startswith(os.path.abspath("server_configs")):
            return jsonify({"error": "Invalid path"}), 400
        
        with open(server_info_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({"status": "updated"})
    except Exception as e:
        print(f"[ERROR] api_server_info_update: {e}")
        return jsonify({"error": "Failed to update server info"}), 500

@bp.route('/api/server_info/<guild_id>', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_server_info_get(guild_id):
    """API endpoint to get server information for admin panel"""
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    try:
        server_info_path = os.path.join("server_configs", f"{guild_id}_info.json")
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

@bp.route('/api/server_info/<guild_id>/assign_role', methods=['POST'])
@rate_limit(max_requests=30, window=60)
def api_assign_role(guild_id):
    """API endpoint to assign a role to a member (via bot)"""
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        action = data.get('action', 'add')
        
        if not user_id or not role_id:
            return jsonify({"error": "Missing user_id or role_id"}), 400
        
        assignment_path = os.path.join("server_configs", f"{guild_id}_assignments.json")
        if not os.path.abspath(assignment_path).startswith(os.path.abspath("server_configs")):
            return jsonify({"error": "Invalid path"}), 400
        
        assignments = []
        if os.path.exists(assignment_path):
            with open(assignment_path, 'r') as f:
                assignments = json.load(f)
        
        assignment = {
            "user_id": str(user_id),
            "role_id": str(role_id),
            "action": action,
            "timestamp": int(datetime.now().timestamp())
        }
        assignments.append(assignment)
        assignments = assignments[-100:]
        
        with open(assignment_path, 'w') as f:
            json.dump(assignments, f, indent=2)
        
        return jsonify({"status": "queued"})
    except Exception as e:
        print(f"[ERROR] api_assign_role: {e}")
        return jsonify({"error": "Failed to queue role assignment"}), 500

@bp.route('/api/server_info/<guild_id>/assignments', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_get_assignments(guild_id):
    """API endpoint for bot to get pending role assignments"""
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
            current_time = int(datetime.now().timestamp())
            assignments = [a for a in assignments if current_time - a.get('timestamp', 0) < 60]
            
            with open(assignment_path, 'w') as f:
                json.dump(assignments, f, indent=2)
            
            return jsonify(assignments)
        else:
            return jsonify([])
    except Exception as e:
        print(f"[ERROR] api_get_assignments: {e}")
        return jsonify({"error": "Failed to get assignments"}), 500

@bp.route('/config/<guild_id>', methods=['GET', 'POST'])
@rate_limit(max_requests=30, window=60)
def server_config(guild_id):
    """Server configuration endpoint"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Configuration interface is LAN-only."}), 403
    
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if is_banned(guild_id):
        return jsonify({"error": "This server has been banned from using the sniper bot."}), 403
    
    config = get_config(guild_id)
    
    if "roles" not in config:
        config["roles"] = {}
    
    if request.method == 'POST':
        try:
            data = request.get_json(force=True)
            if not data:
                return jsonify({"error": "Invalid JSON"}), 400
            
            # Update channels
            if 'channels' in data:
                channels = {}
                for key, value in data.get('channels', {}).items():
                    if value:
                        sanitized = sanitize_channel_id(str(value))
                        channels[key] = sanitized if sanitized else None
                    else:
                        channels[key] = None
                config['channels'] = channels
            
            # Update roles
            if 'roles' in data:
                config['roles'] = data['roles']
            
            # Update thresholds
            if 'thresholds' in data:
                config['thresholds'] = {**config.get('thresholds', {}), **data['thresholds']}
            
            # Update enabled status
            if 'enabled' in data:
                config['enabled'] = bool(data['enabled'])
            
            # Update tier settings if provided
            if 'tier_settings' in data:
                for tier_name, tier_data in data['tier_settings'].items():
                    role_id = tier_data.get('role_id')
                    enabled = tier_data.get('enabled', True)
                    update_guild_tier_setting(guild_id, tier_name, role_id=role_id, enabled=enabled)
            
            # Update min tier for alerts
            if 'min_tier_name' in data:
                min_tier_name = data['min_tier_name']
                if min_tier_name == "":
                    min_tier_name = None
                update_guild_config(guild_id, min_tier_name=min_tier_name)
            
            save_config(guild_id, config)
            return jsonify({"status": "saved", "config": config})
        except Exception as e:
            print(f"[ERROR] server_config POST: {e}")
            return jsonify({"error": "Failed to save configuration"}), 500
    
    return jsonify(config)

@bp.route('/config/<guild_id>/tiers', methods=['GET'])
@rate_limit(max_requests=30, window=60)
def tier_config_page(guild_id):
    """
    Tier configuration endpoint - UI has moved to Next.js frontend.
    This endpoint returns tier configuration data as JSON.
    """
    if not is_local_request():
        return jsonify({"error": "Access denied. Configuration interface is LAN-only."}), 403
    
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if is_banned(guild_id):
        return jsonify({"error": "This server has been banned from using the sniper bot."}), 403
    
    # Get tier configuration directly from database
    try:
        tiers = get_all_tiers()
        guild_settings = get_guild_tier_settings(guild_id)
        guild_config = get_guild_config(guild_id)
        tiers_data = {
            "tiers": tiers,
            "guild_tier_settings": guild_settings,
            "min_tier_name": guild_config.get("min_tier_name"),
            "message": "Use the Next.js frontend for UI. This endpoint is now API-only.",
            "frontend_url": f"http://localhost:3000/config/{guild_id}"
        }
        return jsonify(tiers_data)
    except Exception as e:
        print(f"[ERROR] Failed to fetch tiers: {e}")
        return jsonify({
            "tiers": [],
            "guild_tier_settings": {},
            "min_tier_name": None,
            "error": str(e)
        }), 500

# Setup routes
@bp.route('/api/setup/save-token', methods=['POST'])
@validate_json_payload(max_size=5000)
@rate_limit(max_requests=5, window=300)
def setup_save_token():
    """Save Discord bot token (encrypted)"""
    if not is_local_request():
        return jsonify({"error": "Setup can only be done from local network"}), 403
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        token = data.get('discord_token', '').strip()
        token = sanitize_token(token)
        if not token:
            return jsonify({"error": "Invalid token format"}), 400
        
        # Ensure admin_key exists before encryption (needed for key derivation)
        if not utils.shared.CONFIG.get('admin_key') or utils.shared.CONFIG.get('admin_key') == 'CHANGE_THIS_TO_A_SECURE_RANDOM_STRING':
            utils.shared.CONFIG['admin_key'] = secrets.token_urlsafe(32)
        
        # Encrypt the token before storing
        encrypted_token = encrypt_token(token, utils.shared.CONFIG.get('admin_key'))
        utils.shared.CONFIG['discord_token'] = encrypted_token
        
        # Determine root config path (prioritize root config.json)
        root_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
        if not os.path.exists(root_config_path):
            # Fallback to current CONFIG_PATH
            root_config_path = CONFIG_PATH
        
        # Save to root config.json (where bot reads from)
        try:
            with open(root_config_path, 'w') as f:
                json.dump(utils.shared.CONFIG, f, indent=2)
        except IOError:
            return jsonify({"error": "Failed to save configuration"}), 500
        
        # Also save to backend config.json if different (for backend access)
        if root_config_path != CONFIG_PATH:
            try:
                with open(CONFIG_PATH, 'w') as f:
                    json.dump(utils.shared.CONFIG, f, indent=2)
            except IOError:
                pass  # Non-critical, root config is primary
        
        # Reload CONFIG from file
        with open(root_config_path, 'r') as f:
            utils.shared.CONFIG = json.load(f)
        
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": f"Invalid request: {str(e)}"}), 400

@bp.route('/api/setup/test-bot', methods=['GET'])
@rate_limit(max_requests=10, window=60)
def setup_test_bot():
    """Test Discord bot connection"""
    if not is_local_request():
        return jsonify({"error": "Setup can only be done from local network"}), 403
    
    token = utils.shared.CONFIG.get('discord_token', '')
    
    if not token or token == 'YOUR_BOT_TOKEN_HERE':
        return jsonify({"error": "Bot token not configured"}), 400
    
    if not sanitize_token(token):
        return jsonify({"error": "Invalid token format"}), 400
    
    try:
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
            return jsonify({"error": "Failed to connect to Discord API"}), 400
    except requests.exceptions.Timeout:
        return jsonify({"error": "Connection timeout"}), 400
    except Exception as e:
        print(f"[ERROR] setup_test_bot: {e}")
        return jsonify({"error": "Connection failed"}), 400

@bp.route('/api/setup/save-server', methods=['POST'])
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
        
        channels = {}
        if 'channels' in data:
            for key, value in data.get('channels', {}).items():
                if value:
                    sanitized = sanitize_channel_id(str(value))
                    channels[key] = sanitized if sanitized else None
                else:
                    channels[key] = None
        
        server_config = get_config(guild_id)
        server_config['channels'] = channels
        save_config(guild_id, server_config)
        
        return jsonify({"status": "saved", "guild_id": guild_id})
    except Exception as e:
        print(f"[ERROR] setup_save_server: {e}")
        return jsonify({"error": "Invalid request data"}), 400

@bp.route('/api/setup/save-webhook', methods=['POST'])
@validate_json_payload(max_size=1000)
@rate_limit(max_requests=10, window=60)
def setup_save_webhook():
    """Save Discord webhook"""
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
            
            utils.shared.CONFIG['discord_webhook'] = webhook
            try:
                with open(CONFIG_PATH, 'w') as f:
                    json.dump(utils.shared.CONFIG, f, indent=2)
            except IOError:
                return jsonify({"error": "Failed to save configuration"}), 500
            
            # Reload CONFIG
            with open(CONFIG_PATH, 'r') as f:
                utils.shared.CONFIG = json.load(f)
        
        return jsonify({"status": "saved"})
    except Exception as e:
        print(f"[ERROR] setup_save_webhook: {e}")
        return jsonify({"error": "Invalid request data"}), 400

@bp.route('/api/setup/complete', methods=['POST'])
@rate_limit(max_requests=10, window=60)
def setup_complete():
    """Mark setup as complete"""
    if not is_local_request():
        return jsonify({"error": "Setup can only be done from local network"}), 403
    
    return jsonify({"status": "complete"})

# Admin endpoints
@bp.route('/admin/servers', methods=['GET'])
@require_admin_key()
@rate_limit(max_requests=30, window=60)
def admin_list_servers():
    """List all servers"""
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

@bp.route('/admin/ban/<guild_id>', methods=['POST'])
@require_admin_key()
@rate_limit(max_requests=20, window=60)
def admin_ban_server(guild_id):
    """Ban a server"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    ban_server(guild_id)
    return jsonify({"status": "banned", "guild_id": guild_id})

@bp.route('/admin/unban/<guild_id>', methods=['POST'])
@require_admin_key()
@rate_limit(max_requests=20, window=60)
def admin_unban_server(guild_id):
    """Unban a server"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    unban_server(guild_id)
    return jsonify({"status": "unbanned", "guild_id": guild_id})

@bp.route('/admin/delete/<guild_id>', methods=['DELETE'])
@require_admin_key()
@rate_limit(max_requests=10, window=60)
def admin_delete_server(guild_id):
    """Delete a server configuration"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    delete_config(guild_id)
    return jsonify({"status": "deleted", "guild_id": guild_id})

# Tier management admin routes
@bp.route('/admin/tiers', methods=['GET'])
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

@bp.route('/admin/tiers', methods=['POST'])
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
        
        tier_updates = data.get('tiers', [])
        for tier_update in tier_updates:
            tier_id = tier_update.get('id')
            min_score = tier_update.get('min_score')
            max_score = tier_update.get('max_score')
            
            if tier_id is not None:
                if min_score is not None or max_score is not None:
                    update_tier(tier_id, min_score, max_score)
        
        if guild_id:
            guild_tier_settings = data.get('guild_tier_settings', [])
            for setting in guild_tier_settings:
                tier_name = setting.get('tier_name')
                role_id = setting.get('role_id')
                enabled = setting.get('enabled')
                
                if tier_name:
                    if role_id == "":
                        role_id = None
                    update_guild_tier_setting(guild_id, tier_name, role_id=role_id, enabled=enabled)
            
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

# Update endpoints
@bp.route('/api/update/check', methods=['GET'])
@require_admin_key()
def check_updates():
    """Check if updates are available"""
    try:
        from utils.auto_updater import get_update_status
        status = get_update_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/api/update/status', methods=['GET'])
@require_admin_key()
def update_status():
    """Get update status and history"""
    try:
        from utils.auto_updater import get_update_status
        return jsonify(get_update_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/api/update/pull', methods=['POST'])
@require_admin_key()
def pull_updates():
    """Pull latest updates from GitHub"""
    try:
        from utils.auto_updater import update_code
        restart = request.json.get('restart_services', True) if request.json else True
        result = update_code(restart_services=restart)
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

@bp.route('/api/config/<guild_id>', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_get_guild_config(guild_id):
    """Get unified guild configuration (accessible to bot and local requests)"""
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if is_banned(guild_id):
        return jsonify({"error": "This server has been banned from using the sniper bot."}), 403
    
    try:
        config = get_unified_guild_config(guild_id)
        return jsonify(config)
    except Exception as e:
        print(f"[ERROR] api_get_guild_config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to get guild configuration"}), 500

@bp.route('/api/config/<guild_id>', methods=['POST'])
@rate_limit(max_requests=30, window=60)
def api_save_guild_config(guild_id):
    """Save unified guild configuration"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Configuration interface is LAN-only."}), 403
    
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if is_banned(guild_id):
        return jsonify({"error": "This server has been banned from using the sniper bot."}), 403
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Validate and extract settings
        alert_channel_id = data.get('alert_channel_id')
        min_margin_gp = data.get('min_margin_gp')
        min_score = data.get('min_score')
        enabled_tiers = data.get('enabled_tiers')
        role_ids_per_tier = data.get('role_ids_per_tier', {})
        min_tier_name = data.get('min_tier_name')
        max_alerts_per_interval = data.get('max_alerts_per_interval')
        
        # Validate alert_channel_id
        if alert_channel_id is not None:
            if alert_channel_id == "":
                alert_channel_id = None
            else:
                alert_channel_id = sanitize_channel_id(str(alert_channel_id))
                if not alert_channel_id:
                    return jsonify({"error": "Invalid alert_channel_id format"}), 400
        
        # Validate min_margin_gp
        if min_margin_gp is not None:
            try:
                min_margin_gp = int(min_margin_gp)
                if min_margin_gp < 0:
                    return jsonify({"error": "min_margin_gp must be >= 0"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "min_margin_gp must be an integer"}), 400
        
        # Validate min_score
        if min_score is not None:
            try:
                min_score = int(min_score)
                if min_score < 0 or min_score > 100:
                    return jsonify({"error": "min_score must be between 0 and 100"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "min_score must be an integer"}), 400
        
        # Validate enabled_tiers
        if enabled_tiers is not None:
            if not isinstance(enabled_tiers, list):
                return jsonify({"error": "enabled_tiers must be an array"}), 400
            valid_tiers = ['iron', 'copper', 'bronze', 'silver', 'gold', 'platinum', 'ruby', 'sapphire', 'emerald', 'diamond']
            for tier in enabled_tiers:
                if tier.lower() not in valid_tiers:
                    return jsonify({"error": f"Invalid tier: {tier}. Must be one of: {', '.join(valid_tiers)}"}), 400
            # Normalize to lowercase
            enabled_tiers = [t.lower() for t in enabled_tiers]
        
        # Validate role_ids_per_tier
        if role_ids_per_tier is not None:
            if not isinstance(role_ids_per_tier, dict):
                return jsonify({"error": "role_ids_per_tier must be an object"}), 400
            # Validate each role_id
            for tier_name, role_id in role_ids_per_tier.items():
                if role_id is not None and role_id != "":
                    # Role IDs are Discord snowflakes (17-19 digits)
                    import re
                    if not re.match(r'^\d{17,19}$', str(role_id)):
                        return jsonify({"error": f"Invalid role_id for tier {tier_name}"}), 400
        
        # Validate max_alerts_per_interval
        if max_alerts_per_interval is not None:
            try:
                max_alerts_per_interval = int(max_alerts_per_interval)
                if max_alerts_per_interval < 1 or max_alerts_per_interval > 10:
                    return jsonify({"error": "max_alerts_per_interval must be between 1 and 10"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "max_alerts_per_interval must be an integer"}), 400
        
        # Update alert_channel_id in guild_config
        if alert_channel_id is not None:
            update_guild_config(guild_id, alert_channel_id=alert_channel_id)
        
        # Update min_tier_name in guild_config
        if min_tier_name is not None:
            if min_tier_name == "":
                min_tier_name = None
            update_guild_config(guild_id, min_tier_name=min_tier_name)
        
        # Update alert settings
        update_guild_alert_settings(
            guild_id,
            min_margin_gp=min_margin_gp,
            min_score=min_score,
            enabled_tiers=enabled_tiers,
            max_alerts_per_interval=max_alerts_per_interval
        )
        
        # Update role_ids_per_tier (update guild_tier_settings)
        if role_ids_per_tier is not None:
            for tier_name, role_id in role_ids_per_tier.items():
                # Get current setting to preserve enabled status
                tier_settings = get_guild_tier_settings(guild_id)
                current_setting = tier_settings.get(tier_name, {})
                enabled = current_setting.get("enabled", True)
                
                # Update with new role_id
                update_guild_tier_setting(
                    guild_id,
                    tier_name,
                    role_id=role_id if role_id else None,
                    enabled=enabled
                )
        
        # Return updated config
        config = get_unified_guild_config(guild_id)
        return jsonify({"status": "saved", "config": config})
    except Exception as e:
        print(f"[ERROR] api_save_guild_config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to save guild configuration"}), 500

@bp.route('/api/config/<guild_id>/alerts', methods=['GET'])
@rate_limit(max_requests=100, window=60)
def api_get_alert_settings(guild_id):
    """Get alert settings for a guild (accessible to bot and local requests) - DEPRECATED, use /api/config/<guild_id>"""
    # Allow bot to fetch settings (bot runs on same machine/network)
    
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if is_banned(guild_id):
        return jsonify({"error": "This server has been banned from using the sniper bot."}), 403
    
    try:
        settings = get_guild_alert_settings(guild_id)
        return jsonify(settings)
    except Exception as e:
        print(f"[ERROR] api_get_alert_settings: {e}")
        return jsonify({"error": "Failed to get alert settings"}), 500

@bp.route('/api/config/<guild_id>/alerts', methods=['POST'])
@rate_limit(max_requests=30, window=60)
def api_save_alert_settings(guild_id):
    """Save alert settings for a guild"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Configuration interface is LAN-only."}), 403
    
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if is_banned(guild_id):
        return jsonify({"error": "This server has been banned from using the sniper bot."}), 403
    
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Validate and extract settings
        min_margin_gp = data.get('min_margin_gp')
        min_score = data.get('min_score')
        enabled_tiers = data.get('enabled_tiers')
        max_alerts_per_interval = data.get('max_alerts_per_interval')
        
        # Validate min_margin_gp
        if min_margin_gp is not None:
            try:
                min_margin_gp = int(min_margin_gp)
                if min_margin_gp < 0:
                    return jsonify({"error": "min_margin_gp must be >= 0"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "min_margin_gp must be an integer"}), 400
        
        # Validate min_score
        if min_score is not None:
            try:
                min_score = int(min_score)
                if min_score < 0 or min_score > 100:
                    return jsonify({"error": "min_score must be between 0 and 100"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "min_score must be an integer"}), 400
        
        # Validate enabled_tiers
        if enabled_tiers is not None:
            if not isinstance(enabled_tiers, list):
                return jsonify({"error": "enabled_tiers must be an array"}), 400
            valid_tiers = ['iron', 'copper', 'bronze', 'silver', 'gold', 'platinum', 'ruby', 'sapphire', 'emerald', 'diamond']
            for tier in enabled_tiers:
                if tier.lower() not in valid_tiers:
                    return jsonify({"error": f"Invalid tier: {tier}. Must be one of: {', '.join(valid_tiers)}"}), 400
            # Normalize to lowercase
            enabled_tiers = [t.lower() for t in enabled_tiers]
        
        # Validate max_alerts_per_interval
        if max_alerts_per_interval is not None:
            try:
                max_alerts_per_interval = int(max_alerts_per_interval)
                if max_alerts_per_interval < 1 or max_alerts_per_interval > 10:
                    return jsonify({"error": "max_alerts_per_interval must be between 1 and 10"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "max_alerts_per_interval must be an integer"}), 400
        
        # Update settings
        success = update_guild_alert_settings(
            guild_id,
            min_margin_gp=min_margin_gp,
            min_score=min_score,
            enabled_tiers=enabled_tiers,
            max_alerts_per_interval=max_alerts_per_interval
        )
        
        if success:
            settings = get_guild_alert_settings(guild_id)
            return jsonify({"status": "saved", "settings": settings})
        else:
            return jsonify({"error": "Failed to save alert settings"}), 500
    except Exception as e:
        print(f"[ERROR] api_save_alert_settings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to save alert settings"}), 500

@bp.route('/api/admin/fetch_history', methods=['POST'])
@require_admin_key()
@rate_limit(max_requests=10, window=300)  # Limit to 10 requests per 5 minutes (more lenient for admin)
def api_admin_fetch_history():
    """
    Manually trigger a backfill of the last 4 hours of 5-minute GE price data.
    
    This endpoint fetches historical 5-minute snapshots from the OSRS Wiki API
    and stores them in the database for dump analysis.
    
    Accepts optional JSON body: { "hours": 4 }
    Default is 4 hours, max is 24 hours.
    
    Returns:
        JSON response with:
        - ok (bool): Success status
        - hours (int): Number of hours fetched
        - snapshots (int): Number of 5-minute snapshots fetched
        - items_written (int): Total number of item entries written to database
        - error (str, optional): Error message if failed
    """
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    try:
        data = request.get_json(force=True) if request.is_json else {}
        hours = data.get('hours', 4)
        
        # Validate hours parameter
        try:
            hours = int(hours)
            if hours < 1 or hours > 24:
                return jsonify({"error": "Hours must be between 1 and 24"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid hours parameter"}), 400
        
        # Import and call fetch_recent_history
        from utils.dump_engine import fetch_recent_history
        
        result = fetch_recent_history(hours=hours)
        
        # Check if there was an error
        if 'error' in result:
            return jsonify({
                "ok": False,
                "error": result.get('error'),
                "hours": result.get('hours', hours),
                "snapshots": result.get('snapshots', 0),
                "items_written": result.get('items_written', 0)
            }), 500
        
        return jsonify({
            "ok": True,
            "hours": result.get('hours', hours),
            "snapshots": result.get('snapshots', 0),
            "items_written": result.get('items_written', 0)
        })
        
    except Exception as e:
        print(f"[ERROR] api_admin_fetch_history failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": "Unexpected error occurred",
            "message": str(e)
        }), 500

@bp.route('/api/admin/cache/fetch_recent', methods=['POST'])
@require_admin_key()
@rate_limit(max_requests=10, window=300)  # Limit to 10 requests per 5 minutes (more lenient for admin)
def fetch_recent_cache():
    """
    Manually trigger a backfill of recent GE history data.
    
    Accepts optional JSON body: { "hours": 4 }
    Default is 4 hours, max is 24 hours.
    """
    if not is_local_request():
        return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    
    try:
        data = request.get_json(force=True) if request.is_json else {}
        hours = data.get('hours', 4)
        
        # Validate hours parameter
        try:
            hours = int(hours)
            if hours < 1 or hours > 24:
                return jsonify({"error": "Hours must be between 1 and 24"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid hours parameter"}), 400
        
        # Import and call fetch_recent_history
        from utils.dump_engine import fetch_recent_history
        
        result = fetch_recent_history(hours=hours)
        
        # Check if there was an error
        if 'error' in result:
            return jsonify({
                "ok": False,
                "error": result.get('error'),
                "hours": result.get('hours', hours),
                "snapshots": result.get('snapshots', 0),
                "items_written": result.get('items_written', 0)
            }), 500
        
        return jsonify({
            "ok": True,
            "hours": result.get('hours', hours),
            "snapshots": result.get('snapshots', 0),
            "items_written": result.get('items_written', 0)
        })
        
    except Exception as e:
        print(f"[ERROR] fetch_recent_cache failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": "Unexpected error occurred",
            "message": str(e)
        }), 500

