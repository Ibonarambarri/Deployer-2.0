"""Main view routes."""

import os
from pathlib import Path
from flask import Blueprint, send_from_directory, current_app

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Serve the React frontend."""
    frontend_path = Path(current_app.root_path) / 'static' / 'dist'
    return send_from_directory(frontend_path, 'index.html')


@main_bp.route('/<path:path>')
def serve_static(path):
    """Serve static files from React build."""
    frontend_path = Path(current_app.root_path) / 'static' / 'dist'
    if os.path.exists(os.path.join(frontend_path, path)):
        return send_from_directory(frontend_path, path)
    else:
        # For React Router, serve index.html for unknown routes
        return send_from_directory(frontend_path, 'index.html')


@main_bp.route('/api/health')
def health_check():
    """Health check endpoint."""
    return {'status': 'ok', 'message': 'Deployer API is running'}


@main_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return {'error': 'Resource not found'}, 404


@main_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return {'error': 'Internal server error'}, 500