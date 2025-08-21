"""Project API endpoints."""

from flask import Blueprint, request, jsonify

from deployer.services.project_service_json import ProjectService, ProjectServiceError
from deployer.services.process_service import ProcessService, ProcessServiceError
from deployer.utils.validators import validate_github_url, validate_project_name

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/', methods=['GET'])
def get_projects():
    """Get all projects with current status."""
    try:
        project_service = ProjectService.get_instance()
        process_service = ProcessService.get_instance()
        
        projects = project_service.get_all_projects()
        running_projects = process_service.get_running_projects()
        
        # Update running status for each project
        projects_data = []
        for project in projects:
            project_dict = project.to_dict()
            project_dict['running'] = project.name in running_projects
            if project.name in running_projects:
                # Get recent logs for running projects
                logs = process_service.get_project_logs(project.name)
                project_dict['recent_logs'] = [log.to_dict() for log in logs[-50:]]  # Last 50 logs
            projects_data.append(project_dict)
        
        return jsonify(projects_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/', methods=['POST'])
def create_project():
    """Create new project from GitHub repository."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        github_url = data.get('github_url', '').strip()
        project_name = data.get('project_name', '').strip()
        
        if not github_url:
            return jsonify({'error': 'GitHub URL is required'}), 400
        
        if not validate_github_url(github_url):
            return jsonify({'error': 'Invalid GitHub URL'}), 400
        
        if project_name and not validate_project_name(project_name):
            return jsonify({'error': 'Invalid project name'}), 400
        
        project_service = ProjectService.get_instance()
        project = project_service.create_project(github_url, project_name)
        
        return jsonify(project.to_dict()), 201
    
    except ProjectServiceError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@projects_bp.route('/<project_name>', methods=['GET'])
def get_project(project_name):
    """Get specific project."""
    try:
        project_service = ProjectService.get_instance()
        project = project_service.get_project(project_name)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        return jsonify(project.to_dict())
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>', methods=['DELETE'])
def delete_project(project_name):
    """Delete project."""
    try:
        project_service = ProjectService.get_instance()
        process_service = ProcessService.get_instance()
        
        # Stop project if running
        if process_service.is_project_running(project_name):
            process_service.stop_project(project_name)
        
        success = project_service.delete_project(project_name)
        
        if success:
            return jsonify({'message': 'Project deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete project'}), 500
    
    except ProjectServiceError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/update', methods=['POST'])
def update_project(project_name):
    """Update project from Git repository."""
    try:
        project_service = ProjectService.get_instance()
        project = project_service.update_project(project_name)
        
        return jsonify(project.to_dict())
    
    except ProjectServiceError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/venv', methods=['POST'])
def create_venv(project_name):
    """Create virtual environment for project."""
    try:
        project_service = ProjectService.get_instance()
        success = project_service.create_virtual_environment(project_name)
        
        if success:
            return jsonify({'message': 'Virtual environment created successfully'})
        else:
            return jsonify({'error': 'Failed to create virtual environment'}), 500
    
    except ProjectServiceError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/venv', methods=['DELETE'])
def delete_venv(project_name):
    """Delete virtual environment for project."""
    try:
        project_service = ProjectService.get_instance()
        success = project_service.delete_virtual_environment(project_name)
        
        if success:
            return jsonify({'message': 'Virtual environment deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete virtual environment'}), 500
    
    except ProjectServiceError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/install', methods=['POST'])
def install_requirements(project_name):
    """Install requirements for project."""
    try:
        project_service = ProjectService.get_instance()
        success = project_service.install_requirements(project_name)
        
        if success:
            return jsonify({'message': 'Requirements installed successfully'})
        else:
            return jsonify({'error': 'Failed to install requirements'}), 500
    
    except ProjectServiceError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/start', methods=['POST'])
def start_project(project_name):
    """Start project execution."""
    try:
        project_service = ProjectService.get_instance()
        process_service = ProcessService.get_instance()
        
        project = project_service.get_project(project_name)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        success = process_service.start_project(project)
        
        if success:
            return jsonify({'message': 'Project started successfully'})
        else:
            return jsonify({'error': 'Failed to start project'}), 500
    
    except (ProjectServiceError, ProcessServiceError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/stop', methods=['POST'])
def stop_project(project_name):
    """Stop project execution."""
    try:
        process_service = ProcessService.get_instance()
        
        success = process_service.stop_project(project_name)
        
        if success:
            return jsonify({'message': 'Project stopped successfully'})
        else:
            return jsonify({'error': 'Failed to stop project'}), 500
    
    except ProcessServiceError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/logs', methods=['GET'])
def get_project_logs(project_name):
    """Get project logs with optional pagination."""
    try:
        process_service = ProcessService.get_instance()
        
        # Get pagination parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Limit maximum logs per request
        limit = min(limit, 200)
        
        logs = process_service.get_project_logs(project_name)
        
        # Apply pagination
        total_logs = len(logs)
        paginated_logs = logs[offset:offset + limit] if logs else []
        
        return jsonify({
            'logs': [log.to_dict() for log in paginated_logs],
            'total': total_logs,
            'offset': offset,
            'limit': limit,
            'has_more': offset + limit < total_logs
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/files', methods=['GET'])
def get_project_files(project_name):
    """Get project file structure."""
    try:
        project_service = ProjectService.get_instance()
        file_data = project_service.get_project_files(project_name)
        
        return jsonify(file_data)
    
    except ProjectServiceError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/config', methods=['GET'])
def get_project_config(project_name):
    """Get project configuration."""
    try:
        project_service = ProjectService.get_instance()
        project = project_service.get_project(project_name)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        return jsonify(project.config.to_dict())
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/config', methods=['PUT'])
def update_project_config(project_name):
    """Update project configuration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        project_service = ProjectService.get_instance()
        project = project_service.get_project(project_name)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Update configuration
        for key, value in data.items():
            if hasattr(project.config, key):
                setattr(project.config, key, value)
        
        # Save configuration
        project.save_config()
        
        return jsonify({
            'message': 'Configuration updated successfully',
            'config': project.config.to_dict()
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_name>/logs/realtime', methods=['GET'])
def get_realtime_logs(project_name):
    """Get logs for real-time display based on project configuration."""
    try:
        project_service = ProjectService.get_instance()
        process_service = ProcessService.get_instance()
        
        project = project_service.get_project(project_name)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check if project is running and real-time logs are enabled
        if not process_service.is_project_running(project_name):
            return jsonify({
                'logs': [],
                'realtime_enabled': project.config.realtime_logs,
                'poll_interval': project.config.logs_poll_interval,
                'running': False
            })
        
        # Get logs with project-specific limit
        logs = process_service.get_project_logs(project_name)
        max_logs = project.config.max_logs_display
        recent_logs = logs[-max_logs:] if logs else []
        
        return jsonify({
            'logs': [log.to_dict() for log in recent_logs],
            'realtime_enabled': project.config.realtime_logs,
            'poll_interval': project.config.logs_poll_interval,
            'running': True,
            'total_logs': len(logs)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500