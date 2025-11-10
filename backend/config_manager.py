# backend/config_manager.py
import json, os
from typing import Dict, List

CONFIG_DIR = "server_configs"
BANNED_FILE = "banned_servers.json"
os.makedirs(CONFIG_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "guild_id": None,
    "channels": {
        "cheap_flips": None,           # < 10k gp
        "medium_flips": None,          # 10k - 500k
        "expensive_flips": None,       # 500k - 50M
        "billionaire_flips": None,     # > 50M
        "recipe_items": None,          # Herblore/Crafting
        "high_alch_margins": None,
        "high_limit_items": None       # > 10k limit + high vol
    },
    "roles": {
        # Risk-based role pings
        "risk_low": None,              # Low risk dumps (< 20)
        "risk_medium": None,           # Medium risk dumps (20-40)
        "risk_high": None,             # High risk dumps (40-60)
        "risk_very_high": None,       # Very high risk dumps (60+)
        # Quality-based role pings
        "quality_nuclear": None,      # Nuclear dumps (1.5M+ volume)
        "quality_god_tier": None,      # God-tier dumps (5 stars)
        "quality_elite": None,         # Elite dumps (4 stars)
        "quality_premium": None,       # Premium dumps (3 stars)
        "quality_good": None,          # Good dumps (2 stars)
        "quality_deal": None,          # Deal dumps (1 star)
        # General notification roles
        "dumps": None,                 # All dumps
        "spikes": None,                # All spikes
        "flips": None                  # All flips
    },
    "thresholds": {
        "cheap_max": 10000,
        "medium_max": 500000,
        "expensive_max": 50000000,
        "high_limit_min": 10000,
        "high_volume_min": 50000,
        "high_alch_profit_min": 500000
    },
    "enabled": True
}

def get_config(guild_id: str) -> Dict:
    """Get server configuration with path sanitization"""
    # Sanitize guild_id to prevent path traversal
    if not guild_id or not isinstance(guild_id, str):
        return DEFAULT_CONFIG.copy()
    
    # Discord IDs are numeric, 17-19 digits
    import re
    if not re.match(r'^\d{17,19}$', guild_id):
        return DEFAULT_CONFIG.copy()
    
    # Use safe path joining
    path = os.path.join(CONFIG_DIR, f"{guild_id}.json")
    # Ensure path is within CONFIG_DIR (prevent directory traversal)
    if not os.path.abspath(path).startswith(os.path.abspath(CONFIG_DIR)):
        return DEFAULT_CONFIG.copy()
    
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()
    else:
        config = DEFAULT_CONFIG.copy()
        config["guild_id"] = guild_id
        save_config(guild_id, config)
        return config

def save_config(guild_id: str, config: Dict):
    """Save server configuration with path sanitization"""
    # Sanitize guild_id
    if not guild_id or not isinstance(guild_id, str):
        return
    
    import re
    if not re.match(r'^\d{17,19}$', guild_id):
        return
    
    # Use safe path joining
    path = os.path.join(CONFIG_DIR, f"{guild_id}.json")
    # Ensure path is within CONFIG_DIR
    if not os.path.abspath(path).startswith(os.path.abspath(CONFIG_DIR)):
        return
    
    try:
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
    except IOError:
        pass  # Silently fail on write errors

def list_servers() -> List[str]:
    """List all server IDs with validation"""
    try:
        files = os.listdir(CONFIG_DIR)
        servers = []
        import re
        for f in files:
            if f.endswith('.json'):
                guild_id = f.split('.')[0]
                # Validate guild_id format
                if re.match(r'^\d{17,19}$', guild_id):
                    servers.append(guild_id)
        return servers
    except (OSError, IOError):
        return []

def load_banned() -> set:
    """Load banned server IDs"""
    if os.path.exists(BANNED_FILE):
        try:
            with open(BANNED_FILE) as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_banned(banned_set: set):
    """Save banned server IDs"""
    with open(BANNED_FILE, 'w') as f:
        json.dump(list(banned_set), f, indent=2)

def is_banned(guild_id: str) -> bool:
    """Check if a server is banned"""
    return guild_id in load_banned()

def ban_server(guild_id: str):
    """Ban a server"""
    banned = load_banned()
    banned.add(guild_id)
    save_banned(banned)

def unban_server(guild_id: str):
    """Unban a server"""
    banned = load_banned()
    banned.discard(guild_id)
    save_banned(banned)

def delete_config(guild_id: str):
    """Delete a server's configuration with path sanitization"""
    # Sanitize guild_id
    if not guild_id or not isinstance(guild_id, str):
        return
    
    import re
    if not re.match(r'^\d{17,19}$', guild_id):
        return
    
    # Use safe path joining
    path = os.path.join(CONFIG_DIR, f"{guild_id}.json")
    # Ensure path is within CONFIG_DIR
    if not os.path.abspath(path).startswith(os.path.abspath(CONFIG_DIR)):
        return
    
    try:
        if os.path.exists(path):
            os.remove(path)
    except (IOError, OSError):
        pass  # Silently fail on delete errors