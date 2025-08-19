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
    user_sessions = relationship("UserSession", back_populates="project")
    
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


class UserSession(Base):
    """Database model for user sessions."""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True, index=True)
    user_ip = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(String(500), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    is_active = Column(Boolean, default=True, index=True)
    log_metadata = Column(JSONEncodedDict, nullable=False, default={})
    
    # Relationships
    project = relationship("Project", back_populates="user_sessions")
    
    # Indexes
    __table_args__ = (
        Index('idx_session_active', 'is_active', 'last_activity'),
        Index('idx_session_project', 'project_id', 'is_active'),
    )
    
    @validates('session_id')
    def validate_session_id(self, key, session_id):
        if not session_id or len(session_id.strip()) == 0:
            raise ValueError("Session ID cannot be empty")
        return session_id.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'project_id': self.project_id,
            'user_ip': self.user_ip,
            'user_agent': self.user_agent,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'is_active': self.is_active,
            'metadata': self.log_metadata or {}
        }
    
    def __repr__(self):
        return f"<UserSession(session_id='{self.session_id}', active={self.is_active})>"


class SystemMetrics(Base):
    """Database model for system metrics."""
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    metric_type = Column(String(100), nullable=False, index=True)  # e.g., 'cpu_usage', 'memory_usage'
    metric_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)  # e.g., 'percent', 'bytes', 'seconds'
    tags = Column(JSONEncodedDict, nullable=False, default={})  # Additional metadata/labels
    
    # Indexes
    __table_args__ = (
        Index('idx_metrics_type_timestamp', 'metric_type', 'timestamp'),
        Index('idx_metrics_name_timestamp', 'metric_name', 'timestamp'),
        UniqueConstraint('timestamp', 'metric_type', 'metric_name', name='uq_metric_point'),
    )
    
    @validates('metric_type')
    def validate_metric_type(self, key, metric_type):
        if not metric_type or len(metric_type.strip()) == 0:
            raise ValueError("Metric type cannot be empty")
        return metric_type.strip()
    
    @validates('metric_name')
    def validate_metric_name(self, key, metric_name):
        if not metric_name or len(metric_name.strip()) == 0:
            raise ValueError("Metric name cannot be empty")
        return metric_name.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metric_type': self.metric_type,
            'metric_name': self.metric_name,
            'value': self.value,
            'unit': self.unit,
            'tags': self.tags or {}
        }
    
    def __repr__(self):
        return f"<SystemMetrics(type='{self.metric_type}', name='{self.metric_name}', value={self.value})>"


