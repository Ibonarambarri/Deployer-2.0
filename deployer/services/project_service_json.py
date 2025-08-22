"""JSON-based project service."""

import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from deployer.models.project_json import Project
from deployer.storage.json_storage import get_project_storage, get_log_storage
from deployer.utils.security import SecurityContext

logger = logging.getLogger(__name__)


class ProjectServiceError(Exception):
    """Project service specific error."""
    pass


class ProjectService:
    """Service for managing projects using JSON storage."""
    
    _instance: Optional['ProjectService'] = None
    _vault_path: Optional[Path] = None
    _security_context: Optional[SecurityContext] = None
    _projects_cache: List[Project] = []
    _cache_timestamp: Optional[float] = None
    _cache_ttl: int = 30  # Cache TTL in seconds
    
    def __init__(self):
        if self._vault_path is None:
            raise ProjectServiceError("ProjectService not initialized")
        
        self.vault_path = self._vault_path
        self.security_context = self._security_context
        self.project_storage = get_project_storage()
        self.log_storage = get_log_storage()
    
    @classmethod
    def initialize(cls, vault_path: Path, security_context: SecurityContext) -> None:
        """Initialize the project service."""
        cls._vault_path = vault_path
        cls._security_context = security_context
        if cls._instance is None:
            cls._instance = cls()
    
    @classmethod
    def get_instance(cls) -> 'ProjectService':
        """Get the singleton instance."""
        if cls._instance is None:
            raise ProjectServiceError("ProjectService not initialized")
        return cls._instance
    
    def _invalidate_cache(self) -> None:
        """Invalidate the projects cache."""
        self._projects_cache.clear()
        self._cache_timestamp = None
    
    def get_all_projects(self) -> List[Project]:
        """Get all projects by scanning vault directory with caching."""
        try:
            # Check if cache is valid
            current_time = time.time()
            if (self._cache_timestamp and 
                current_time - self._cache_timestamp < self._cache_ttl and 
                self._projects_cache):
                return self._projects_cache.copy()
            
            projects = []
            
            # Scan vault directory for project folders
            if not self.vault_path.exists():
                return projects
            
            for item in self.vault_path.iterdir():
                # Skip data directory and files
                if item.name == 'data' or item.is_file():
                    continue
                    
                if item.is_dir():
                    try:
                        project = self._create_project_from_directory(item)
                        if project:
                            projects.append(project)
                    except Exception as e:
                        logger.warning(f"Could not load project from {item.name}: {e}")
                        continue
            
            # Update cache
            self._projects_cache = projects.copy()
            self._cache_timestamp = current_time
            
            return projects
        except Exception as e:
            logger.error(f"Error getting projects: {e}")
            return []
    
    def get_project(self, project_name: str) -> Optional[Project]:
        """Get a specific project by scanning vault directory."""
        try:
            project_path = self.vault_path / project_name
            if project_path.exists() and project_path.is_dir():
                return self._create_project_from_directory(project_path)
            return None
        except Exception as e:
            logger.error(f"Error getting project {project_name}: {e}")
            return None
    
    def _create_project_from_directory(self, project_path: Path) -> Optional[Project]:
        """Create a Project object from a directory."""
        try:
            project_name = project_path.name
            
            # Only try to get GitHub URL if really needed and cache it
            github_url = "unknown"
            if (project_path / '.git').exists():
                # For performance, we could cache this or load it lazily
                # For now, we'll keep it simple but add timeout and error handling
                try:
                    result = subprocess.run(
                        ['git', 'config', '--get', 'remote.origin.url'],
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=5  # Add timeout to prevent hanging
                    )
                    if result.returncode == 0:
                        github_url = result.stdout.strip()
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception):
                    # Don't fail the whole operation if git command fails
                    github_url = "git-repository"
            
            # Create project object
            project = Project(
                name=project_name,
                path=str(project_path),
                github_url=github_url
            )
            
            return project
            
        except Exception as e:
            logger.error(f"Error creating project from directory {project_path}: {e}")
            return None
    
    def create_project(self, github_url: str, project_name: Optional[str] = None) -> Project:
        """Create a new project from GitHub URL."""
        try:
            # Validate repository URL
            from deployer.utils.validators import validate_github_url
            if not validate_github_url(github_url):
                raise ProjectServiceError("Invalid repository URL")
            
            # Extract project name from URL if not provided
            if not project_name:
                project_name = github_url.split('/')[-1]
                if project_name.endswith('.git'):
                    project_name = project_name[:-4]
            
            # Validate project name
            if not project_name or not project_name.strip():
                raise ProjectServiceError("Project name is required")
            
            project_name = project_name.strip()
            original_project_name = project_name
            
            # Create project directory
            project_path = self.vault_path / project_name
            
            if project_path.exists():
                # If directory exists but project is not registered, offer to import it
                if project_path.is_dir() and (project_path / '.git').exists():
                    # This looks like an existing git repository
                    logger.info(f"Found existing repository at {project_path}, importing it")
                    # Don't clone, just register the existing project
                else:
                    # Generate a unique name
                    counter = 1
                    original_name = project_name
                    while project_path.exists():
                        project_name = f"{original_name}-{counter}"
                        project_path = self.vault_path / project_name
                        counter += 1
                    
                    logger.info(f"Directory '{original_name}' exists, using '{project_name}' instead")
                    # Clone repository with new name
                    self._clone_repository(github_url, project_path)
            else:
                # Clone repository normally
                self._clone_repository(github_url, project_path)
            
            # Create project object
            project = Project(
                name=project_name,
                path=str(project_path),
                github_url=github_url
            )
            
            # Add creation log
            self.log_storage.add_log_entry(
                project_name,
                f"Project created from {github_url}",
                'INFO',
                'project_service'
            )
            
            logger.info(f"Project '{project_name}' created successfully")
            
            # Invalidate cache since we added a new project
            self._invalidate_cache()
            
            return project
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git clone failed: {e}")
            raise ProjectServiceError(f"Failed to clone repository: {e}")
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            raise ProjectServiceError(f"Failed to create project: {e}")
    
    def delete_project(self, project_name: str) -> bool:
        """Delete a project."""
        try:
            project_path = self.vault_path / project_name
            if not project_path.exists():
                raise ProjectServiceError(f"Project '{project_name}' not found")
            
            # Stop project if running
            from deployer.services.process_service import ProcessService
            try:
                process_service = ProcessService.get_instance()
                if process_service.is_project_running(project_name):
                    process_service.stop_project(project_name)
            except Exception as e:
                logger.warning(f"Could not stop running project: {e}")
            
            # Remove project directory
            if project_path.exists():
                shutil.rmtree(project_path)
            
            # Remove logs
            self.log_storage.delete_project_logs(project_name)
            
            logger.info(f"Project '{project_name}' deleted successfully")
            
            # Invalidate cache since we deleted a project
            self._invalidate_cache()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting project {project_name}: {e}")
            return False
    
    def update_project_status(self, project_name: str, running: bool, 
                            pid: Optional[int] = None, started_at: Optional[str] = None) -> bool:
        """Update project running status (status is now managed by ProcessService)."""
        # Status is now managed in memory by ProcessService, no need to persist
        return True
    
    def create_venv(self, project_name: str) -> bool:
        """Create virtual environment for project."""
        try:
            project = self.get_project(project_name)
            if not project:
                raise ProjectServiceError(f"Project '{project_name}' not found")
            
            if project.has_venv:
                raise ProjectServiceError("Virtual environment already exists")
            
            project_path = Path(project.path)
            venv_path = project_path / 'venv'
            
            # Create virtual environment
            result = subprocess.run(
                ['python3', '-m', 'venv', str(venv_path)],
                cwd=project_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise ProjectServiceError(f"Failed to create venv: {result.stderr}")
            
            self.log_storage.add_log_entry(
                project_name,
                "Virtual environment created successfully",
                'INFO',
                'project_service'
            )
            
            logger.info(f"Virtual environment created for '{project_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error creating venv for {project_name}: {e}")
            self.log_storage.add_log_entry(
                project_name,
                f"Failed to create virtual environment: {e}",
                'ERROR',
                'project_service'
            )
            return False
    
    def delete_venv(self, project_name: str) -> bool:
        """Delete virtual environment for project."""
        try:
            project = self.get_project(project_name)
            if not project:
                raise ProjectServiceError(f"Project '{project_name}' not found")
            
            if not project.has_venv:
                raise ProjectServiceError("Virtual environment does not exist")
            
            project_path = Path(project.path)
            venv_paths = [
                project_path / 'venv',
                project_path / '.venv',
                project_path / 'env'
            ]
            
            for venv_path in venv_paths:
                if venv_path.exists():
                    shutil.rmtree(venv_path)
                    break
            
            self.log_storage.add_log_entry(
                project_name,
                "Virtual environment deleted",
                'INFO',
                'project_service'
            )
            
            logger.info(f"Virtual environment deleted for '{project_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting venv for {project_name}: {e}")
            return False
    
    def install_requirements(self, project_name: str) -> bool:
        """Install requirements for project."""
        try:
            project = self.get_project(project_name)
            if not project:
                raise ProjectServiceError(f"Project '{project_name}' not found")
            
            project_path = Path(project.path)
            requirements_files = [
                project_path / 'requirements.txt',
                project_path / 'requirements.in'
            ]
            
            requirements_file = None
            for req_file in requirements_files:
                if req_file.exists():
                    requirements_file = req_file
                    break
            
            if not requirements_file:
                raise ProjectServiceError("No requirements file found")
            
            # Determine Python executable
            python_executable = project.get_venv_python() or 'python3'
            
            # Install requirements
            result = subprocess.run(
                [python_executable, '-m', 'pip', 'install', '-r', str(requirements_file)],
                cwd=project_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise ProjectServiceError(f"Failed to install requirements: {result.stderr}")
            
            self.log_storage.add_log_entry(
                project_name,
                f"Requirements installed from {requirements_file.name}",
                'INFO',
                'project_service'
            )
            
            logger.info(f"Requirements installed for '{project_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error installing requirements for {project_name}: {e}")
            self.log_storage.add_log_entry(
                project_name,
                f"Failed to install requirements: {e}",
                'ERROR',
                'project_service'
            )
            return False
    
    def _clone_repository(self, github_url: str, target_path: Path) -> None:
        """Clone a repository (local or remote)."""
        try:
            # Create parent directory if it doesn't exist
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Handle local file paths
            if github_url.startswith('file://') or github_url.startswith('/'):
                local_path = github_url.replace('file://', '') if github_url.startswith('file://') else github_url
                source_path = Path(local_path)
                
                if not source_path.exists():
                    raise ProjectServiceError(f"Local path does not exist: {local_path}")
                
                if not (source_path / '.git').exists():
                    raise ProjectServiceError(f"Path is not a git repository: {local_path}")
                
                # Copy local repository
                shutil.copytree(source_path, target_path)
                logger.info(f"Copied local repository from {source_path} to {target_path}")
                return
            
            # Clone remote repository
            result = subprocess.run(
                ['git', 'clone', github_url, str(target_path)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                if target_path.exists():
                    shutil.rmtree(target_path)
                raise subprocess.CalledProcessError(result.returncode, 'git clone', result.stderr)
            
            logger.info(f"Successfully cloned {github_url} to {target_path}")
            
        except subprocess.TimeoutExpired:
            if target_path.exists():
                shutil.rmtree(target_path)
            raise ProjectServiceError("Git clone timed out")
        except FileNotFoundError:
            raise ProjectServiceError("Git is not installed or not in PATH")
        except Exception as e:
            if target_path.exists():
                shutil.rmtree(target_path)
            raise ProjectServiceError(f"Failed to clone repository: {e}")
    
    def get_project_stats(self) -> Dict[str, Any]:
        """Get project statistics."""
        try:
            projects = self.get_all_projects()
            running_count = sum(1 for p in projects if p.running)
            
            return {
                'total_projects': len(projects),
                'running_projects': running_count,
                'stopped_projects': len(projects) - running_count,
                'projects_with_venv': sum(1 for p in projects if p.has_venv),
                'git_projects': sum(1 for p in projects if p.is_git)
            }
        except Exception as e:
            logger.error(f"Error getting project stats: {e}")
            return {}