"""
Shared utilities and constants for Flask routes
"""
import os
import json
import threading
import requests
import base64
from datetime import datetime

# Try to import cryptography for token decryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

# Thread-safe storage for item data
_item_lock = threading.Lock()
item_names = {}
top_items = []
dump_items = []
spike_items = []
all_items = []  # All items for volume tracker

# Load config with fallback paths for Docker and local development
# Priority: 1) CONFIG_PATH env var, 2) /repo/config.json (Docker), 3) relative paths (local dev)
CONFIG_PATH = os.getenv('CONFIG_PATH')
if not CONFIG_PATH:
    # Try Docker path first (/repo is mounted repo root)
    docker_path = '/repo/config.json'
    if os.path.exists(docker_path):
        CONFIG_PATH = docker_path
    else:
        # Fall back to relative paths for local development
        CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')
        if not os.path.exists(CONFIG_PATH):
            CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
        if not os.path.exists(CONFIG_PATH):
            CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')

# Note: config.json auto-creation is handled by Docker entrypoint script
# This ensures the file exists before Docker tries to mount it

CONFIG = {}
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r') as f:
            CONFIG = json.load(f)
    except (json.JSONDecodeError, IOError):
        CONFIG = {}

# Decrypt token if encrypted (for backward compatibility with plain tokens)
def _decrypt_token_if_needed(encrypted_token: str) -> str:
    """Decrypt token if encrypted, otherwise return as-is"""
    if not encrypted_token or not CRYPTOGRAPHY_AVAILABLE:
        return encrypted_token
    
    try:
        decoded = base64.urlsafe_b64decode(encrypted_token.encode())
        if decoded.startswith(b'gAAAAA'):  # Fernet token
            admin_key = CONFIG.get('admin_key', '')
            if admin_key:
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'osrs_ge_sniper_salt',
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(admin_key.encode()))
                fernet = Fernet(key)
                return fernet.decrypt(decoded).decode()
    except Exception:
        pass
    
    return encrypted_token

# Decrypt discord_token if present and encrypted
if 'discord_token' in CONFIG:
    CONFIG['discord_token'] = _decrypt_token_if_needed(CONFIG['discord_token'])

# Set default thresholds if not present
if "thresholds" not in CONFIG:
    CONFIG["thresholds"] = {}
CONFIG["thresholds"].setdefault("margin_min", 100000)  # 100k profit (was 2M - too high!)
CONFIG["thresholds"].setdefault("dump_drop_pct", 5)     # 5% drop (was 18% - too high!)
CONFIG["thresholds"].setdefault("spike_rise_pct", 5)    # 5% rise (was 20% - too high!)
CONFIG["thresholds"].setdefault("min_volume", 100)      # 100 volume (was 400 - reasonable)

# Primary OSRS API (official)
BASE = "https://prices.runescape.wiki/api/v1/osrs"
# Fallback API
FALLBACK_BASE = "https://grandexchange.tools/api"
# Improved User-Agent as required by API documentation
USER_AGENT = os.getenv('OSRS_API_USER_AGENT', "OSRS-GE-Sniper/1.0 (https://github.com/ImPanick/OSRS-GE-Sniper; contact@example.com)")
HEADERS = {"User-Agent": USER_AGENT}
FALLBACK_HEADERS = {"User-Agent": USER_AGENT}

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

def get_item_lock():
    """Get the thread lock for item data (returns the lock object itself)"""
    return _item_lock

def get_item_data():
    """Get thread-safe access to item data"""
    return {
        'item_names': item_names,
        'top_items': top_items,
        'dump_items': dump_items,
        'spike_items': spike_items,
        'all_items': all_items
    }

def set_item_data(**kwargs):
    """Set item data with thread-safe lock"""
    global item_names, top_items, dump_items, spike_items, all_items
    with _item_lock:
        if 'item_names' in kwargs:
            item_names = kwargs['item_names']
        if 'top_items' in kwargs:
            top_items = kwargs['top_items']
        if 'dump_items' in kwargs:
            dump_items = kwargs['dump_items']
        if 'spike_items' in kwargs:
            spike_items = kwargs['spike_items']
        if 'all_items' in kwargs:
            all_items = kwargs['all_items']

def ge_tax(sell):
    """Calculate Grand Exchange tax (1% up to 5M max)"""
    return min(0.01 * sell, 5_000_000)

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

def needs_setup():
    """Check if initial setup is needed"""
    if not CONFIG:
        return True
    
    # Check if config has placeholder values
    token = CONFIG.get('discord_token', '').strip()
    if not token or token == 'YOUR_BOT_TOKEN_HERE' or 'YOUR_BOT_TOKEN' in token.upper():
        return True
    
    admin_key = CONFIG.get('admin_key', '').strip()
    if not admin_key or admin_key == 'CHANGE_THIS_TO_A_SECURE_RANDOM_STRING':
        return True
    
    return False

def is_local_request():
    """Check if request is from local network"""
    from flask import request
    client_ip = request.remote_addr
    
    if not client_ip:
        return False
    
    # Check if localhost
    if client_ip in ['127.0.0.1', 'localhost', '::1']:
        return True
    
    # Check private IP ranges
    try:
        ip_parts = client_ip.split('.')
        if len(ip_parts) != 4:
            return False
        
        first_octet = ip_parts[0]
        second_octet = int(ip_parts[1])
        
        # 192.168.x.x
        if first_octet == '192' and ip_parts[1] == '168':
            return True
        # 10.x.x.x
        if first_octet == '10':
            return True
        # 172.16-31.x.x
        if first_octet == '172' and 16 <= second_octet <= 31:
            return True
    except (ValueError, IndexError):
        pass
    
    return False

