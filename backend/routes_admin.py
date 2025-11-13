"""
Admin and configuration routes blueprint
"""
from flask import Blueprint, jsonify, request
from utils.shared import CONFIG, CONFIG_PATH, is_local_request
from config_manager import (
    get_config, save_config, is_banned, ban_server, unban_server, 
    list_servers, delete_config
)
from utils.database import (
    get_all_tiers, get_guild_tier_settings, get_guild_config,
    update_tier, update_guild_tier_setting, update_guild_config
)
from security import (
    rate_limit, validate_json_payload, require_admin_key,
    sanitize_guild_id, sanitize_channel_id, sanitize_webhook_url,
    sanitize_token, escape_html
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
    """Tier configuration page for a guild"""
    if not is_local_request():
        return jsonify({"error": "Access denied. Configuration interface is LAN-only."}), 403
    
    guild_id = sanitize_guild_id(guild_id)
    if not guild_id:
        return jsonify({"error": "Invalid server ID"}), 400
    
    if is_banned(guild_id):
        return jsonify({"error": "This server has been banned from using the sniper bot."}), 403
    
    from flask import render_template_string
    
    # Get tier configuration directly from database
    try:
        tiers = get_all_tiers()
        guild_settings = get_guild_tier_settings(guild_id)
        guild_config = get_guild_config(guild_id)
        tiers_data = {
            "tiers": tiers,
            "guild_tier_settings": guild_settings,
            "min_tier_name": guild_config.get("min_tier_name")
        }
    except Exception as e:
        print(f"[ERROR] Failed to fetch tiers: {e}")
        tiers_data = {"tiers": [], "guild_tier_settings": {}, "min_tier_name": None}
    
    TIER_CONFIG_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tier Configuration - {{ guild_id }}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <h1>⚙️ Tier Configuration</h1>
  
  <nav>
    <a href="/dashboard">📊 Dashboard</a>
    <a href="/volume_tracker">📈 Volume Tracker</a>
    <a href="/admin">🔒 Admin</a>
  </nav>
  
  <div style="max-width: 1200px; margin: 0 auto; padding: 0 2rem;">
    <div class="card" style="margin-bottom: 1rem;">
      <h3 style="margin: 0;">Guild ID: <code style="color: var(--accent-primary); background: var(--bg-tertiary); padding: 0.25rem 0.5rem; border-radius: var(--radius-sm);">{{ guild_id }}</code></h3>
    </div>
    
    <div class="card">
      <h2>🎯 Tier Settings</h2>
      <p style="color: var(--text-secondary); margin-bottom: 2rem;">
        Configure Discord role mentions for each tier and set minimum tier for automatic alerts.
      </p>
      
      <div id="tier-settings-container">
        <div style="text-align: center; padding: 2rem; color: var(--text-muted);">Loading tier settings...</div>
      </div>
      
      <div style="margin-top: 2rem; padding-top: 2rem; border-top: 1px solid var(--border-color);">
        <div class="filter-group" style="margin-bottom: 1.5rem;">
          <label>Minimum Tier for Automatic Alerts</label>
          <select id="min_tier_name" style="max-width: 300px;">
            <option value="">All Tiers</option>
            <option value="iron">Iron</option>
            <option value="copper">Copper</option>
            <option value="bronze">Bronze</option>
            <option value="silver">Silver</option>
            <option value="gold">Gold</option>
            <option value="platinum">Platinum</option>
            <option value="ruby">Ruby</option>
            <option value="sapphire">Sapphire</option>
            <option value="emerald">Emerald</option>
            <option value="diamond">Diamond</option>
          </select>
          <p style="color: var(--text-muted); font-size: 0.875rem; margin-top: 0.5rem;">
            Only tiers at or above this level will trigger automatic Discord alerts.
          </p>
        </div>
      </div>
      
      <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; margin-top: 2rem;">
        <button onclick="saveTierSettings()" style="min-width: 200px;">💾 Save Tier Settings</button>
        <button onclick="location.reload()" class="secondary" style="min-width: 200px;">🔄 Reset</button>
      </div>
      
      <div id="save_status" style="margin-top: 1.5rem; min-height: 1.5rem; text-align: center;"></div>
    </div>
  </div>
  
  <script>
    const guildId = '{{ guild_id }}';
    const tiersData = {{ tiers_json|safe }};
    
    function loadTierSettings() {
      renderTierSettings(tiersData);
    }
    
    function renderTierSettings(data) {
      const tiers = data.tiers || [];
      const minTierName = data.min_tier_name || '';
      
      // Set min tier dropdown
      document.getElementById('min_tier_name').value = minTierName;
      
      // Render tier settings
      let html = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;">';
      
      tiers.forEach(tier => {
        const setting = data.guild_tier_settings?.[tier.name] || {};
        const roleId = setting.role_id || '';
        const enabled = setting.enabled !== false;
        
        html += `
          <div class="card" style="padding: 1.5rem;">
            <h3 style="margin-top: 0; margin-bottom: 1rem;">
              ${tier.emoji} ${tier.name.charAt(0).toUpperCase() + tier.name.slice(1)}
            </h3>
            <p style="color: var(--text-muted); font-size: 0.875rem; margin-bottom: 1rem;">
              Score Range: ${tier.min_score} - ${tier.max_score} | Group: ${tier.group}
            </p>
            <div class="filter-group" style="margin-bottom: 1rem;">
              <label>Discord Role ID</label>
              <input type="text" 
                     id="tier_${tier.name}_role" 
                     placeholder="Role ID (e.g., 123456789012345678)" 
                     value="${roleId}">
              <p style="color: var(--text-muted); font-size: 0.75rem; margin-top: 0.25rem;">
                Leave empty to disable role mentions for this tier.
              </p>
            </div>
            <div class="filter-group">
              <label>
                <input type="checkbox" 
                       id="tier_${tier.name}_enabled" 
                       ${enabled ? 'checked' : ''}>
                Enable alerts for this tier
              </label>
            </div>
          </div>
        `;
      });
      
      html += '</div>';
      document.getElementById('tier-settings-container').innerHTML = html;
    }
    
    async function saveTierSettings() {
      const statusDiv = document.getElementById('save_status');
      statusDiv.innerHTML = '<div class="loading" style="margin: 0 auto;"></div><p style="margin-top: 0.5rem; color: var(--text-muted);">Saving...</p>';
      
      // Collect tier settings
      const tierSettings = {};
      const tierInputs = document.querySelectorAll('[id^="tier_"][id$="_role"], [id^="tier_"][id$="_enabled"]');
      
      tierInputs.forEach(input => {
        const match = input.id.match(/tier_(.+)_(role|enabled)/);
        if (match) {
          const tierName = match[1];
          const field = match[2];
          
          if (!tierSettings[tierName]) {
            tierSettings[tierName] = {};
          }
          
          if (field === 'role') {
            tierSettings[tierName].role_id = input.value.trim() || null;
          } else if (field === 'enabled') {
            tierSettings[tierName].enabled = input.checked;
          }
        }
      });
      
      const minTierName = document.getElementById('min_tier_name').value.trim() || null;
      
      try {
        const response = await fetch(`/config/${guildId}`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            tier_settings: tierSettings,
            min_tier_name: minTierName
          })
        });
        
        if (response.ok) {
          statusDiv.innerHTML = '<span style="color: var(--accent-success);">✅ Tier settings saved successfully!</span>';
          setTimeout(() => {
            statusDiv.innerHTML = '';
          }, 3000);
        } else {
          const error = await response.json().catch(() => ({error: 'Unknown error'}));
          statusDiv.innerHTML = `<span style="color: var(--accent-danger);">❌ Error: ${error.error || 'Failed to save settings'}</span>`;
        }
      } catch (error) {
        console.error('Save error:', error);
        statusDiv.innerHTML = `<span style="color: var(--accent-danger);">❌ Error: ${error.message}</span>`;
      }
    }
    
    // Load settings on page load
    loadTierSettings();
  </script>
