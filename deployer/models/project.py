"""Project model and data structures."""

import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .project_config import ProjectConfig


@dataclass
class LogEntry:
    """Represents a single log entry."""
    timestamp: str
    message: str
    level: str = 'INFO'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogEntry':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class Project:
    """Represents a project in the deployer."""
    
    name: str
    path: Path
    is_git: bool = False
    has_init: bool = False
    has_venv: bool = False
    has_requirements: bool = False
    running: bool = False
    pid: Optional[int] = None
    started_at: Optional[str] = None
    recent_logs: List[LogEntry] = None
    config: ProjectConfig = None
    
    def __post_init__(self):
        """Initialize after creation."""
        if self.recent_logs is None:
            self.recent_logs = []
        
        if self.config is None:
            self.config = ProjectConfig()
        
        # Ensure path is Path object
        if isinstance(self.path, str):
            self.path = Path(self.path)
    
    @classmethod
    def from_directory(cls, project_path: Path) -> 'Project':
        """
        Create project instance from directory analysis.
        
        Args:
            project_path: Path to project directory
            
        Returns:
            Project instance
        """
        name = project_path.name
        
        # Check project characteristics
        is_git = (project_path / '.git').exists()
        has_init = (project_path / '__init__.py').exists()
        has_venv = cls._check_venv_exists(project_path)
        has_requirements = (project_path / 'requirements.txt').exists()
        
        # Load project configuration
        config = ProjectConfig.load_from_file(project_path / '.deployer_config.json')
        
        return cls(
            name=name,
            path=project_path,
            is_git=is_git,
            has_init=has_init,
            has_venv=has_venv,
            has_requirements=has_requirements,
            config=config
        )
    
    @staticmethod
    def _check_venv_exists(project_path: Path) -> bool:
        """Check if virtual environment exists."""
        venv_path = project_path / 'venv'
        return (
            venv_path.exists() and 
            venv_path.is_dir() and 
            (venv_path / 'bin' / 'python').exists()
        )
    
    def get_venv_path(self) -> Path:
        """Get virtual environment path."""
        return self.path / 'venv'
    
    def get_venv_python(self) -> Path:
        """Get virtual environment Python executable path."""
        return self.get_venv_path() / 'bin' / 'python'
    
    def refresh_status(self) -> None:
        """Refresh project status from filesystem."""
        self.is_git = (self.path / '.git').exists()
        self.has_init = (self.path / '__init__.py').exists()
        self.has_venv = self._check_venv_exists(self.path)
        self.has_requirements = (self.path / 'requirements.txt').exists()
    
    def add_log_entry(self, message: str, level: str = 'INFO') -> None:
        """Add a log entry to the project."""
        log_entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            message=message,
            level=level
        )
        self.recent_logs.append(log_entry)
        
        # Keep only recent logs to prevent memory issues
        if len(self.recent_logs) > 100:
            self.recent_logs = self.recent_logs[-50:]
    
    def clear_logs(self) -> None:
        """Clear all log entries."""
        self.recent_logs.clear()
    
    def save_config(self) -> None:
        """Save project configuration to file."""
        config_path = self.path / '.deployer_config.json'
        self.config.save_to_file(config_path)
    
    def reload_config(self) -> None:
        """Reload project configuration from file."""
        config_path = self.path / '.deployer_config.json'
        self.config = ProjectConfig.load_from_file(config_path)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for JSON serialization."""
        data = asdict(self)
        data['path'] = str(self.path)
        data['recent_logs'] = [log.to_dict() for log in self.recent_logs]
        data['config'] = self.config.to_dict() if self.config else {}
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create project from dictionary."""
        # Convert logs back to LogEntry objects
        if 'recent_logs' in data:
            data['recent_logs'] = [
                LogEntry.from_dict(log) if isinstance(log, dict) else log
                for log in data['recent_logs']
            ]
        
        # Convert config back to ProjectConfig object
        if 'config' in data and isinstance(data['config'], dict):
            data['config'] = ProjectConfig.from_dict(data['config'])
        
        return cls(**data)
    
    def is_valid(self) -> bool:
        """Check if project directory and structure is valid."""
        return (
            self.path.exists() and 
            self.path.is_dir() and
            self.has_init
        )
    
    def get_size(self) -> int:
        """Get total size of project directory in bytes."""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(self.path):
                # Skip venv directory for size calculation
                if 'venv' in dirnames:
                    dirnames.remove('venv')
                
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    try:
                        total_size += filepath.stat().st_size
                    except (OSError, IOError):
                        continue
        except (OSError, IOError):
            pass
        
        return total_size
    
    def __str__(self) -> str:
        """String representation of project."""
        status = "running" if self.running else "stopped"
        return f"Project(name='{self.name}', status='{status}', path='{self.path}')"