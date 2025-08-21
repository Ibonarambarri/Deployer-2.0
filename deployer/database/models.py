"""SQLAlchemy database models for Deployer application."""

from datetime import datetime
from typing import List, Optional, Dict, Any
import json

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    Float, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.types import TypeDecorator, VARCHAR


Base = declarative_base()


class JSONEncodedDict(TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""
    impl = VARCHAR
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        return json.dumps(value)
    
    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        return json.loads(value)


class Project(Base):
    """Database model for projects."""
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    path = Column(String(500), nullable=False)
    is_git = Column(Boolean, default=False)
    has_init = Column(Boolean, default=False)
    has_venv = Column(Boolean, default=False)
    has_requirements = Column(Boolean, default=False)
    running = Column(Boolean, default=False, index=True)
    pid = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    config = Column(JSONEncodedDict, nullable=False, default={})
    
    # Relationships
    log_entries = relationship("LogEntry", back_populates="project", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_project_status', 'name', 'running'),
        Index('idx_project_created', 'created_at'),
    )
    
    @validates('name')
    def validate_name(self, key, name):
        if not name or len(name.strip()) == 0:
            raise ValueError("Project name cannot be empty")
        if len(name) > 255:
            raise ValueError("Project name too long")
        return name.strip()
    
    @validates('path')
    def validate_path(self, key, path):
        if not path or len(path.strip()) == 0:
            raise ValueError("Project path cannot be empty")
        return path.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'is_git': self.is_git,
            'has_init': self.has_init,
            'has_venv': self.has_venv,
            'has_requirements': self.has_requirements,
            'running': self.running,
            'pid': self.pid,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'config': self.config or {}
        }
    
    def __repr__(self):
        return f"<Project(name='{self.name}', running={self.running})>"


class LogEntry(Base):
    """Database model for log entries."""
    __tablename__ = 'log_entries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(String(20), nullable=False, default='INFO', index=True)
    message = Column(Text, nullable=False)
    source = Column(String(100), nullable=True)  # e.g., 'deployment', 'build', 'test'
    log_metadata = Column(JSONEncodedDict, nullable=False, default={})
    
    # Relationships
    project = relationship("Project", back_populates="log_entries")
    
    # Indexes
    __table_args__ = (
        Index('idx_log_project_timestamp', 'project_id', 'timestamp'),
        Index('idx_log_level_timestamp', 'level', 'timestamp'),
    )
    
    @validates('level')
    def validate_level(self, key, level):
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if level not in valid_levels:
            raise ValueError(f"Invalid log level: {level}")
        return level
    
    @validates('message')
    def validate_message(self, key, message):
        if not message or len(message.strip()) == 0:
            raise ValueError("Log message cannot be empty")
        return message.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'level': self.level,
            'message': self.message,
            'source': self.source,
            'metadata': self.log_metadata or {}
        }
    
    def __repr__(self):
        return f"<LogEntry(project_id={self.project_id}, level='{self.level}')>"




