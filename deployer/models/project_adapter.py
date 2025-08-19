"""Adapter layer between legacy models and SQLAlchemy models."""

from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from deployer.database.models import (
    Project as DBProject, LogEntry as DBLogEntry
)
from deployer.database.database import db_session_scope
from .project import Project as LegacyProject, LogEntry as LegacyLogEntry
from .project_config import ProjectConfig


class ProjectAdapter:
    """Adapter to bridge legacy Project model and database model."""
    
    @staticmethod
    def legacy_to_db(legacy_project: LegacyProject) -> DBProject:
        """
        Convert legacy Project to database Project.
        
        Args:
            legacy_project: Legacy Project instance
            
        Returns:
            Database Project instance
        """
        return DBProject(
            name=legacy_project.name,
            path=str(legacy_project.path),
            is_git=legacy_project.is_git,
            has_init=legacy_project.has_init,
            has_venv=legacy_project.has_venv,
            has_requirements=legacy_project.has_requirements,
            running=legacy_project.running,
            pid=legacy_project.pid,
            started_at=datetime.fromisoformat(legacy_project.started_at) if legacy_project.started_at else None,
            config=legacy_project.config.to_dict() if legacy_project.config else {}
        )
    
    @staticmethod
    def db_to_legacy(db_project: DBProject, load_logs: bool = True) -> LegacyProject:
        """
        Convert database Project to legacy Project.
        
        Args:
            db_project: Database Project instance
            load_logs: Whether to load recent logs
            
        Returns:
            Legacy Project instance
        """
        # Convert logs if requested
        recent_logs = []
        if load_logs and hasattr(db_project, 'log_entries'):
            # Get recent logs (last 100)
            recent_db_logs = sorted(db_project.log_entries, key=lambda x: x.timestamp)[-100:]
            recent_logs = [LogAdapter.db_to_legacy(log) for log in recent_db_logs]
        
        # Create legacy project
        legacy_project = LegacyProject(
            name=db_project.name,
            path=Path(db_project.path),
            is_git=db_project.is_git,
            has_init=db_project.has_init,
            has_venv=db_project.has_venv,
            has_requirements=db_project.has_requirements,
            running=db_project.running,
            pid=db_project.pid,
            started_at=db_project.started_at.isoformat() if db_project.started_at else None,
            recent_logs=recent_logs,
            config=ProjectConfig.from_dict(db_project.config) if db_project.config else ProjectConfig()
        )
        
        return legacy_project
    
    @staticmethod
    def sync_to_db(legacy_project: LegacyProject) -> Optional[DBProject]:
        """
        Sync legacy project to database, creating or updating as needed.
        
        Args:
            legacy_project: Legacy Project instance
            
        Returns:
            Database Project instance or None if failed
        """
        try:
            with db_session_scope() as session:
                # Look for existing project
                db_project = session.query(DBProject).filter_by(name=legacy_project.name).first()
                
                if db_project:
                    # Update existing project
                    db_project.path = str(legacy_project.path)
                    db_project.is_git = legacy_project.is_git
                    db_project.has_init = legacy_project.has_init
                    db_project.has_venv = legacy_project.has_venv
                    db_project.has_requirements = legacy_project.has_requirements
                    db_project.running = legacy_project.running
                    db_project.pid = legacy_project.pid
                    db_project.started_at = (
                        datetime.fromisoformat(legacy_project.started_at) 
                        if legacy_project.started_at else None
                    )
                    db_project.config = legacy_project.config.to_dict() if legacy_project.config else {}
                else:
                    # Create new project
                    db_project = ProjectAdapter.legacy_to_db(legacy_project)
                    session.add(db_project)
                
                session.flush()  # Ensure ID is assigned
                return db_project
                
        except Exception as e:
            print(f"Error syncing project to database: {e}")
            return None
    
    @staticmethod
    def load_from_db(name: str) -> Optional[LegacyProject]:
        """
        Load project from database and convert to legacy format.
        
        Args:
            name: Project name
            
        Returns:
            Legacy Project instance or None if not found
        """
        try:
            with db_session_scope() as session:
                db_project = session.query(DBProject).filter_by(name=name).first()
                if db_project:
                    return ProjectAdapter.db_to_legacy(db_project)
                return None
        except Exception as e:
            print(f"Error loading project from database: {e}")
            return None


