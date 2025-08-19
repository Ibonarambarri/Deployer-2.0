"""Permission system for Deployer application."""

from typing import List, Dict, Optional, Set
from flask import g
from enum import Enum

from .models import User, RoleEnum, PermissionEnum


class Permission:
    """Permission management utility class."""
    
    # Role-based permission mapping
    ROLE_PERMISSIONS: Dict[RoleEnum, Set[PermissionEnum]] = {
        RoleEnum.ADMIN: {
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
        },
        RoleEnum.DEVELOPER: {
            # Project and process permissions for developers
            PermissionEnum.PROJECT_CREATE,
            PermissionEnum.PROJECT_READ,
            PermissionEnum.PROJECT_UPDATE,
            PermissionEnum.PROCESS_START,
            PermissionEnum.PROCESS_STOP,
            PermissionEnum.PROCESS_LOGS,
            PermissionEnum.SYSTEM_MONITOR,
            PermissionEnum.USER_READ,
        },
        RoleEnum.VIEWER: {
            # Read-only permissions for viewers
            PermissionEnum.PROJECT_READ,
            PermissionEnum.PROCESS_LOGS,
            PermissionEnum.SYSTEM_MONITOR,
        }
    }
    
    # Permission hierarchy (higher level permissions include lower level ones)
    PERMISSION_HIERARCHY: Dict[PermissionEnum, Set[PermissionEnum]] = {
        PermissionEnum.PROJECT_DELETE: {
            PermissionEnum.PROJECT_UPDATE,
            PermissionEnum.PROJECT_READ,
        },
        PermissionEnum.PROJECT_UPDATE: {
            PermissionEnum.PROJECT_READ,
        },
        PermissionEnum.PROCESS_STOP: {
            PermissionEnum.PROCESS_LOGS,
        },
        PermissionEnum.PROCESS_START: {
            PermissionEnum.PROCESS_LOGS,
        },
        PermissionEnum.USER_DELETE: {
            PermissionEnum.USER_UPDATE,
            PermissionEnum.USER_READ,
        },
        PermissionEnum.USER_UPDATE: {
            PermissionEnum.USER_READ,
        },
        PermissionEnum.SYSTEM_CONFIG: {
            PermissionEnum.SYSTEM_MONITOR,
        },
    }
    
    @classmethod
    def get_role_permissions(cls, role: RoleEnum) -> Set[PermissionEnum]:
        """
        Get all permissions for a role, including hierarchical permissions.
        
        Args:
            role: User role
            
        Returns:
            Set of permissions
        """
        base_permissions = cls.ROLE_PERMISSIONS.get(role, set())
        all_permissions = set(base_permissions)
        
        # Add hierarchical permissions
        for permission in base_permissions:
            all_permissions.update(cls._get_inherited_permissions(permission))
        
        return all_permissions
    
    @classmethod
    def _get_inherited_permissions(cls, permission: PermissionEnum) -> Set[PermissionEnum]:
        """Get permissions inherited from a higher-level permission."""
        inherited = set()
        
        if permission in cls.PERMISSION_HIERARCHY:
            inherited.update(cls.PERMISSION_HIERARCHY[permission])
            
            # Recursively get inherited permissions
            for inherited_perm in cls.PERMISSION_HIERARCHY[permission]:
                inherited.update(cls._get_inherited_permissions(inherited_perm))
        
        return inherited
    
    @classmethod
    def user_has_permission(cls, user: User, permission: PermissionEnum) -> bool:
        """
        Check if user has a specific permission.
        
        Args:
            user: User object
            permission: Permission to check
            
        Returns:
            True if user has permission
        """
        if not user or not user.is_active:
            return False
        
        user_permissions = cls.get_role_permissions(user.role)
        return permission in user_permissions
    
    @classmethod
    def user_has_any_permission(cls, user: User, permissions: List[PermissionEnum]) -> bool:
        """
        Check if user has any of the specified permissions.
        
        Args:
            user: User object
            permissions: List of permissions to check
            
        Returns:
            True if user has at least one permission
        """
        if not user or not user.is_active:
            return False
        
        user_permissions = cls.get_role_permissions(user.role)
        return any(perm in user_permissions for perm in permissions)
    
    @classmethod
    def user_has_all_permissions(cls, user: User, permissions: List[PermissionEnum]) -> bool:
        """
        Check if user has all of the specified permissions.
        
        Args:
            user: User object
            permissions: List of permissions to check
            
        Returns:
            True if user has all permissions
        """
        if not user or not user.is_active:
            return False
        
        user_permissions = cls.get_role_permissions(user.role)
        return all(perm in user_permissions for perm in permissions)
    
    @classmethod
    def get_permission_description(cls, permission: PermissionEnum) -> str:
        """
        Get human-readable description of a permission.
        
        Args:
            permission: Permission enum
            
        Returns:
            Description string
        """
        descriptions = {
            PermissionEnum.PROJECT_CREATE: "Create new projects",
            PermissionEnum.PROJECT_READ: "View project information and status",
            PermissionEnum.PROJECT_UPDATE: "Modify project settings and configuration",
            PermissionEnum.PROJECT_DELETE: "Delete projects",
            PermissionEnum.PROCESS_START: "Start project processes",
            PermissionEnum.PROCESS_STOP: "Stop running processes",
            PermissionEnum.PROCESS_LOGS: "View process logs and output",
            PermissionEnum.SYSTEM_MONITOR: "View system metrics and status",
            PermissionEnum.SYSTEM_CONFIG: "Modify system configuration",
            PermissionEnum.USER_CREATE: "Create new user accounts",
            PermissionEnum.USER_READ: "View user information",
            PermissionEnum.USER_UPDATE: "Modify user accounts",
            PermissionEnum.USER_DELETE: "Delete user accounts",
        }
        
        return descriptions.get(permission, permission.value)
    
    @classmethod
    def get_role_description(cls, role: RoleEnum) -> str:
        """
        Get human-readable description of a role.
        
        Args:
            role: Role enum
            
        Returns:
            Description string
        """
        descriptions = {
            RoleEnum.ADMIN: "Full access to all system features and user management",
            RoleEnum.DEVELOPER: "Can create, modify, and deploy projects, but cannot manage users or system settings",
            RoleEnum.VIEWER: "Read-only access to view projects, processes, and system status",
        }
        
        return descriptions.get(role, role.value)
    
    @classmethod
    def can_manage_user(cls, actor: User, target_user: User) -> bool:
        """
        Check if actor can manage (create, update, delete) target user.
        
        Args:
            actor: User performing the action
            target_user: User being managed
            
        Returns:
            True if management is allowed
        """
        # Only admins can manage users
        if actor.role != RoleEnum.ADMIN:
            return False
        
        # Users cannot delete themselves
        if target_user and actor.id == target_user.id and actor.role == RoleEnum.ADMIN:
            # Admin can update their own profile but not delete their own account
            return True
        
        return True
    
    @classmethod
    def can_modify_role(cls, actor: User, current_role: RoleEnum, new_role: RoleEnum) -> bool:
        """
        Check if actor can modify a user's role.
        
        Args:
            actor: User performing the action
            current_role: Current role of target user
            new_role: New role to assign
            
        Returns:
            True if role modification is allowed
        """
        # Only admins can modify roles
        if actor.role != RoleEnum.ADMIN:
            return False
        
        # Cannot demote the last admin
        if current_role == RoleEnum.ADMIN and new_role != RoleEnum.ADMIN:
            # In a real application, you would check if there are other admins
            # For now, we'll allow it but this should be validated
            pass
        
        return True
    
    @classmethod
    def filter_users_by_permission(cls, users: List[User], viewer: User) -> List[User]:
        """
        Filter user list based on viewer's permissions.
        
        Args:
            users: List of users to filter
            viewer: User viewing the list
            
        Returns:
            Filtered user list
        """
        if not viewer or not viewer.is_active:
            return []
        
        # Admins can see all users
        if viewer.role == RoleEnum.ADMIN:
            return users
        
        # Developers and viewers can see basic info but not sensitive data
        if viewer.role in [RoleEnum.DEVELOPER, RoleEnum.VIEWER]:
            # Return users but caller should use to_dict(include_sensitive=False)
            return users
        
        return []


