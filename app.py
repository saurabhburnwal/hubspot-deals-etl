import hmac
from flask import Flask, request
from flask_cors import CORS
import logging
import os

from config import get_config
from api.routes import create_api
from loki_logger import configure_app_logging
from datetime import datetime, timezone
from models.database import initialize_database, check_database_health

def create_app(config_name: str = None) -> Flask:
    """Application factory function"""
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Setup CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://localhost:8080", "http://localhost:3001"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-API-Key"]
        },
        r"/docs/*": {
            "origins": ["http://localhost:3000", "http://localhost:8080", "http://localhost:3001"],
            "methods": ["GET"],
            "allow_headers": ["Content-Type"]
        }
    })
    
    # Setup logging
    setup_logging(app, config)
    # Initialize database tables
    initialize_database()
    
    # Optional inbound API-key auth. When SERVICE_API_KEY is set, every /api/*
    # call except health/docs must send "X-API-Key: <key>". Off when unset
    # (local development). Put the service behind a gateway in production.
    service_api_key = os.environ.get('SERVICE_API_KEY', '')
    open_paths = ('/api/health', '/api/swagger.json')

    @app.before_request
    def require_api_key():
        if not service_api_key or not request.path.startswith('/api/') or request.path in open_paths:
            return None
        if request.method == 'OPTIONS':
            return None
        supplied = request.headers.get('X-API-Key', '')
        if not hmac.compare_digest(supplied, service_api_key):
            return {"success": False, "message": "Missing or invalid X-API-Key header",
                    "error": "unauthorized"}, 401
        return None

    api = create_api()
    # Initialize Flask-RESTX API
    api.init_app(app)
    
    # Root route
    @app.route('/')
    def index():
        return {
            "service": config.APP_TITLE,
            "version": config.APP_VERSION,
            "documentation": config.API_DOCS_PATH,
            "health": "/health",
            "endpoints": {
                "validate_credentials": "POST /api/scan/validate-credentials",
                "start_scan": "POST /api/scan/start",
                "scan_status": "GET /api/scan/{scan_id}/status",
                "pause_scan": "POST /api/scan/{scan_id}/pause",
                "resume_scan": "POST /api/scan/{scan_id}/resume",
                "cancel_scan": "POST /api/scan/{scan_id}/cancel",
                "list_scans": "GET /api/scan/list",
                "result_tables": "GET /api/results/{scan_id}/tables",
                "results": "GET /api/results/{scan_id}/result",
                "pipeline_info": "GET /api/pipeline/info",
                "cleanup": "POST /api/maintenance/cleanup"
            }
        }

    # Lightweight liveness/readiness probe at the root (the Flask-RESTX
    # /api/health endpoint also reports DLT pipeline details).
    @app.route('/health', endpoint='root_health')
    def root_health():
        db = check_database_health()
        db_ok = bool(db.get('healthy'))
        body = {
            "status": "healthy" if db_ok else "unhealthy",
            "service": "hubspot_deals",
            "version": config.APP_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {"database": "healthy" if db_ok else "unhealthy"},
        }
        return body, (200 if db_ok else 503)

    return app


def setup_logging(app: Flask, config):
    """Setup application logging"""
    
    # Configure basic logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT
    )
    
    # Setup Loki logging if enabled - ONLY ONCE
    if config.LOKI_ENABLED and not hasattr(app, '_loki_configured'):
        try:
            configure_app_logging(app)
            app._loki_configured = True  # Mark as configured
            app.logger.info("Loki logging enabled")
        except Exception as e:
            app.logger.warning(f"Failed to setup Loki logging: {e}")


# Create app instance
app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(host=host, port=port, debug=debug)
