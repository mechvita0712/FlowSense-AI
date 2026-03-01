import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from .config import Config
from .extensions import db, jwt, socketio


def create_app(config_class=Config):
    # Configure Flask to serve frontend files
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'smart-campus-frontend')
    app = Flask(__name__, 
                static_folder=frontend_dir,
                static_url_path='')
    app.config.from_object(config_class)

    # Extensions
    db.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app)
    CORS(app)   # Allow frontend on any origin / port to reach the API

    # API blueprints
    from .routes.traffic import traffic_bp
    from .routes.auth import auth_bp
    from .routes.antigravity import ag_bp          # Anti-Gravity AI layer
    from .routes.admin import admin_bp             # Admin configuration
    from .routes.mobile import mobile_bp           # Mobile push notifications
    from .routes.events import events_bp           # Event management and forecasting

    app.register_blueprint(traffic_bp, url_prefix='/api/traffic')
    app.register_blueprint(auth_bp,    url_prefix='/api/auth')
    app.register_blueprint(ag_bp,      url_prefix='/api/antigravity')  # Anti-Gravity AI
    app.register_blueprint(admin_bp,   url_prefix='/api/admin')        # Admin panel
    app.register_blueprint(mobile_bp,  url_prefix='/api/mobile')       # Mobile integration
    app.register_blueprint(events_bp,  url_prefix='/api/events')       # Events & predictions

    # ── Frontend & API routes ─────────────────────────────────────────────────────

    @app.route('/')
    def index():
        """Serve the frontend dashboard."""
        return send_from_directory(app.static_folder, 'index.html')
    
    @app.route('/<path:path>')
    def serve_static(path):
        """Serve static frontend files (CSS, JS, etc.)."""
        if os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        # If file doesn't exist, return index.html for SPA routing
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/api')
    def api_info():
        """API directory for developers."""
        return jsonify({
            'name':      'SmartCampus AI — Mobility Backend',
            'version':   '2.1.0',
            'status':    'online',
            'note':      'Dashboard available at http://127.0.0.1:5000/',
            'endpoints': {
                'gates':      '/api/traffic/gates',
                'congestion': '/api/traffic/congestion',
                'shuttles':   '/api/traffic/shuttles',
                'routes':     '/api/traffic/routes',
                'predict':    '/api/traffic/predict         [POST]',
                'add':        '/api/traffic/add             [POST]',
                'login':      '/api/auth/login              [POST]',
                'register':   '/api/auth/register           [POST]',
                'me':         '/api/auth/me                 [GET, Bearer]',
                # ── Anti-Gravity AI ──────────────────────────────────────
                'ag_analyze': '/api/antigravity/analyze     [POST]',
                'ag_live':    '/api/antigravity/live        [GET]',
                'ag_health':  '/api/antigravity/health      [GET]',
                'ag_caps':    '/api/antigravity/capabilities [GET]',
            },
        })

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'message': 'Backend is running'}), 200

    # Create DB tables
    with app.app_context():
        db.create_all()

    return app
