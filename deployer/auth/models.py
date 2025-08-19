"""Authentication models for Deployer application."""

import enum
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import bcrypt
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, 
    Enum, Text, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.types import TypeDecorator, VARCHAR
import json

from deployer.database.models import Base


class RoleEnum(enum.Enum):
    """User role enumeration."""
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class PermissionEnum(enum.Enum):
    """Permission enumeration."""
    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    
    # Process permissions
    PROCESS_START = "process:start"
    PROCESS_STOP = "process:stop"
    PROCESS_LOGS = "process:logs"
    
    # System permissions
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_CONFIG = "system:config"
    
    # User permissions
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"


class JSONField(TypeDecorator):
    """Custom JSON field for storing metadata."""
    impl = VARCHAR
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        return json.dumps(value)
    
    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        return json.loads(value)


class User(Base):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.VIEWER, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    account_locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    audit_metadata = Column(JSONField, nullable=False, default={})
    
    # Relationships
    created_by = relationship("User", remote_side=[id])
    audit_logs = relationship("AuditLog", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_user_active_role', 'is_active', 'role'),
        Index('idx_user_login_attempts', 'failed_login_attempts', 'account_locked_until'),
    )
    
    @validates('username')
    def validate_username(self, key, username):
        if not username or len(username.strip()) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(username) > 80:
            raise ValueError("Username too long")
        if not username.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return username.strip().lower()
    
    @validates('email')
    def validate_email(self, key, email):
        if not email or '@' not in email:
            raise ValueError("Valid email address required")
        return email.strip().lower()
    
    @validates('role')
    def validate_role(self, key, role):
        if isinstance(role, str):
            role = RoleEnum(role)
        return role
    
    def set_password(self, password: str) -> None:
        """Set password with bcrypt hashing."""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        self.password_changed_at = datetime.utcnow()
        self.failed_login_attempts = 0  # Reset failed attempts on password change
        self.account_locked_until = None
    
    def check_password(self, password: str) -> bool:
        """Check password against stored hash."""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def is_account_locked(self) -> bool:
        """Check if account is locked due to failed login attempts."""
        if not self.account_locked_until:
            return False
        return datetime.utcnow() < self.account_locked_until
    
    def increment_failed_login(self) -> None:
        """Increment failed login attempts and lock account if necessary."""
        self.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts for 30 minutes
        if self.failed_login_attempts >= 5:
            self.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
    
    def reset_failed_login(self) -> None:
        """Reset failed login attempts on successful login."""
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.last_login = datetime.utcnow()
    
    def get_permissions(self) -> List[PermissionEnum]:
        """Get permissions based on user role."""
        role_permissions = {
            RoleEnum.ADMIN: [
                # All permissions for admin
                PermissionEnum.PROJECT_CREATE,
                PermissionEnum.PROJECT_READ,
                PermissionEnum.PROJECT_UPDATE,
                PermissionEnum.PROJECT_DELETE,
                PermissionEnum.PROCESS_START,
                PermissionEnum.PROCESS_STOP,
                PermissionEnum.PROCESS_LOGS,
                PermissionEnum.SYSTEM_MONITOR,
                PermissionEnum.SYSTEM_CONFIG,
                PermissionEnum.USER_CREATE,
                PermissionEnum.USER_READ,
                PermissionEnum.USER_UPDATE,
                PermissionEnum.USER_DELETE,
            ],
            RoleEnum.DEVELOPER: [
                # Project and process permissions for developers
                PermissionEnum.PROJECT_CREATE,
                PermissionEnum.PROJECT_READ,
                PermissionEnum.PROJECT_UPDATE,
                PermissionEnum.PROCESS_START,
                PermissionEnum.PROCESS_STOP,
                PermissionEnum.PROCESS_LOGS,
                PermissionEnum.SYSTEM_MONITOR,
                PermissionEnum.USER_READ,
            ],
            RoleEnum.VIEWER: [
                # Read-only permissions for viewers
                PermissionEnum.PROJECT_READ,
                PermissionEnum.PROCESS_LOGS,
                PermissionEnum.SYSTEM_MONITOR,
            ]
        }
        
        return role_permissions.get(self.role, [])
    
    def has_permission(self, permission: PermissionEnum) -> bool:
        """Check if user has specific permission."""
        if not self.is_active:
            return False
        return permission in self.get_permissions()
    
    def get_full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return self.username
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email if include_sensitive else None,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.get_full_name(),
            'role': self.role.value,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'permissions': [p.value for p in self.get_permissions()]
        }
        
        if include_sensitive:
            data.update({
                'failed_login_attempts': self.failed_login_attempts,
                'is_account_locked': self.is_account_locked(),
                'password_changed_at': self.password_changed_at.isoformat() if self.password_changed_at else None,
                'metadata': self.audit_metadata
            })
        
        return data
    
    def __repr__(self):
        return f"<User(username='{self.username}', role='{self.role.value}')>"


class RefreshToken(Base):
    """Refresh token model for JWT token management."""
    __tablename__ = 'refresh_tokens'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False, index=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")
    
    # Indexes
    __table_args__ = (
        Index('idx_refresh_token_active', 'is_revoked', 'expires_at'),
        Index('idx_refresh_token_user', 'user_id', 'is_revoked'),
    )
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not revoked)."""
        return not self.is_revoked and not self.is_expired()
    
    def revoke(self) -> None:
        """Revoke the refresh token."""
        self.is_revoked = True
    
    def update_usage(self, ip_address: str = None, user_agent: str = None) -> None:
        """Update token usage information."""
        self.last_used = datetime.utcnow()
        if ip_address:
            self.ip_address = ip_address
        if user_agent:
            self.user_agent = user_agent


class AuditLog(Base):
    """Audit log model for tracking user actions."""
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSONField, nullable=False, default={})
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    success = Column(Boolean, nullable=False, default=True, index=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_action_timestamp', 'action', 'timestamp'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_success_timestamp', 'success', 'timestamp'),
    )
    
    @validates('action')
    def validate_action(self, key, action):
        if not action or len(action.strip()) == 0:
            raise ValueError("Action cannot be empty")
        return action.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'success': self.success,
            'error_message': self.error_message
        }
    
    def __repr__(self):
        return f"<AuditLog(action='{self.action}', user_id={self.user_id})>"


# Role alias for backward compatibility
Role = RoleEnum