class LogAdapter:
    """Adapter to bridge legacy LogEntry model and database model."""
    
    @staticmethod
    def legacy_to_db(legacy_log: LegacyLogEntry, project_id: int) -> DBLogEntry:
        """
        Convert legacy LogEntry to database LogEntry.
        
        Args:
            legacy_log: Legacy LogEntry instance
            project_id: Database project ID
            
        Returns:
            Database LogEntry instance
        """
        return DBLogEntry(
            project_id=project_id,
            timestamp=datetime.fromisoformat(legacy_log.timestamp),
            level=legacy_log.level,
            message=legacy_log.message,
            source='legacy',
            log_metadata={}
        )
    
    @staticmethod
    def db_to_legacy(db_log: DBLogEntry) -> LegacyLogEntry:
        """
        Convert database LogEntry to legacy LogEntry.
        
        Args:
            db_log: Database LogEntry instance
            
        Returns:
            Legacy LogEntry instance
        """
        return LegacyLogEntry(
            timestamp=db_log.timestamp.isoformat(),
            message=db_log.message,
            level=db_log.level
        )
    
    @staticmethod
    def add_log_to_db(project_name: str, message: str, level: str = 'INFO', source: str = None) -> bool:
        """
        Add log entry directly to database.
        
        Args:
            project_name: Name of the project
            message: Log message
            level: Log level
            source: Log source
            
        Returns:
            True if successful
        """
        try:
            with db_session_scope() as session:
                # Find project
                db_project = session.query(DBProject).filter_by(name=project_name).first()
                if not db_project:
                    return False
                
                # Create log entry
                log_entry = DBLogEntry(
                    project_id=db_project.id,
                    timestamp=datetime.utcnow(),
                    level=level,
                    message=message,
                    source=source or 'system',
                    log_metadata={}
                )
                
                session.add(log_entry)
                return True
                
        except Exception as e:
            print(f"Error adding log to database: {e}")
            return False


class HybridProject:
    """
    Hybrid project class that maintains compatibility with legacy code
    while using database backend when possible.
    """
    
    def __init__(self, legacy_project: LegacyProject):
        """Initialize with legacy project."""
        self._legacy = legacy_project
        self._db_id: Optional[int] = None
        
        # Try to sync to database
        db_project = ProjectAdapter.sync_to_db(legacy_project)
        if db_project:
            self._db_id = db_project.id
    
    def __getattr__(self, name):
        """Delegate attribute access to legacy project."""
        return getattr(self._legacy, name)
    
    def add_log_entry(self, message: str, level: str = 'INFO') -> None:
        """Add log entry to both legacy and database."""
        # Add to legacy project (for immediate access)
        self._legacy.add_log_entry(message, level)
        
        # Add to database (for persistence)
        if self._db_id:
            LogAdapter.add_log_to_db(self._legacy.name, message, level)
    
    def save_config(self) -> None:
        """Save configuration to both file and database."""
        # Save to file (legacy)
        self._legacy.save_config()
        
        # Update database
        if self._db_id:
            ProjectAdapter.sync_to_db(self._legacy)
    
    def refresh_from_db(self) -> None:
        """Refresh project state from database."""
        if self._db_id:
            db_project = ProjectAdapter.load_from_db(self._legacy.name)
            if db_project:
                # Update legacy project with database state
                self._legacy.running = db_project.running
                self._legacy.pid = db_project.pid
                self._legacy.started_at = db_project.started_at
                # Note: We don't update logs to avoid overwriting recent changes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, including database ID if available."""
        data = self._legacy.to_dict()
        if self._db_id:
            data['db_id'] = self._db_id
        return data
    
    @classmethod
    def from_directory(cls, project_path: Path) -> 'HybridProject':
        """Create hybrid project from directory analysis."""
        legacy_project = LegacyProject.from_directory(project_path)
        return cls(legacy_project)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HybridProject':
        """Create hybrid project from dictionary."""
        db_id = data.pop('db_id', None)
        legacy_project = LegacyProject.from_dict(data)
        hybrid = cls(legacy_project)
        if db_id:
            hybrid._db_id = db_id
        return hybrid