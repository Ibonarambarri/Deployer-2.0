"""Project management service."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

import git

from deployer.models.project import Project
from deployer.utils.validators import (
    validate_github_url, validate_project_name, validate_project_path
)
from deployer.utils.security import SecurityContext, secure_path_join


class ProjectServiceError(Exception):
    """Project service specific error."""
    pass


class ProjectService:
    """Service for managing projects."""
    
    _instance: Optional['ProjectService'] = None
    
    def __init__(self, vault_path: Path, security_context: SecurityContext):
        self.vault_path = vault_path
        self.security = security_context
        self._projects_cache: Dict[str, Project] = {}
    
    @classmethod
    def initialize(cls, vault_path: Path, security_context: SecurityContext) -> None:
        """Initialize the project service."""
        if cls._instance is None:
            cls._instance = cls(vault_path, security_context)
    
    @classmethod
    def get_instance(cls) -> 'ProjectService':
        """Get the singleton instance."""
        if cls._instance is None:
            raise ProjectServiceError("ProjectService not initialized")
        return cls._instance
    
    def get_all_projects(self) -> List[Project]:
        """
        Get all projects from vault directory.
        
        Returns:
            List of Project instances
        """
        projects = []
        
        if not self.vault_path.exists():
            return projects
        
        try:
            for item_path in self.vault_path.iterdir():
                if item_path.is_dir() and not item_path.name.startswith('.'):
                    try:
                        project = Project.from_directory(item_path)
                        if project.is_valid():
                            projects.append(project)
                            self._projects_cache[project.name] = project
                    except Exception as e:
                        # Log error but continue with other projects
                        print(f"Error loading project {item_path.name}: {e}")
                        continue
        
        except Exception as e:
            raise ProjectServiceError(f"Error scanning vault directory: {e}")
        
        return sorted(projects, key=lambda p: p.name)
    
    def get_project(self, name: str) -> Optional[Project]:
        """
        Get project by name.
        
        Args:
            name: Project name
            
        Returns:
            Project instance or None if not found
        """
        # Check cache first
        if name in self._projects_cache:
            project = self._projects_cache[name]
            project.refresh_status()
            return project
        
        # Load from filesystem
        project_path = secure_path_join(self.vault_path, name)
        if not project_path or not project_path.exists():
            return None
        
        try:
            project = Project.from_directory(project_path)
            if project.is_valid():
                self._projects_cache[name] = project
                return project
        except Exception:
            pass
        
        return None
    
    def create_project(self, github_url: str, project_name: Optional[str] = None) -> Project:
        """
        Create new project by cloning from GitHub.
        
        Args:
            github_url: GitHub repository URL
            project_name: Optional custom project name
            
        Returns:
            Created Project instance
            
        Raises:
            ProjectServiceError: If creation fails
        """
        # Validate GitHub URL
        if not validate_github_url(github_url):
            raise ProjectServiceError("Invalid GitHub URL")
        
        # Determine project name
        if project_name:
            try:
                project_name = validate_project_name(project_name)
            except ValueError as e:
                raise ProjectServiceError(str(e))
        else:
            # Extract from URL
            project_name = github_url.split('/')[-1].replace('.git', '')
            try:
                project_name = validate_project_name(project_name)
            except ValueError:
                raise ProjectServiceError("Could not determine valid project name from URL")
        
        # Check if project already exists
        if self.get_project(project_name):
            raise ProjectServiceError(f"Project '{project_name}' already exists")
        
        # Create project path
        project_path = secure_path_join(self.vault_path, project_name)
        if not project_path:
            raise ProjectServiceError("Invalid project path")
        
        if project_path.exists():
            raise ProjectServiceError(f"Directory '{project_name}' already exists")
        
        # Clone repository
        try:
            git.Repo.clone_from(github_url, project_path)
        except Exception as e:
            # Cleanup on failure
            if project_path.exists():
                shutil.rmtree(project_path, ignore_errors=True)
            raise ProjectServiceError(f"Failed to clone repository: {e}")
        
        # Create project instance
        try:
            project = Project.from_directory(project_path)
            self._projects_cache[project.name] = project
            return project
        except Exception as e:
            # Cleanup on failure
            if project_path.exists():
                shutil.rmtree(project_path, ignore_errors=True)
            raise ProjectServiceError(f"Failed to create project: {e}")
    
    def delete_project(self, name: str) -> bool:
        """
        Delete project and its directory.
        
        Args:
            name: Project name
            
        Returns:
            True if deleted successfully
            
        Raises:
            ProjectServiceError: If deletion fails
        """
        project = self.get_project(name)
        if not project:
            raise ProjectServiceError(f"Project '{name}' not found")
        
        # Only allow deletion of Git repositories
        if not project.is_git:
            raise ProjectServiceError("Only Git repositories can be deleted")
        
        # Security check
        if not self.security.is_safe_path(project.path):
            raise ProjectServiceError("Project path is not safe for deletion")
        
        try:
            shutil.rmtree(project.path)
            # Remove from cache
            self._projects_cache.pop(name, None)
            return True
        except Exception as e:
            raise ProjectServiceError(f"Failed to delete project: {e}")
    
    def update_project(self, name: str) -> Project:
        """
        Update project from Git repository.
        
        Args:
            name: Project name
            
        Returns:
            Updated Project instance
            
        Raises:
            ProjectServiceError: If update fails
        """
        project = self.get_project(name)
        if not project:
            raise ProjectServiceError(f"Project '{name}' not found")
        
        if not project.is_git:
            raise ProjectServiceError("Project is not a Git repository")
        
        try:
            repo = git.Repo(project.path)
            origin = repo.remotes.origin
            origin.pull()
            
            # Refresh project status
            project.refresh_status()
            return project
        
        except Exception as e:
            raise ProjectServiceError(f"Failed to update project: {e}")
    
    def create_virtual_environment(self, name: str) -> bool:
        """
        Create virtual environment for project.
        
        Args:
            name: Project name
            
        Returns:
            True if created successfully
            
        Raises:
            ProjectServiceError: If creation fails
        """
        project = self.get_project(name)
        if not project:
            raise ProjectServiceError(f"Project '{name}' not found")
        
        if project.has_venv:
            raise ProjectServiceError("Virtual environment already exists")
        
        venv_path = project.get_venv_path()
        
        try:
            # Create virtual environment
            result = subprocess.run(
                ['python3', '-m', 'venv', 'venv'],
                cwd=project.path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise ProjectServiceError(f"Failed to create virtual environment: {result.stderr}")
            
            # Update project status
            project.refresh_status()
            return True
        
        except subprocess.TimeoutExpired:
            raise ProjectServiceError("Virtual environment creation timed out")
        except Exception as e:
            # Cleanup on failure
            if venv_path.exists():
                shutil.rmtree(venv_path, ignore_errors=True)
            raise ProjectServiceError(f"Failed to create virtual environment: {e}")
    
    def delete_virtual_environment(self, name: str) -> bool:
        """
        Delete virtual environment for project.
        
        Args:
            name: Project name
            
        Returns:
            True if deleted successfully
            
        Raises:
            ProjectServiceError: If deletion fails
        """
        project = self.get_project(name)
        if not project:
            raise ProjectServiceError(f"Project '{name}' not found")
        
        if not project.has_venv:
            raise ProjectServiceError("Virtual environment does not exist")
        
        venv_path = project.get_venv_path()
        
        try:
            shutil.rmtree(venv_path)
            project.refresh_status()
            return True
        except Exception as e:
            raise ProjectServiceError(f"Failed to delete virtual environment: {e}")
    
    def install_requirements(self, name: str) -> bool:
        """
        Install requirements for project.
        
        Args:
            name: Project name
            
        Returns:
            True if installed successfully
            
        Raises:
            ProjectServiceError: If installation fails
        """
        project = self.get_project(name)
        if not project:
            raise ProjectServiceError(f"Project '{name}' not found")
        
        if not project.has_venv:
            raise ProjectServiceError("Virtual environment must be created first")
        
        if not project.has_requirements:
            raise ProjectServiceError("requirements.txt not found")
        
        python_path = project.get_venv_python()
        
        try:
            result = subprocess.run(
                [str(python_path), '-m', 'pip', 'install', '-r', 'requirements.txt'],
                cwd=project.path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise ProjectServiceError(f"Failed to install requirements: {result.stderr}")
            
            return True
        
        except subprocess.TimeoutExpired:
            raise ProjectServiceError("Requirements installation timed out")
        except Exception as e:
            raise ProjectServiceError(f"Failed to install requirements: {e}")
    
    def get_project_files(self, name: str) -> Dict[str, Any]:
        """
        Get file structure for project.
        
        Args:
            name: Project name
            
        Returns:
            Dictionary with file structure and stats
            
        Raises:
            ProjectServiceError: If analysis fails
        """
        project = self.get_project(name)
        if not project:
            raise ProjectServiceError(f"Project '{name}' not found")
        
        try:
            file_tree = self._analyze_directory(project.path)
            stats = self._calculate_stats(file_tree)
            
            return {
                'files': file_tree,
                'stats': {
                    'total_files': stats['files'],
                    'total_size': stats['size'],
                    'issues_count': stats['issues'],
                    'project_name': name
                }
            }
        
        except Exception as e:
            raise ProjectServiceError(f"Failed to analyze project files: {e}")
    
    def _analyze_directory(self, path: Path, relative_path: str = "") -> List[Dict[str, Any]]:
        """Analyze directory structure recursively."""
        items = []
        
        try:
            for item in sorted(path.iterdir()):
                # Skip hidden files except git files
                if item.name.startswith('.') and item.name not in {'.git', '.gitignore'}:
                    continue
                
                relative_item_path = f"{relative_path}/{item.name}" if relative_path else item.name
                
                if item.is_dir():
                    children = self._analyze_directory(item, relative_item_path)
                    items.append({
                        'name': item.name,
                        'type': 'directory',
                        'path': relative_item_path,
                        'children': children,
                        'size': len(children)
                    })
                else:
                    file_info = self._analyze_file(item, relative_item_path)
                    items.append(file_info)
        
        except PermissionError:
            return [{'name': 'Error', 'type': 'error', 'message': 'Permission denied'}]
        except Exception as e:
            return [{'name': 'Error', 'type': 'error', 'message': str(e)}]
        
        return items
    
    def _analyze_file(self, file_path: Path, relative_path: str) -> Dict[str, Any]:
        """Analyze individual file."""
        try:
            file_size = file_path.stat().st_size
            file_ext = file_path.suffix.lower()
            
            file_info = {
                'name': file_path.name,
                'type': 'file',
                'path': relative_path,
                'size': file_size,
                'extension': file_ext,
                'issues': []
            }
            
            # Check for issues
            if file_size == 0:
                file_info['issues'].append("Empty file")
            elif file_size > 10 * 1024 * 1024:  # 10MB
                file_info['issues'].append("Large file (>10MB)")
            
            # Python file specific checks
            if file_ext == '.py':
                try:
                    content = file_path.read_text(encoding='utf-8')
                    if len(content.strip()) > 0:
                        if not any(keyword in content for keyword in ['import', 'def', 'class']):
                            file_info['issues'].append("Python file without imports/functions/classes")
                except Exception:
                    file_info['issues'].append("Could not read file content")
            
            return file_info
        
        except Exception as e:
            return {
                'name': file_path.name,
                'type': 'file',
                'path': relative_path,
                'size': 0,
                'extension': file_path.suffix.lower() if file_path.suffix else '',
                'issues': [f"Error analyzing file: {e}"]
            }
    
    def _calculate_stats(self, file_tree: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate statistics from file tree."""
        stats = {'files': 0, 'size': 0, 'issues': 0}
        
        def count_recursive(items):
            for item in items:
                if item['type'] == 'file':
                    stats['files'] += 1
                    stats['size'] += item.get('size', 0)
                    stats['issues'] += len(item.get('issues', []))
                elif item['type'] == 'directory':
                    count_recursive(item.get('children', []))
        
        count_recursive(file_tree)
        return stats