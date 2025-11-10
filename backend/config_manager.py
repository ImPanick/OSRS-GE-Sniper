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
    path = f"{CONFIG_DIR}/{guild_id}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    else:
        config = DEFAULT_CONFIG.copy()
        config["guild_id"] = guild_id
        save_config(guild_id, config)
        return config

def save_config(guild_id: str, config: Dict):
    path = f"{CONFIG_DIR}/{guild_id}.json"
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)

def list_servers() -> List[str]:
    return [f.split('.')[0] for f in os.listdir(CONFIG_DIR) if f.endswith('.json')]

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
    """Delete a server's configuration"""
    path = f"{CONFIG_DIR}/{guild_id}.json"
    if os.path.exists(path):
        os.remove(path)