</body>
</html>
"""
    
    # Convert tiers_data to JSON for JavaScript
    tiers_json = json.dumps(tiers_data)
    
    return render_template_string(TIER_CONFIG_TEMPLATE, guild_id=guild_id, tiers_json=tiers_json)

# Setup routes
@bp.route('/api/setup/save-token', methods=['POST'])
@validate_json_payload(max_size=5000)
@rate_limit(max_requests=5, window=300)
def setup_save_token():
    """Save Discord bot token"""
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
        
        utils.shared.CONFIG['discord_token'] = token
        
        if not utils.shared.CONFIG.get('admin_key') or utils.shared.CONFIG.get('admin_key') == 'CHANGE_THIS_TO_A_SECURE_RANDOM_STRING':
            utils.shared.CONFIG['admin_key'] = secrets.token_urlsafe(32)
        
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(utils.shared.CONFIG, f, indent=2)
        except IOError:
            return jsonify({"error": "Failed to save configuration"}), 500
        
        # Reload CONFIG from file
        with open(CONFIG_PATH, 'r') as f:
            import utils.shared as shared_utils
            shared_utils.CONFIG = json.load(f)
        
        return jsonify({"status": "saved"})
    except Exception:
        return jsonify({"error": "Invalid request"}), 400

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
                global CONFIG
                CONFIG = json.load(f)
        
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

