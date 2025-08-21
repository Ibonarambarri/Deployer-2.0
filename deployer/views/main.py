"""Main view routes."""

from flask import Blueprint, send_from_directory, current_app
import os

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/<path:path>')
def serve_react_app(path=''):
    """Serve the React SPA."""
    dist_path = os.path.join(current_app.static_folder, 'dist')
    
    # If it's an API route, don't serve React app
    if path.startswith('api/'):
        return {'error': 'Not found'}, 404
    
    # If it's a static file request, serve the file
    if path and os.path.exists(os.path.join(dist_path, path)):
        return send_from_directory(dist_path, path)
    
    # Otherwise, serve the main React index.html
    return send_from_directory(dist_path, 'index.html')


@main_bp.route('/api/health')
def health_check():
    """Health check endpoint."""
    return {'status': 'ok', 'message': 'Deployer API is running'}


@main_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors - serve React app for client-side routing."""
    dist_path = os.path.join(current_app.static_folder, 'dist')
    return send_from_directory(dist_path, 'index.html')


@main_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return {'error': 'Internal server error'}, 500