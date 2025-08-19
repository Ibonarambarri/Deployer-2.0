"""Authentication decorators for protecting routes."""

from functools import wraps
from typing import List, Optional, Callable, Any
from flask import request, jsonify, g, current_app

from deployer.database.database import db_session_scope
from .models import User, PermissionEnum, RoleEnum, AuditLog
from .auth import verify_token, TokenExpiredError, InvalidTokenError


def token_required(f: Callable) -> Callable:
    """
    Decorator to require valid JWT token.
    
    Args:
        f: Function to wrap
        
    Returns:
        Wrapped function
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for token in Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Check for token in cookies (fallback)
        if not token:
            token = request.cookies.get('access_token')
        
        if not token:
            return jsonify({
                'error': 'Authentication required',
                'message': 'Access token is missing'
            }), 401
        
        try:
            # Verify token
            payload = verify_token(token, 'access')
            user_id = payload.get('user_id')
            
            # Get user from database
            with db_session_scope() as session:
                user = session.query(User).filter_by(id=user_id).first()
                
                if not user or not user.is_active:
                    return jsonify({
                        'error': 'Authentication failed',
                        'message': 'User account is disabled or not found'
                    }), 401
                
                # Store user in Flask's g object for access in route
                g.current_user = user
                g.token_payload = payload
                
                return f(*args, **kwargs)
        
        except TokenExpiredError:
            return jsonify({
                'error': 'Token expired',
                'message': 'Access token has expired'
            }), 401
        
        except InvalidTokenError:
            return jsonify({
                'error': 'Invalid token',
                'message': 'Access token is invalid'
            }), 401
        
        except Exception as e:
            current_app.logger.error(f"Token validation error: {e}")
            return jsonify({
                'error': 'Authentication failed',
                'message': 'Could not validate token'
            }), 401
    
    return decorated


def role_required(*allowed_roles: RoleEnum) -> Callable:
    """
    Decorator to require specific user roles.
    
    Args:
        *allowed_roles: List of allowed roles
        
    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            user = g.get('current_user')
            
            if not user:
                return jsonify({
                    'error': 'Authentication required',
                    'message': 'User information not available'
                }), 401
            
            # Convert string roles to RoleEnum if necessary
            roles_list = []
            for role in allowed_roles:
                if isinstance(role, str):
                    try:
                        roles_list.append(RoleEnum(role))
                    except ValueError:
                        current_app.logger.warning(f"Invalid role in decorator: {role}")
                        continue
                else:
                    roles_list.append(role)
            
            if user.role not in roles_list:
                # Log unauthorized access attempt
                _log_unauthorized_access(user, f.__name__, 'insufficient_role')
                
                return jsonify({
                    'error': 'Insufficient permissions',
                    'message': f'This action requires one of the following roles: {[r.value for r in roles_list]}'
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator


def permission_required(*permissions: PermissionEnum) -> Callable:
    """
    Decorator to require specific permissions.
    
    Args:
        *permissions: List of required permissions
        
    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            user = g.get('current_user')
            
            if not user:
                return jsonify({
                    'error': 'Authentication required',
                    'message': 'User information not available'
                }), 401
            
            # Convert string permissions to PermissionEnum if necessary
            perms_list = []
            for perm in permissions:
                if isinstance(perm, str):
                    try:
                        perms_list.append(PermissionEnum(perm))
                    except ValueError:
                        current_app.logger.warning(f"Invalid permission in decorator: {perm}")
                        continue
                else:
                    perms_list.append(perm)
            
            # Check if user has all required permissions
            missing_permissions = []
            for permission in perms_list:
                if not user.has_permission(permission):
                    missing_permissions.append(permission.value)
            
            if missing_permissions:
                # Log unauthorized access attempt
                _log_unauthorized_access(user, f.__name__, 'insufficient_permissions', {
                    'missing_permissions': missing_permissions
                })
                
                return jsonify({
                    'error': 'Insufficient permissions',
                    'message': f'This action requires the following permissions: {missing_permissions}'
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator


def admin_required(f: Callable) -> Callable:
    """
    Decorator to require admin role.
    
    Args:
        f: Function to wrap
        
    Returns:
        Wrapped function
    """
    return role_required(RoleEnum.ADMIN)(f)


def developer_or_admin_required(f: Callable) -> Callable:
    """
    Decorator to require developer or admin role.
    
    Args:
        f: Function to wrap
        
    Returns:
        Wrapped function
    """
    return role_required(RoleEnum.DEVELOPER, RoleEnum.ADMIN)(f)


def audit_action(action: str, resource_type: str = None) -> Callable:
    """
    Decorator to log user actions in audit log.
    
    Args:
        action: Action being performed
        resource_type: Type of resource being acted upon
        
    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            user = g.get('current_user')
            start_time = None
            
            try:
                import time
                start_time = time.time()
                
                # Execute the function
                result = f(*args, **kwargs)
                
                # Log successful action
                _log_audit_action(
                    user=user,
                    action=action,
                    resource_type=resource_type,
                    success=True,
                    details={
                        'endpoint': request.endpoint,
                        'method': request.method,
                        'path': request.path,
                        'execution_time': time.time() - start_time if start_time else None
                    }
                )
                
                return result
            
            except Exception as e:
                # Log failed action
                _log_audit_action(
                    user=user,
                    action=action,
                    resource_type=resource_type,
                    success=False,
                    error_message=str(e),
                    details={
                        'endpoint': request.endpoint,
                        'method': request.method,
                        'path': request.path,
                        'execution_time': time.time() - start_time if start_time else None
                    }
                )
                
                # Re-raise the exception
                raise
        
        return decorated
    return decorator


def rate_limit_by_user(max_requests: int, window_minutes: int = 1) -> Callable:
    """
    Simple rate limiting decorator by user ID.
    
    Args:
        max_requests: Maximum number of requests
        window_minutes: Time window in minutes
        
    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            user = g.get('current_user')
            
            if not user:
                return jsonify({
                    'error': 'Authentication required'
                }), 401
            
            # Simple in-memory rate limiting (in production, use Redis)
            if not hasattr(current_app, '_rate_limit_store'):
                current_app._rate_limit_store = {}
            
            import time
            now = time.time()
            window_start = now - (window_minutes * 60)
            
            # Clean up old entries
            user_key = f"user_{user.id}_{f.__name__}"
            if user_key not in current_app._rate_limit_store:
                current_app._rate_limit_store[user_key] = []
            
            # Remove requests outside the window
            current_app._rate_limit_store[user_key] = [
                req_time for req_time in current_app._rate_limit_store[user_key] 
                if req_time > window_start
            ]
            
            # Check if limit exceeded
            if len(current_app._rate_limit_store[user_key]) >= max_requests:
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {max_requests} requests per {window_minutes} minute(s) allowed'
                }), 429
            
            # Add current request
            current_app._rate_limit_store[user_key].append(now)
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator


def optional_auth(f: Callable) -> Callable:
    """
    Decorator that allows but doesn't require authentication.
    If token is provided, user will be available in g.current_user.
    
    Args:
        f: Function to wrap
        
    Returns:
        Wrapped function
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for token in Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # Check for token in cookies (fallback)
        if not token:
            token = request.cookies.get('access_token')
        
        if token:
            try:
                # Verify token
                payload = verify_token(token, 'access')
                user_id = payload.get('user_id')
                
                # Get user from database
                with db_session_scope() as session:
                    user = session.query(User).filter_by(id=user_id).first()
                    
                    if user and user.is_active:
                        g.current_user = user
                        g.token_payload = payload
            
            except (TokenExpiredError, InvalidTokenError):
                # Token is invalid, but that's okay for optional auth
                pass
            except Exception as e:
                current_app.logger.warning(f"Optional auth error: {e}")
        
        return f(*args, **kwargs)
    
    return decorated


def _log_unauthorized_access(
    user: User, 
    endpoint: str, 
    reason: str, 
    details: dict = None
) -> None:
    """Log unauthorized access attempt."""
    try:
        with db_session_scope() as session:
            audit_log = AuditLog(
                user_id=user.id if user else None,
                action='unauthorized_access',
                resource_type='api',
                resource_id=endpoint,
                details={
                    'reason': reason,
                    'endpoint': endpoint,
                    'method': request.method,
                    'path': request.path,
                    **(details or {})
                },
                ip_address=_get_client_ip(),
                user_agent=request.headers.get('User-Agent', ''),
                success=False,
                error_message=f'Unauthorized access: {reason}'
            )
            
            session.add(audit_log)
    
    except Exception as e:
        current_app.logger.error(f"Error logging unauthorized access: {e}")


def _log_audit_action(
    user: User,
    action: str,
    resource_type: str = None,
    resource_id: str = None,
    success: bool = True,
    error_message: str = None,
    details: dict = None
) -> None:
    """Log audit action."""
    try:
        with db_session_scope() as session:
            audit_log = AuditLog(
                user_id=user.id if user else None,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
                ip_address=_get_client_ip(),
                user_agent=request.headers.get('User-Agent', ''),
                success=success,
                error_message=error_message
            )
            
            session.add(audit_log)
    
    except Exception as e:
        current_app.logger.error(f"Error logging audit action: {e}")


def _get_client_ip() -> Optional[str]:
    """Get client IP address from request."""
    if not request:
        return None
    
    # Check for forwarded IP first
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    
    # Check other common headers
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    return request.remote_addr