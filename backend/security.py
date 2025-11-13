# backend/security.py
"""
Security utilities for input validation, sanitization, and rate limiting
"""
import re
import hashlib
import time
from functools import wraps
from flask import request, jsonify
from collections import defaultdict

# Rate limiting storage (in-memory, resets on restart)
_rate_limit_store = defaultdict(list)
_rate_limit_window = 60  # 60 seconds
_rate_limit_max_requests = 100  # Max requests per window

def sanitize_guild_id(guild_id: str) -> str:
    """
    Sanitize guild ID to prevent path traversal attacks
    Only allows numeric strings (Discord IDs are numeric)
    """
    if not guild_id:
        return None
    
    # Discord IDs are numeric strings, 17-19 digits
    if not re.match(r'^\d{17,19}$', str(guild_id)):
        return None
    
    return str(guild_id)

def sanitize_channel_id(channel_id: str) -> str:
    """
    Sanitize channel ID or name
    Allows numeric IDs or alphanumeric names (no path traversal)
    """
    if not channel_id:
        return None
    
    channel_id = str(channel_id).strip()
    
    # If it's a numeric ID (Discord channel ID)
    if re.match(r'^\d{17,19}$', channel_id):
        return channel_id
    
    # If it's a channel name, sanitize it
    # Only allow alphanumeric, hyphens, underscores
    if re.match(r'^[a-zA-Z0-9_-]+$', channel_id):
        return channel_id
    
    return None

def sanitize_webhook_url(url: str) -> str:
    """
    Validate webhook URL format
    """
    if not url:
        return None
    
    url = str(url).strip()
    
    # Must be Discord webhook URL
    if not url.startswith('https://discord.com/api/webhooks/'):
        return None
    
    # Basic URL validation
    if len(url) > 500:  # Reasonable max length
        return None
    
    return url

def sanitize_token(token: str) -> str:
    """
    Validate Discord bot token format
    Discord bot tokens have the format: [part1].[part2].[part3]
    Each part is base64-like (A-Z, a-z, 0-9, _, -)
    Total length is typically 59-80 characters
    """
    if not token:
        return None
    
    token = str(token).strip()
    
    # Discord tokens have format: XXXX.XXXX.XXXX (three parts separated by dots)
    # Allow dots and base64-like characters, length 50-100 characters
    # Must contain exactly 2 dots (separating 3 parts)
    if not re.match(r'^[A-Za-z0-9_.-]{50,100}$', token):
        return None
    
    # Ensure it has the correct structure: exactly 2 dots separating 3 parts
    parts = token.split('.')
    if len(parts) != 3:
        return None
    
    # Each part should be non-empty
    if not all(part for part in parts):
        return None
    
    return token

def validate_json_payload(max_size: int = 10000):
    """
    Validate JSON payload size and structure
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "Content-Type must be application/json"}), 400
            
            # Check content length
            content_length = request.content_length
            if content_length and content_length > max_size:
                return jsonify({"error": f"Payload too large (max {max_size} bytes)"}), 413
            
            try:
                data = request.get_json(force=True)
                if data is None:
                    return jsonify({"error": "Invalid JSON"}), 400
            except Exception as e:
                return jsonify({"error": "Invalid JSON format"}), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def rate_limit(max_requests: int = None, window: int = None):
    """
    Rate limiting decorator
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            max_req = max_requests or _rate_limit_max_requests
            win = window or _rate_limit_window
            
            # Get client identifier (IP address)
            client_id = request.remote_addr or 'unknown'
            
            # Clean old entries
            current_time = time.time()
            _rate_limit_store[client_id] = [
                req_time for req_time in _rate_limit_store[client_id]
                if current_time - req_time < win
            ]
            
            # Check rate limit
            if len(_rate_limit_store[client_id]) >= max_req:
                return jsonify({
                    "error": "Rate limit exceeded",
                    "retry_after": int(win - (current_time - _rate_limit_store[client_id][0]))
                }), 429
            
            # Record request
            _rate_limit_store[client_id].append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_admin_key():
    """
    Decorator to require admin key in headers
    Note: CONFIG must be imported at runtime to avoid circular imports
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Import CONFIG at runtime to avoid circular import
            import sys
            import os
            import json
            
            # Get CONFIG_PATH from environment or default
            CONFIG_PATH = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(__file__), '..', 'config.json'))
            if not os.path.exists(CONFIG_PATH):
                CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
            if not os.path.exists(CONFIG_PATH):
                CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
            
            CONFIG = {}
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, 'r') as cfg_file:
                        CONFIG = json.load(cfg_file)
                except (json.JSONDecodeError, IOError):
                    CONFIG = {}
            
            admin_key = request.headers.get('X-Admin-Key')
            
            if not admin_key:
                return jsonify({"error": "Missing admin key"}), 401
            
            if admin_key != CONFIG.get('admin_key'):
                return jsonify({"error": "Invalid admin key"}), 401
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def sanitize_string(value: str, max_length: int = 200, allow_special: bool = False) -> str:
    """
    Sanitize string input
    """
    if not value:
        return None
    
    value = str(value).strip()
    
    if len(value) > max_length:
        return None
    
    if not allow_special:
        # Only allow alphanumeric, spaces, and basic punctuation
        if not re.match(r'^[a-zA-Z0-9\s\-_.,!?]+$', value):
            return None
    
    return value

def validate_numeric(value, min_val=None, max_val=None):
    """
    Validate numeric input
    """
    try:
        num = int(value)
        if min_val is not None and num < min_val:
            return None
        if max_val is not None and num > max_val:
            return None
        return num
    except (ValueError, TypeError):
        return None

def escape_html(text: str) -> str:
    """
    Escape HTML to prevent XSS
    """
    if not text:
        return ""
    
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;'))

def safe_path_join(base: str, *paths: str) -> str:
    """
    Safely join paths, preventing directory traversal
    """
    import os
    result = os.path.normpath(os.path.join(base, *paths))
    
    # Ensure result is within base directory
    base = os.path.normpath(base)
    if not result.startswith(base):
        return None
    
    return result