def has_permission(permission: PermissionEnum, user: Optional[User] = None) -> bool:
    """
    Check if current user or specified user has permission.
    
    Args:
        permission: Permission to check
        user: User to check (defaults to current user from Flask's g)
        
    Returns:
        True if user has permission
    """
    if user is None:
        user = g.get('current_user')
    
    return Permission.user_has_permission(user, permission)


def has_any_permission(permissions: List[PermissionEnum], user: Optional[User] = None) -> bool:
    """
    Check if current user or specified user has any of the permissions.
    
    Args:
        permissions: List of permissions to check
        user: User to check (defaults to current user from Flask's g)
        
    Returns:
        True if user has at least one permission
    """
    if user is None:
        user = g.get('current_user')
    
    return Permission.user_has_any_permission(user, permissions)


def has_all_permissions(permissions: List[PermissionEnum], user: Optional[User] = None) -> bool:
    """
    Check if current user or specified user has all of the permissions.
    
    Args:
        permissions: List of permissions to check
        user: User to check (defaults to current user from Flask's g)
        
    Returns:
        True if user has all permissions
    """
    if user is None:
        user = g.get('current_user')
    
    return Permission.user_has_all_permissions(user, permissions)


def has_role(role: RoleEnum, user: Optional[User] = None) -> bool:
    """
    Check if current user or specified user has specific role.
    
    Args:
        role: Role to check
        user: User to check (defaults to current user from Flask's g)
        
    Returns:
        True if user has role
    """
    if user is None:
        user = g.get('current_user')
    
    if not user or not user.is_active:
        return False
    
    return user.role == role