class AlertRule(Base):
    """Database model for alert rules configuration."""
    __tablename__ = 'alert_rules'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, default='warning')  # critical, warning, info
    enabled = Column(Boolean, default=True, index=True)
    
    # Condition settings
    metric_type = Column(String(100), nullable=False)
    metric_name = Column(String(100), nullable=False)
    operator = Column(String(10), nullable=False, default='>')  # >, <, >=, <=, ==, !=
    threshold = Column(Float, nullable=False)
    duration_minutes = Column(Integer, default=5)
    
    # Scope filters
    project_filter = Column(String(255), nullable=True)
    tags_filter = Column(JSONEncodedDict, nullable=False, default={})
    
    # Notification settings
    notification_channels = Column(JSONEncodedDict, nullable=False, default={})  # List as JSON
    repeat_interval_minutes = Column(Integer, default=60)
    max_notifications = Column(Integer, default=10)
    
    # Escalation
    escalate_after_minutes = Column(Integer, default=0)
    escalation_channels = Column(JSONEncodedDict, nullable=False, default={})
    
    # Auto-resolution
    auto_resolve_after_minutes = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    alert_instances = relationship("AlertInstance", back_populates="rule", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_alert_rules_enabled', 'enabled'),
        Index('idx_alert_rules_severity', 'severity'),
        Index('idx_alert_rules_metric', 'metric_type', 'metric_name'),
    )
    
    @validates('severity')
    def validate_severity(self, key, severity):
        valid_severities = ['critical', 'warning', 'info']
        if severity not in valid_severities:
            raise ValueError(f"Severity must be one of: {', '.join(valid_severities)}")
        return severity
    
    @validates('operator')
    def validate_operator(self, key, operator):
        valid_operators = ['>', '<', '>=', '<=', '==', '!=']
        if operator not in valid_operators:
            raise ValueError(f"Operator must be one of: {', '.join(valid_operators)}")
        return operator
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'severity': self.severity,
            'enabled': self.enabled,
            'metric_type': self.metric_type,
            'metric_name': self.metric_name,
            'operator': self.operator,
            'threshold': self.threshold,
            'duration_minutes': self.duration_minutes,
            'project_filter': self.project_filter,
            'tags_filter': self.tags_filter or {},
            'notification_channels': self.notification_channels or {},
            'repeat_interval_minutes': self.repeat_interval_minutes,
            'max_notifications': self.max_notifications,
            'escalate_after_minutes': self.escalate_after_minutes,
            'escalation_channels': self.escalation_channels or {},
            'auto_resolve_after_minutes': self.auto_resolve_after_minutes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by_id': self.created_by_id
        }
    
    def __repr__(self):
        return f"<AlertRule(name='{self.name}', severity='{self.severity}', enabled={self.enabled})>"


class AlertInstance(Base):
    """Database model for active/historical alert instances."""
    __tablename__ = 'alert_instances'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(255), unique=True, nullable=False, index=True)  # Unique identifier
    rule_id = Column(Integer, ForeignKey('alert_rules.id'), nullable=False, index=True)
    
    # Alert state
    status = Column(String(20), nullable=False, default='active', index=True)  # active, acknowledged, resolved, suppressed
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    
    # Trigger information
    triggered_at = Column(DateTime, default=datetime.utcnow, index=True)
    metric_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    project_name = Column(String(255), nullable=True, index=True)
    tags = Column(JSONEncodedDict, nullable=False, default={})
    
    # Status tracking
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    resolution_message = Column(Text, nullable=True)
    
    # Notification tracking
    last_notification_at = Column(DateTime, nullable=True)
    notification_count = Column(Integer, default=0)
    escalated = Column(Boolean, default=False, index=True)
    
    # Relationships
    rule = relationship("AlertRule", back_populates="alert_instances")
    acknowledged_by = relationship("User", foreign_keys=[acknowledged_by_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_alerts_status_triggered', 'status', 'triggered_at'),
        Index('idx_alerts_project_status', 'project_name', 'status'),
        Index('idx_alerts_severity_triggered', 'severity', 'triggered_at'),
    )
    
    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = ['active', 'acknowledged', 'resolved', 'suppressed']
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return status
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'alert_id': self.alert_id,
            'rule_id': self.rule_id,
            'status': self.status,
            'severity': self.severity,
            'title': self.title,
            'description': self.description,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'metric_value': self.metric_value,
            'threshold_value': self.threshold_value,
            'project_name': self.project_name,
            'tags': self.tags or {},
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'acknowledged_by_id': self.acknowledged_by_id,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by_id': self.resolved_by_id,
            'resolution_message': self.resolution_message,
            'last_notification_at': self.last_notification_at.isoformat() if self.last_notification_at else None,
            'notification_count': self.notification_count,
            'escalated': self.escalated
        }
    
    def __repr__(self):
        return f"<AlertInstance(alert_id='{self.alert_id}', status='{self.status}', severity='{self.severity}')>"


