"""JSON-based project models."""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class Project:
    """Project model using JSON storage."""
    
    name: str
    path: str
    github_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    running: bool = False
    pid: Optional[int] = None
    started_at: Optional[str] = None
    
    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()
    
    @property
    def project_path(self) -> Path:
        """Get project path as Path object."""
        return Path(self.path)
    
    @property
    def is_git(self) -> bool:
        """Check if project is a git repository."""
        return (self.project_path / '.git').exists()
    
    @property
    def has_init(self) -> bool:
        """Check if project has __init__.py file."""
        return (self.project_path / '__init__.py').exists()
    
    @property
    def has_venv(self) -> bool:
        """Check if project has virtual environment."""
        venv_paths = [
            self.project_path / 'venv',
            self.project_path / '.venv',
            self.project_path / 'env'
        ]
        return any(venv_path.exists() and venv_path.is_dir() for venv_path in venv_paths)
    
    @property
    def has_requirements(self) -> bool:
        """Check if project has requirements.txt."""
        requirements_files = [
            self.project_path / 'requirements.txt',
            self.project_path / 'requirements.in',
            self.project_path / 'pyproject.toml'
        ]
        return any(req_file.exists() for req_file in requirements_files)
    
    def get_venv_python(self) -> Optional[str]:
        """Get path to virtual environment Python executable."""
        if not self.has_venv:
            return None
        
        venv_paths = [
            self.project_path / 'venv',
            self.project_path / '.venv', 
            self.project_path / 'env'
        ]
        
        for venv_path in venv_paths:
            if venv_path.exists():
                python_paths = [
                    venv_path / 'bin' / 'python',
                    venv_path / 'bin' / 'python3',
                    venv_path / 'Scripts' / 'python.exe',  # Windows
                    venv_path / 'Scripts' / 'python3.exe'  # Windows
                ]
                
                for python_path in python_paths:
                    if python_path.exists():
                        return str(python_path)
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary."""
        data = asdict(self)
        # Add computed properties
        data.update({
            'is_git': self.is_git,
            'has_init': self.has_init,
            'has_venv': self.has_venv,
            'has_requirements': self.has_requirements
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create project from dictionary."""
        # Filter out computed properties
        project_data = {k: v for k, v in data.items() 
                       if k in ['name', 'path', 'github_url', 'created_at', 
                               'updated_at', 'running', 'pid', 'started_at']}
        return cls(**project_data)
    
    def update_status(self, running: bool, pid: Optional[int] = None, 
                     started_at: Optional[str] = None):
        """Update project running status."""
        self.running = running
        self.pid = pid
        self.started_at = started_at
        self.updated_at = datetime.now().isoformat()


@dataclass
class LogEntry:
    """Log entry model."""
    
    id: str
    timestamp: str
    message: str
    level: str
    source: str = 'system'
    project_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogEntry':
        """Create log entry from dictionary."""
        return cls(**data)
    
    @classmethod
    def create(cls, message: str, level: str = 'INFO', source: str = 'system',
               project_name: Optional[str] = None) -> 'LogEntry':
        """Create a new log entry with auto-generated ID and timestamp."""
        timestamp = datetime.now().isoformat()
        log_id = f"{project_name or 'system'}_{int(datetime.now().timestamp() * 1000)}"
        
        return cls(
            id=log_id,
            timestamp=timestamp,
            message=message,
            level=level.upper(),
            source=source,
            project_name=project_name
        )