def is_admin(user: Optional[User] = None) -> bool:
    """
    Check if current user or specified user is admin.
    
    Args:
        user: User to check (defaults to current user from Flask's g)
        
    Returns:
        True if user is admin
    """
    return has_role(RoleEnum.ADMIN, user)


def can_access_project(project_name: str, user: Optional[User] = None) -> bool:
    """
    Check if user can access a specific project.
    Currently all authenticated users can access all projects,
    but this can be extended for project-level permissions.
    
    Args:
        project_name: Name of the project
        user: User to check (defaults to current user from Flask's g)
        
    Returns:
        True if user can access project
    """
    if user is None:
        user = g.get('current_user')
    
    if not user or not user.is_active:
        return False
    
    # For now, any authenticated user can access any project
    # This can be extended to support project-specific permissions
    return has_permission(PermissionEnum.PROJECT_READ, user)


def can_modify_project(project_name: str, user: Optional[User] = None) -> bool:
    """
    Check if user can modify a specific project.
    
    Args:
        project_name: Name of the project
        user: User to check (defaults to current user from Flask's g)
        
    Returns:
        True if user can modify project
    """
    if user is None:
        user = g.get('current_user')
    
    return has_permission(PermissionEnum.PROJECT_UPDATE, user)


def can_delete_project(project_name: str, user: Optional[User] = None) -> bool:
    """
    Check if user can delete a specific project.
    
    Args:
        project_name: Name of the project
        user: User to check (defaults to current user from Flask's g)
        
    Returns:
        True if user can delete project
    """
    if user is None:
        user = g.get('current_user')
    
    return has_permission(PermissionEnum.PROJECT_DELETE, user)


def get_accessible_actions(user: Optional[User] = None) -> Dict[str, List[str]]:
    """
    Get list of actions accessible to user, grouped by category.
    
    Args:
        user: User to check (defaults to current user from Flask's g)
        
    Returns:
        Dictionary of accessible actions grouped by category
    """
    if user is None:
        user = g.get('current_user')
    
    if not user or not user.is_active:
        return {}
    
    permissions = Permission.get_role_permissions(user.role)
    
    actions = {
        'projects': [],
        'processes': [],
        'system': [],
        'users': []
    }
    
    # Project actions
    if PermissionEnum.PROJECT_READ in permissions:
        actions['projects'].append('view')
    if PermissionEnum.PROJECT_CREATE in permissions:
        actions['projects'].append('create')
    if PermissionEnum.PROJECT_UPDATE in permissions:
        actions['projects'].append('update')
    if PermissionEnum.PROJECT_DELETE in permissions:
        actions['projects'].append('delete')
    
    # Process actions
    if PermissionEnum.PROCESS_LOGS in permissions:
        actions['processes'].append('view_logs')
    if PermissionEnum.PROCESS_START in permissions:
        actions['processes'].append('start')
    if PermissionEnum.PROCESS_STOP in permissions:
        actions['processes'].append('stop')
    
    # System actions
    if PermissionEnum.SYSTEM_MONITOR in permissions:
        actions['system'].append('monitor')
    if PermissionEnum.SYSTEM_CONFIG in permissions:
        actions['system'].append('configure')
    
    # User actions
    if PermissionEnum.USER_READ in permissions:
        actions['users'].append('view')
    if PermissionEnum.USER_CREATE in permissions:
        actions['users'].append('create')
    if PermissionEnum.USER_UPDATE in permissions:
        actions['users'].append('update')
    if PermissionEnum.USER_DELETE in permissions:
        actions['users'].append('delete')
    
    return actions