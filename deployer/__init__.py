"""Deployer application factory."""

import logging
import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from config import config


def create_app(config_name=None):
    """Create and configure Flask application."""
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Ensure vault directory exists
    Path(app.config['VAULT_PATH']).mkdir(exist_ok=True)
    
    # Configure logging
    configure_logging(app)
    
    # Initialize extensions
    CORS(app, resources={
        r"/api/*": {"origins": app.config['CORS_ORIGINS']},
        r"/*": {"origins": app.config['CORS_ORIGINS']}
    })
    
    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins=app.config['CORS_ORIGINS'])
    app.socketio = socketio
    
    # Register blueprints
    register_blueprints(app)
    
    # Register WebSocket events
    register_socketio_events(socketio)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Initialize JSON storage
    initialize_json_storage(app)
    
    # Initialize services
    from deployer.services.process_service import ProcessService
    from deployer.services.project_service_json import ProjectService
    from deployer.utils.security import SecurityContext
    
    vault_path = Path(app.config['VAULT_PATH'])
    security_context = SecurityContext(vault_path)
    
    ProcessService.initialize(app.config)
    ProjectService.initialize(vault_path, security_context)
    
    # Start background log monitoring
    start_background_tasks(socketio)
    
    return app


def start_background_tasks(socketio):
    """Start background tasks for log monitoring."""
    import threading
    import time
    
    def log_monitoring_task():
        """Background task to check for new logs."""
        from deployer.services.log_service import LogService
        
        while True:
            try:
                LogService.check_for_new_logs()
            except Exception as e:
                print(f"Error in log monitoring: {e}")
            time.sleep(1)  # Check every second
    
    # Start the background thread
    log_thread = threading.Thread(target=log_monitoring_task, daemon=True)
    log_thread.start()


def configure_logging(app):
    """Configure application logging."""
    
    if not app.debug and not app.testing:
        # Production logging
        log_level = getattr(logging, app.config['LOG_LEVEL'].upper())
        
        # File handler
        file_handler = logging.FileHandler(app.config['LOG_FILE'])
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        app.logger.addHandler(file_handler)
        app.logger.setLevel(log_level)
        app.logger.info('Deployer application startup')


def register_blueprints(app):
    """Register application blueprints."""
    
    from deployer.api.projects import projects_bp
    from deployer.api.system import system_bp
    from deployer.views.main import main_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(projects_bp, url_prefix='/api/projects')
    app.register_blueprint(system_bp, url_prefix='/api/system')


def register_socketio_events(socketio):
    """Register WebSocket event handlers."""
    from deployer.websocket.events import register_events
    register_events(socketio)


def register_error_handlers(app):
    """Register error handlers."""
    
    @app.errorhandler(400)
    def bad_request(error):
        return {'error': 'Bad request'}, 400
    
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Resource not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Server Error: {error}')
        return {'error': 'Internal server error'}, 500


def initialize_json_storage(app):
    """Initialize JSON-based storage system."""
    from deployer.storage.json_storage import initialize_storage
    
    # Use configured storage path or default to vault/data
    storage_path = Path(app.config.get('STORAGE_PATH', app.config['VAULT_PATH'] / 'data'))
    
    # Initialize JSON storage
    initialize_storage(str(storage_path))
    
    app.logger.info(f"JSON storage initialized at: {storage_path}")




