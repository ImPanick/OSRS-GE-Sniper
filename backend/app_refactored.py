"""
Main Flask application - refactored to use blueprints
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import os

# Import blueprints
from routes_core import bp as core_bp
from routes_api_items import bp as items_bp
from routes_api_dumps import bp as dumps_bp
from routes_admin import bp as admin_bp

# Import background tasks
from background_tasks import start_background_tasks

# Import shared utilities
from utils.shared import CONFIG, is_local_request

app = Flask(__name__, static_folder='static', static_url_path='/static')

# CORS configuration
cors_origins = os.getenv('CORS_ORIGINS', '*').split(',')
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# Register blueprints
app.register_blueprint(core_bp)
app.register_blueprint(items_bp)
app.register_blueprint(dumps_bp)
app.register_blueprint(admin_bp)

# Security headers middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
    return response

# Setup check middleware
@app.before_request
def check_setup():
    """Check setup status - frontend handles redirects"""
    if request.path.startswith('/api'):
        return None
    if request.path.startswith('/static'):
        return None
    if request.path.startswith('/admin') or request.path.startswith('/config'):
        if not is_local_request():
            return jsonify({"error": "Access denied. Admin interface is LAN-only."}), 403
    return None

# Initialize background tasks
_poll_thread_started = False

def _start_background_tasks():
    """Start background tasks (database init and polling thread)"""
    global _poll_thread_started
    if _poll_thread_started:
        return
    start_background_tasks()
    _poll_thread_started = True

# Start background tasks when module is imported
_start_background_tasks()

if __name__ == '__main__':
    # SECURITY NOTE: host='0.0.0.0' binds to all interfaces
    # This is REQUIRED for Docker container networking to work properly
    # Security is ensured through:
    # 1. Docker network isolation (containers only accessible via exposed ports)
    # 2. Firewall rules (only port 5000 should be exposed if needed)
    # 3. Rate limiting on all endpoints (see security.py)
    # 4. Admin key authentication for sensitive endpoints
    # DO NOT change this unless you understand Docker networking implications
    app.run(host='0.0.0.0', port=5000)

