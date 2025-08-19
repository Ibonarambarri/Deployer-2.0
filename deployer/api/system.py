"""System API endpoints."""

from flask import Blueprint, jsonify

from deployer.services.process_service import ProcessService
from deployer.auth.decorators import permission_required, audit_action, admin_required
from deployer.auth.models import PermissionEnum

system_bp = Blueprint('system', __name__)


@system_bp.route('/stats', methods=['GET'])
@permission_required(PermissionEnum.SYSTEM_MONITOR)
@audit_action('view_system_stats', 'system')
def get_system_stats():
    """Get system statistics."""
    try:
        process_service = ProcessService.get_instance()
        stats = process_service.get_system_stats()
        
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@system_bp.route('/running', methods=['GET'])
@permission_required(PermissionEnum.SYSTEM_MONITOR)
@audit_action('view_running_projects', 'system')
def get_running_projects():
    """Get list of currently running projects."""
    try:
        process_service = ProcessService.get_instance()
        running_projects = process_service.get_running_projects()
        
        return jsonify({'running_projects': running_projects})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@system_bp.route('/cleanup', methods=['POST'])
@admin_required
@audit_action('system_cleanup', 'system')
def cleanup_finished():
    """Clean up finished processes."""
    try:
        process_service = ProcessService.get_instance()
        process_service.cleanup_finished_processes()
        
        return jsonify({'message': 'Cleanup completed successfully'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500