class HealthCheckConfig(Base):
    """Database model for health check configurations."""
    __tablename__ = 'health_check_configs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    check_type = Column(String(50), nullable=False, index=True)  # http, process, log, custom
    enabled = Column(Boolean, default=True, index=True)
    interval_seconds = Column(Integer, default=60)
    timeout_seconds = Column(Integer, default=30)
    
    # HTTP check specific
    url = Column(String(1000), nullable=True)
    expected_status_codes = Column(JSONEncodedDict, nullable=False, default={})  # List as JSON
    expected_response_pattern = Column(String(1000), nullable=True)
    headers = Column(JSONEncodedDict, nullable=False, default={})
    
    # Process check specific
    pid = Column(Integer, nullable=True)
    process_name = Column(String(255), nullable=True)
    max_cpu_percent = Column(Float, default=90.0)
    max_memory_mb = Column(Float, default=1024.0)
    
    # Log check specific
    log_file_path = Column(String(1000), nullable=True)
    error_patterns = Column(JSONEncodedDict, nullable=False, default={})  # List as JSON
    warning_patterns = Column(JSONEncodedDict, nullable=False, default={})  # List as JSON
    max_error_rate_per_minute = Column(Integer, default=5)
    
    # Custom check specific
    custom_params = Column(JSONEncodedDict, nullable=False, default={})
    
    # Project association
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Relationships
    project = relationship("Project", backref="health_checks")
    created_by = relationship("User", foreign_keys=[created_by_id])
    health_results = relationship("HealthCheckResult", back_populates="config", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_health_checks_type_enabled', 'check_type', 'enabled'),
        Index('idx_health_checks_project', 'project_id'),
    )
    
    @validates('check_type')
    def validate_check_type(self, key, check_type):
        valid_types = ['http', 'process', 'log', 'custom']
        if check_type not in valid_types:
            raise ValueError(f"Check type must be one of: {', '.join(valid_types)}")
        return check_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'check_type': self.check_type,
            'enabled': self.enabled,
            'interval_seconds': self.interval_seconds,
            'timeout_seconds': self.timeout_seconds,
            'url': self.url,
            'expected_status_codes': self.expected_status_codes or {},
            'expected_response_pattern': self.expected_response_pattern,
            'headers': self.headers or {},
            'pid': self.pid,
            'process_name': self.process_name,
            'max_cpu_percent': self.max_cpu_percent,
            'max_memory_mb': self.max_memory_mb,
            'log_file_path': self.log_file_path,
            'error_patterns': self.error_patterns or {},
            'warning_patterns': self.warning_patterns or {},
            'max_error_rate_per_minute': self.max_error_rate_per_minute,
            'custom_params': self.custom_params or {},
            'project_id': self.project_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by_id': self.created_by_id
        }
    
    def __repr__(self):
        return f"<HealthCheckConfig(name='{self.name}', type='{self.check_type}', enabled={self.enabled})>"


class HealthCheckResult(Base):
    """Database model for health check results."""
    __tablename__ = 'health_check_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(Integer, ForeignKey('health_check_configs.id'), nullable=False, index=True)
    check_name = Column(String(255), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)  # healthy, degraded, unhealthy, unknown
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    response_time_ms = Column(Float, nullable=True)
    message = Column(Text, nullable=True)
    details = Column(JSONEncodedDict, nullable=False, default={})
    
    # Relationships
    config = relationship("HealthCheckConfig", back_populates="health_results")
    
    # Indexes
    __table_args__ = (
        Index('idx_health_results_name_timestamp', 'check_name', 'timestamp'),
        Index('idx_health_results_status_timestamp', 'status', 'timestamp'),
        Index('idx_health_results_config_timestamp', 'config_id', 'timestamp'),
    )
    
    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = ['healthy', 'degraded', 'unhealthy', 'unknown']
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return status
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'config_id': self.config_id,
            'check_name': self.check_name,
            'status': self.status,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'response_time_ms': self.response_time_ms,
            'message': self.message,
            'details': self.details or {}
        }
    
    def __repr__(self):
        return f"<HealthCheckResult(check='{self.check_name}', status='{self.status}')>"