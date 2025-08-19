"""Database module for Deployer application."""

from .database import DatabaseManager, get_db_session
from .models import Project, LogEntry, UserSession, SystemMetrics, AlertRule, AlertInstance, HealthCheckConfig, HealthCheckResult

# Import auth models to register with SQLAlchemy
from deployer.auth.models import User, RefreshToken, AuditLog

__all__ = [
    'DatabaseManager',
    'get_db_session',
    'Project',
    'LogEntry', 
    'UserSession',
    'SystemMetrics',
    'AlertRule',
    'AlertInstance',
    'HealthCheckConfig',
    'HealthCheckResult',
    'User',
    'RefreshToken',
    'AuditLog'
]