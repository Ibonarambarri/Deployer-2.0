"""WebSocket event handlers for real-time project logs."""

import logging
from flask_socketio import emit, join_room, leave_room, disconnect
from flask import request

logger = logging.getLogger(__name__)

# Store active connections per project
active_connections = {}


def register_events(socketio):
    """Register all WebSocket event handlers."""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info(f"Client connected: {request.sid}")
        emit('connected', {'status': 'connected'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        logger.info(f"Client disconnected: {request.sid}")
        
        # Remove from all project rooms
        for project_name in list(active_connections.keys()):
            if request.sid in active_connections[project_name]:
                active_connections[project_name].remove(request.sid)
                if not active_connections[project_name]:
                    del active_connections[project_name]
    
    @socketio.on('join_project_logs')
    def handle_join_project_logs(data):
        """Handle joining a project's log room."""
        project_name = data.get('project_name')
        
        if not project_name:
            emit('error', {'message': 'Project name is required'})
            return
        
        # Join the room for this project
        room = f"project_{project_name}_logs"
        join_room(room)
        
        # Track active connections
        if project_name not in active_connections:
            active_connections[project_name] = []
        
        if request.sid not in active_connections[project_name]:
            active_connections[project_name].append(request.sid)
        
        logger.info(f"Client {request.sid} joined logs for project: {project_name}")
        emit('joined_project', {'project_name': project_name, 'room': room})
        
        # Send recent logs if available
        from deployer.services.log_service import LogService
        try:
            recent_logs = LogService.get_recent_logs(project_name, limit=100)
            if recent_logs:
                emit('recent_logs', {'logs': recent_logs})
        except Exception as e:
            logger.error(f"Error getting recent logs for {project_name}: {e}")
    
    @socketio.on('leave_project_logs')
    def handle_leave_project_logs(data):
        """Handle leaving a project's log room."""
        project_name = data.get('project_name')
        
        if not project_name:
            emit('error', {'message': 'Project name is required'})
            return
        
        # Leave the room
        room = f"project_{project_name}_logs"
        leave_room(room)
        
        # Remove from active connections
        if project_name in active_connections and request.sid in active_connections[project_name]:
            active_connections[project_name].remove(request.sid)
            if not active_connections[project_name]:
                del active_connections[project_name]
        
        logger.info(f"Client {request.sid} left logs for project: {project_name}")
        emit('left_project', {'project_name': project_name})


def broadcast_log_message(project_name, log_data):
    """Broadcast a log message to all clients watching this project."""
    from flask import current_app
    
    if hasattr(current_app, 'socketio'):
        room = f"project_{project_name}_logs"
        current_app.socketio.emit('new_log', {
            'project_name': project_name,
            'log': log_data
        }, room=room)


def broadcast_project_status(project_name, status_data):
    """Broadcast project status change to all clients watching this project."""
    from flask import current_app
    
    if hasattr(current_app, 'socketio'):
        room = f"project_{project_name}_logs"
        current_app.socketio.emit('project_status', {
            'project_name': project_name,
            'status': status_data
        }, room=room)


def get_active_connections():
    """Get count of active connections per project."""
    return {project: len(sids) for project, sids in active_connections.items()}